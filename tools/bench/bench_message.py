#!/usr/bin/env python3
"""Micro-benchmark Message construction strategies for PR2.

Compares:
  1. Message(**kwargs)              — current pydantic validation path
  2. Message.model_construct(...)   — pydantic, validation skipped (§4.1)
  3. @dataclass(slots=True)         — drop pydantic on hot path (§4.3)

Measures both construction wall-clock and per-object memory.

Each strategy runs in a fresh subprocess so RSS readings aren't polluted
by previous high-water marks.
"""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from sawmill.models.message import FileRef, Message


@dataclass(slots=True)
class MessageData:
    """Candidate replacement: a plain dataclass with __slots__."""

    start_line: int
    end_line: int
    raw_text: str
    content: str
    severity: str | None = None
    message_id: str | None = None
    category: str | None = None
    file_ref: FileRef | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def make_kwargs(i: int) -> dict[str, Any]:
    return {
        "start_line": i,
        "end_line": i + 2,
        "raw_text": f"hal: *W,URAREG (rtl/foo_{i % 32}.sv,{i},12): unused register 'sig_{i}'",
        "content": f"unused register 'sig_{i}'",
        "severity": "warning",
        "message_id": "URAREG",
        "category": "hal",
        "file_ref": FileRef(path=f"rtl/foo_{i % 32}.sv", line=i),
        "metadata": {"tool": "hal"},
    }


def _rss_kb() -> int:
    """Current RSS in KB (not peak — use /proc so each subprocess starts clean)."""
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return 0


def measure(label: str, build_fn, n: int) -> dict:
    gc.collect()
    rss_before = _rss_kb()
    t0 = time.perf_counter()
    items = build_fn(n)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    rss_after = _rss_kb()
    # Hold a reference, tickle endpoints so the constructor work isn't elided.
    assert items[0].start_line == 0
    assert items[-1].start_line == n - 1
    return {
        "label": label,
        "n": n,
        "build_ms": round(elapsed_ms, 1),
        "per_item_us": round(elapsed_ms * 1000 / n, 2),
        "rss_delta_mb": round((rss_after - rss_before) / 1024, 1),
        "per_item_bytes": round((rss_after - rss_before) * 1024 / n, 1),
    }


def build_pydantic_validated(n: int) -> list[Message]:
    return [Message(**make_kwargs(i)) for i in range(n)]


def build_pydantic_construct(n: int) -> list[Message]:
    return [Message.model_construct(**make_kwargs(i)) for i in range(n)]


def build_dataclass(n: int) -> list[MessageData]:
    return [MessageData(**make_kwargs(i)) for i in range(n)]


STRATEGIES = {
    "validated": ("pydantic (validated)", build_pydantic_validated),
    "construct": ("pydantic.model_construct", build_pydantic_construct),
    "dataclass": ("dataclass(slots=True)", build_dataclass),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Message construction micro-benchmark.")
    parser.add_argument("--n", type=int, default=200_000, help="Items per run (default 200k).")
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES.keys(),
        help="Run a single strategy (used internally by subprocess sweep).",
    )
    args = parser.parse_args()

    if args.strategy:
        label, fn = STRATEGIES[args.strategy]
        # Warm-up: discard timing of the very first batch so import/JIT cost
        # doesn't skew the result.
        fn(min(1000, args.n))
        result = measure(label, fn, args.n)
        print(json.dumps(result))
        return

    results = []
    for key in STRATEGIES:
        proc = subprocess.run(
            [sys.executable, __file__, "--strategy", key, "--n", str(args.n)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            raise SystemExit(f"strategy {key} failed")
        results.append(json.loads(proc.stdout.strip().splitlines()[-1]))

    baseline = results[0]
    print(f"\nN = {args.n:,} per strategy, fresh subprocess each\n")
    print(
        f"  {'strategy':<28} {'build':>12} {'per item':>10} "
        f"{'RSS Δ':>10} {'per item':>11} {'speedup':>9}"
    )
    print(f"  {'-' * 28} {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 11} {'-' * 9}")
    for r in results:
        speedup = baseline["build_ms"] / r["build_ms"] if r["build_ms"] else float("inf")
        print(
            f"  {r['label']:<28} "
            f"{r['build_ms']:>10.1f}ms "
            f"{r['per_item_us']:>8.2f}μs "
            f"{r['rss_delta_mb']:>8.1f}MB "
            f"{r['per_item_bytes']:>9.1f}B "
            f"{speedup:>8.2f}x"
        )


if __name__ == "__main__":
    main()
