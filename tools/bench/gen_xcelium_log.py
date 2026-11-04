#!/usr/bin/env python3
"""Synthetic Xcelium log generator for benchmarking sawmill.

Produces a log that the xcelium plugin will parse, with a realistic mix of
severities, rule codes, file refs, and preamble code+pointer pairs.
Message-to-line ratio matches real Xcelium output: each diagnostic averages
~4 raw lines once preambles and continuations are included.

Usage:
    python tools/bench/gen_xcelium_log.py --messages 500000 --out big.log
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

TOOLS = ["hal", "halcheck", "halstruct", "halsynth"]

SEVERITY_LETTERS = ["F", "E", "W", "N"]
SEVERITY_WEIGHTS = [1, 30, 500, 200]

RULES = [
    "URAREG",
    "URDREG",
    "UEASTR",
    "PRMSZM",
    "PRMBSE",
    "PRMVAL",
    "USEPAR",
    "SYNASN",
    "ACNCPI",
    "RSTINP",
    "DIFRST",
    "MLTDRV",
    "TIELOG",
    "DFDRVS",
    "IOPNTA",
    "CSEINP",
    "ALWLTE",
    "NOCOND",
    "NOBLKN",
    "WRNOWT",
]

FILES = [f"rtl/{m}/{m}_{n}.sv" for m in ("cpu", "mem", "io", "fabric", "phy") for n in range(8)]

MESSAGES = [
    "register '{sig}' is unread or unused",
    "width mismatch on assignment to '{sig}' ({a} vs {b} bits)",
    "parameter '{sig}' overrides default value",
    "signal '{sig}' has multiple continuous drivers",
    "tying input '{sig}' to constant",
    "reset '{sig}' not synchronised to clock domain '{clk}'",
    "asynchronous control path on '{sig}'",
    "inout port '{sig}' drives multiple internal nets",
    "case statement on '{sig}' is missing 'default' branch",
    "always block sensitivity list incomplete for '{sig}'",
]

SIGNALS = ["clk", "rst_n", "data", "valid", "ready", "addr", "wr_en", "rd_en", "ctrl", "fifo"]


def emit_header(out, tool: str) -> None:
    out.write(f"{tool}: 25.03-s004: (c) Copyright 1995-2025 Cadence Design Systems, Inc.\n")
    out.write(f"{tool}: started at Mon Jan  1 12:00:00 2026\n")
    out.write(f"{tool}: command-line arguments: -elaborate -access +rwc top.sv\n")
    out.write("\n")


def emit_filler(out, rng: random.Random, n: int) -> None:
    for _ in range(n):
        out.write(f"  reading source file 'rtl/{rng.choice(SIGNALS)}.sv'\n")


def emit_message(out, rng: random.Random, line_counter: list[int]) -> None:
    tool = rng.choice(TOOLS)
    sev = rng.choices(SEVERITY_LETTERS, weights=SEVERITY_WEIGHTS, k=1)[0]
    rule = rng.choice(RULES)
    has_loc = rng.random() < 0.85
    sig = rng.choice(SIGNALS)
    msg = rng.choice(MESSAGES).format(
        sig=sig, a=rng.randint(1, 64), b=rng.randint(1, 64), clk=rng.choice(SIGNALS)
    )

    # ~50% of messages get a preamble: code line + pointer line just above
    if has_loc and rng.random() < 0.5:
        col = rng.randint(8, 60)
        out.write(f"      assign {sig}_q = {sig}_d;\n")
        line_counter[0] += 1
        out.write(" " * col + "|\n")
        line_counter[0] += 1

    if has_loc:
        f = rng.choice(FILES)
        ln = rng.randint(1, 9999)
        col = rng.randint(1, 80)
        out.write(f"{tool}: *{sev},{rule} ({f},{ln}|{col}): {msg}\n")
    else:
        out.write(f"{tool}: *{sev},{rule}: {msg}\n")
    line_counter[0] += 1

    # ~25% get a tab-indented continuation
    if rng.random() < 0.25:
        out.write(f"\t  see also definition at rtl/{rng.choice(SIGNALS)}.sv\n")
        line_counter[0] += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic Xcelium log.")
    parser.add_argument(
        "--messages",
        type=int,
        default=100_000,
        help="Number of diagnostic messages to emit (default 100k).",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output file path.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default 42).")
    parser.add_argument(
        "--filler-every",
        type=int,
        default=200,
        help="Emit a block of non-diagnostic filler lines every N messages.",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    line_counter = [0]

    with open(args.out, "w", encoding="utf-8") as out:
        emit_header(out, "hal")
        for i in range(args.messages):
            emit_message(out, rng, line_counter)
            if args.filler_every and i and i % args.filler_every == 0:
                emit_filler(out, rng, rng.randint(2, 6))

    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(
        f"wrote {args.messages} messages, {line_counter[0]} diagnostic lines, "
        f"{size_mb:.1f} MB -> {args.out}"
    )


if __name__ == "__main__":
    main()
