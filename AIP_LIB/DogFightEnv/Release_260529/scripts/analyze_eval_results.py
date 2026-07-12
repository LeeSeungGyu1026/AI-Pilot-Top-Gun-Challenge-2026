from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _float(value: Any) -> float | None:
    if value in (None, "", "n/a", "nan"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _eval_dir(name_or_path: str) -> Path:
    path = Path(name_or_path)
    if path.exists():
        return path
    return ROOT / "artifacts" / "eval" / name_or_path


def _read_episodes(eval_name: str) -> list[dict[str, str]]:
    path = _eval_dir(eval_name) / "episodes.csv"
    if not path.exists():
        raise FileNotFoundError(f"episodes.csv not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _read_summary(eval_name: str) -> dict[str, Any]:
    path = _eval_dir(eval_name) / "summary.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _target_health(rows: list[dict[str, str]], outcome: str | None = None) -> list[float]:
    values: list[float] = []
    for row in rows:
        if outcome is not None and row.get("outcome") != outcome:
            continue
        value = _float(row.get("target_health"))
        if value is not None:
            values.append(value)
    return values


def _bucket_health(values: list[float]) -> dict[str, int]:
    buckets = {
        "<=0.25": 0,
        "0.25-0.50": 0,
        "0.50-0.75": 0,
        ">0.75": 0,
    }
    for value in values:
        if value <= 0.25:
            buckets["<=0.25"] += 1
        elif value <= 0.50:
            buckets["0.25-0.50"] += 1
        elif value <= 0.75:
            buckets["0.50-0.75"] += 1
        else:
            buckets[">0.75"] += 1
    return buckets


def summarize(eval_name: str) -> dict[str, Any]:
    rows = _read_episodes(eval_name)
    summary = _read_summary(eval_name)
    outcomes = Counter(row.get("outcome", "n/a") for row in rows)
    ends = Counter(row.get("end_condition", "n/a") for row in rows)
    draw_health = _target_health(rows, "draw")
    all_health = _target_health(rows)
    return {
        "eval": eval_name,
        "episodes": len(rows),
        "seed": summary.get("seed"),
        "outcomes": dict(outcomes),
        "end_conditions": dict(ends),
        "win_rate": outcomes.get("win", 0) / max(len(rows), 1),
        "loss_rate": outcomes.get("loss", 0) / max(len(rows), 1),
        "draw_rate": outcomes.get("draw", 0) / max(len(rows), 1),
        "draw_target_health_mean": mean(draw_health) if draw_health else None,
        "draw_target_health_min": min(draw_health) if draw_health else None,
        "draw_target_health_buckets": _bucket_health(draw_health),
        "all_target_health_buckets": _bucket_health(all_health),
    }


def compare(base_eval: str, candidate_eval: str) -> dict[str, Any]:
    base = _read_episodes(base_eval)
    cand = _read_episodes(candidate_eval)
    if len(base) != len(cand):
        raise ValueError("evals must have the same episode count for comparison")

    transitions: Counter[str] = Counter()
    changed: list[dict[str, Any]] = []
    for idx, (left, right) in enumerate(zip(base, cand)):
        left_out = left.get("outcome", "n/a")
        right_out = right.get("outcome", "n/a")
        key = f"{left_out}->{right_out}"
        transitions[key] += 1
        if left_out != right_out or left.get("end_condition") != right.get("end_condition"):
            changed.append(
                {
                    "episode": idx,
                    "base_outcome": left_out,
                    "base_end": left.get("end_condition"),
                    "base_target_health": _float(left.get("target_health")),
                    "candidate_outcome": right_out,
                    "candidate_end": right.get("end_condition"),
                    "candidate_target_health": _float(right.get("target_health")),
                }
            )

    return {
        "base": base_eval,
        "candidate": candidate_eval,
        "transitions": dict(transitions),
        "changed": changed,
    }


def _print_summary(data: dict[str, Any]) -> None:
    print(f"[eval] {data['eval']}")
    print(
        "  rates: "
        f"win={data['win_rate']:.0%} "
        f"loss={data['loss_rate']:.0%} "
        f"draw={data['draw_rate']:.0%}"
    )
    print(f"  outcomes: {json.dumps(data['outcomes'], sort_keys=True)}")
    print(f"  end_conditions: {json.dumps(data['end_conditions'], sort_keys=True)}")
    print(f"  draw_health_mean: {_fmt(data['draw_target_health_mean'])}")
    print(f"  draw_health_min: {_fmt(data['draw_target_health_min'])}")
    print(f"  draw_health_buckets: {json.dumps(data['draw_target_health_buckets'], sort_keys=True)}")


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize and compare eval episode CSVs.")
    parser.add_argument("eval", nargs="+", help="Eval folder name under artifacts/eval or a path.")
    parser.add_argument("--compare", action="store_true", help="Compare the first two evals episode-by-episode.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.compare:
        if len(args.eval) != 2:
            raise SystemExit("--compare requires exactly two eval names")
        data = {
            "summaries": [summarize(args.eval[0]), summarize(args.eval[1])],
            "comparison": compare(args.eval[0], args.eval[1]),
        }
    else:
        data = {"summaries": [summarize(name) for name in args.eval]}

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    for item in data["summaries"]:
        _print_summary(item)
    if "comparison" in data:
        cmp = data["comparison"]
        print(f"[compare] {cmp['base']} -> {cmp['candidate']}")
        print(f"  transitions: {json.dumps(cmp['transitions'], sort_keys=True)}")
        print(f"  changed_episodes: {len(cmp['changed'])}")
        for row in cmp["changed"][:20]:
            print(
                "  ep={episode}: {base_outcome}/{base_end}/hp={base_target_health:.3f} "
                "-> {candidate_outcome}/{candidate_end}/hp={candidate_target_health:.3f}".format(
                    **row
                )
            )


if __name__ == "__main__":
    main()
