#!/usr/bin/env python3
"""Sawmill benchmark runner.

Measures parse cost and filter latency for the Xcelium plugin against
synthetic logs of varying sizes. Each size is run in a fresh subprocess so
peak RSS is not polluted by previous iterations.

Usage:
    # Single size, in-process (use this when debugging the bench itself):
    python tools/bench/run_bench.py --size 100000

    # Sweep — spawns a clean subprocess per size:
    python tools/bench/run_bench.py --sweep 100000 500000 1000000
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from statistics import median

BENCH_DIR = Path(__file__).parent
GEN_SCRIPT = BENCH_DIR / "gen_xcelium_log.py"


_PAGE_KB = os.sysconf("SC_PAGE_SIZE") // 1024


def _rss_kb() -> int:
    """Current resident set size in KB (Linux /proc/self/statm)."""
    with open("/proc/self/statm") as f:
        resident_pages = int(f.read().split()[1])
    return resident_pages * _PAGE_KB


def _peak_rss_kb() -> int:
    """Peak resident set size in KB (ru_maxrss is KB on Linux)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _time_ms(fn, *args, repeats: int = 5):
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn(*args)
        samples.append((time.perf_counter() - t0) * 1000)
    return median(samples), len(result) if hasattr(result, "__len__") else None


def run_single(size: int, log_path: Path, keep: bool) -> dict:
    """Run the benchmark for one size in the current process."""
    from sawmill_plugin_xcelium.plugin import XceliumPlugin

    if not log_path.exists() or not keep:
        print(f"  generating {size} messages -> {log_path}", file=sys.stderr)
        subprocess.run(
            [sys.executable, str(GEN_SCRIPT), "--messages", str(size), "--out", str(log_path)],
            check=True,
        )

    file_size_mb = log_path.stat().st_size / (1024 * 1024)
    plugin = XceliumPlugin()

    baseline_rss = _rss_kb()

    # Parse — measure both time to first yield (proxy for "first row drawn"
    # once PR3 lands the background worker) and total time to exhaust.
    t0 = time.perf_counter()
    it = plugin.load_and_parse(log_path)
    try:
        first = next(it)
        first_ms = (time.perf_counter() - t0) * 1000
        messages = [first]
        messages.extend(it)
    except StopIteration:
        first_ms = (time.perf_counter() - t0) * 1000
        messages = []
    parse_ms = (time.perf_counter() - t0) * 1000

    post_parse_rss = _rss_kb()
    parse_delta_mb = (post_parse_rss - baseline_rss) / 1024

    # Filter benchmarks go through sawmill's real filter path (as used by
    # SawmillApp._apply_filters). Each repeated 5x, median reported.
    from sawmill.core.filter import (
        FilterEngine,
        filter_by_severity_toggles,
        match_message_id,
    )

    # Show only warning + note: disable every other plugin-defined level.
    levels = plugin.get_severity_levels()
    level_ids = [lv["id"] if isinstance(lv, dict) else lv.id for lv in levels]
    sev_toggles = {sid: sid in {"warning", "note"} for sid in level_ids}
    sev_ms, sev_kept = _time_ms(lambda: filter_by_severity_toggles(messages, sev_toggles))

    id_ms, id_kept = _time_ms(
        lambda: [m for m in messages if match_message_id(m.message_id, "URAREG")]
    )

    # Mirrors the cat: prefix filter in _apply_filters
    cat_ms, cat_kept = _time_ms(
        lambda: [m for m in messages if m.category and m.category.lower() == "halcheck"]
    )

    engine = FilterEngine()
    regex_ms, regex_kept = _time_ms(
        lambda: engine.apply_filter("width mismatch", messages, case_sensitive=False)
    )

    # Raw substring scan: a lower bound, not a sawmill code path.
    substr_ms, substr_kept = _time_ms(lambda: [m for m in messages if "parameter" in m.raw_text])

    final_rss = _rss_kb()
    final_delta_mb = (final_rss - baseline_rss) / 1024

    return {
        "size": size,
        "file_mb": round(file_size_mb, 1),
        "messages": len(messages),
        "first_msg_ms": round(first_ms, 2),
        "parse_ms": round(parse_ms, 1),
        "parse_rss_delta_mb": round(parse_delta_mb, 1),
        "final_rss_delta_mb": round(final_delta_mb, 1),
        "peak_rss_mb": round(_peak_rss_kb() / 1024, 1),
        "filter_sev_ms": round(sev_ms, 2),
        "filter_sev_kept": sev_kept,
        "filter_id_ms": round(id_ms, 2),
        "filter_id_kept": id_kept,
        "filter_cat_ms": round(cat_ms, 2),
        "filter_cat_kept": cat_kept,
        "filter_regex_ms": round(regex_ms, 2),
        "filter_regex_kept": regex_kept,
        "filter_substr_ms": round(substr_ms, 2),
        "filter_substr_kept": substr_kept,
    }


def format_row(r: dict) -> str:
    first_ms = r.get("first_msg_ms")
    first_str = f"{first_ms:>6.2f}ms" if first_ms is not None else "    n/a"
    peak = r.get("peak_rss_mb")
    peak_str = f"{peak:>7.1f}MB" if peak is not None else "    n/a"
    return (
        f"{r['size']:>10,}  "
        f"{r['file_mb']:>7.1f}MB  "
        f"{r['messages']:>10,}  "
        f"first: {first_str}  "
        f"parse: {r['parse_ms']:>8.1f}ms  "
        f"rss(parse): {r['parse_rss_delta_mb']:>6.1f}MB  "
        f"rss(end): {r['final_rss_delta_mb']:>6.1f}MB  "
        f"peak: {peak_str}"
    )


def format_filter_row(r: dict) -> str:
    return (
        f"{r['size']:>10,}  "
        f"sev: {r['filter_sev_ms']:>6.2f}ms ({r['filter_sev_kept']:>7,})  "
        f"id: {r['filter_id_ms']:>6.2f}ms ({r['filter_id_kept']:>5,})  "
        f"cat: {r['filter_cat_ms']:>6.2f}ms ({r['filter_cat_kept']:>6,})  "
        f"regex: {r['filter_regex_ms']:>6.2f}ms ({r['filter_regex_kept']:>5,})  "
        f"substr(lower bound): {r['filter_substr_ms']:>6.2f}ms ({r['filter_substr_kept']:>5,})"
    )


def run_sweep(sizes: list[int], out_dir: Path, keep: bool, results_path: Path | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for size in sizes:
        log_path = out_dir / f"xcelium-{size}.log"
        print(f"\n=== size={size} ===", file=sys.stderr)

        # Run in a subprocess so RSS is clean per size
        proc = subprocess.run(
            [sys.executable, __file__, "--size", str(size), "--log-path", str(log_path), "--json"]
            + (["--keep"] if keep else []),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(f"bench failed for size={size}")
        # Stderr is informational; stdout is the JSON line
        sys.stderr.write(proc.stderr)
        line = proc.stdout.strip().splitlines()[-1]
        results.append(json.loads(line))

    print("\n=== Parse & memory ===")
    for r in results:
        print(format_row(r))

    print("\n=== Filter latency ===")
    for r in results:
        print(format_filter_row(r))

    if results_path:
        results_path.write_text(json.dumps(results, indent=2))
        print(f"\nwrote results to {results_path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sawmill benchmark runner.")
    parser.add_argument("--size", type=int, help="Single-run message count.")
    parser.add_argument(
        "--sweep", type=int, nargs="+", help="Run a sweep of sizes, one subprocess each."
    )
    parser.add_argument("--log-path", type=Path, help="Log path for single run; default is /tmp.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/tmp/sawmill-bench"),
        help="Directory for generated logs during a sweep.",
    )
    parser.add_argument("--keep", action="store_true", help="Reuse existing generated logs.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON line on stdout (used internally by --sweep).",
    )
    parser.add_argument("--results", type=Path, help="Write sweep results to this JSON path.")
    args = parser.parse_args()

    if args.sweep:
        run_sweep(args.sweep, args.out_dir, args.keep, args.results)
    elif args.size is not None:
        log_path = args.log_path or Path(f"/tmp/xcelium-{args.size}.log")
        result = run_single(args.size, log_path, args.keep)
        if args.json:
            print(json.dumps(result))
        else:
            print(format_row(result))
            print(format_filter_row(result))
    else:
        parser.error("must provide --size or --sweep")


if __name__ == "__main__":
    main()
