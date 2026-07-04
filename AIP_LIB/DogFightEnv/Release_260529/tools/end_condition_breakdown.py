"""Tally per-episode end_condition counts from a train-watch RUNDIR's train.log.

training_log.csv's win_rate comes from the platform's own classifier and does
not separate a genuine "target destroyed" kill from a "target altitude below
min" forced-ground outcome. This scans the full raw console log (every
SingleAgentEnvRunner episode-end print, including the "[repeated Nx across
cluster]" collapsed lines) and reports each end_condition's share directly,
so training progress can be judged against real kills specifically.

Usage:
    python tools/end_condition_breakdown.py --rundir artifacts/watch/<stamp>
    python tools/end_condition_breakdown.py --rundir artifacts/watch/<stamp> --last-n-lines 20000
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_monitor import _detect_encoding  # noqa: E402

TERMINATION_RE = re.compile(r"termination= \[([^\]]+)\]")
REPEAT_RE = re.compile(r"repeated (\d+)x")


def read_all_text(path: Path) -> str:
    with open(path, "rb") as f:
        encoding = _detect_encoding(f.read(3))
        f.seek(0)
        data = f.read()
    return data.decode(encoding, errors="replace")


def tally(text: str, last_n_lines: int | None) -> dict[str, int]:
    lines = text.splitlines()
    if last_n_lines is not None:
        lines = lines[-last_n_lines:]
    counts: dict[str, int] = {}
    for line in lines:
        m = TERMINATION_RE.search(line)
        if not m:
            continue
        rep = REPEAT_RE.search(line)
        n = int(rep.group(1)) if rep else 1
        counts[m.group(1)] = counts.get(m.group(1), 0) + n
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rundir", type=Path, required=True)
    parser.add_argument("--last-n-lines", type=int, default=None,
                         help="Only tally the last N lines of train.log (default: whole file)")
    args = parser.parse_args()

    log_path = args.rundir / "train.log"
    if not log_path.exists():
        print(f"not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    text = read_all_text(log_path)
    counts = tally(text, args.last_n_lines)
    total = sum(counts.values())
    if total == 0:
        print("no termination lines found")
        return

    print(f"{'end_condition':40s} {'count':>8s} {'share':>8s}")
    for cond, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{cond:40s} {n:8d} {n / total * 100:7.2f}%")
    print(f"{'TOTAL':40s} {total:8d}")

    real_kills = counts.get("target destroyed", 0)
    forced_ground = counts.get("target altitude below min", 0)
    print()
    print(f"real kill rate (target destroyed):        {real_kills / total * 100:.2f}%")
    print(f"forced-ground rate (target alt below min): {forced_ground / total * 100:.2f}%")


if __name__ == "__main__":
    main()
