from __future__ import annotations

import argparse
import csv
import json
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _values(rows: list[dict[str, str]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _float(row.get(key))
        if value is not None:
            values.append(value)
    return values


def _last(row_values: list[float]) -> float | None:
    return row_values[-1] if row_values else None


def _avg(row_values: list[float]) -> float | None:
    return mean(row_values) if row_values else None


def _tail(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    return rows[-count:] if len(rows) > count else rows


def _trend(rows: list[dict[str, str]], key: str, window: int) -> dict[str, float | None]:
    values = _values(rows, key)
    if not values:
        return {"first": None, "last": None, "delta": None}
    first_slice = values[:window] if len(values) >= window else values
    last_slice = values[-window:] if len(values) >= window else values
    first = mean(first_slice)
    last = mean(last_slice)
    return {"first": first, "last": last, "delta": last - first}


def _health_stats(rows: list[dict[str, str]]) -> dict[str, float | None]:
    target = _values(rows, "target_health")
    ownship = _values(rows, "ownship_health")
    return {
        "target_health_min": min(target) if target else None,
        "target_health_last": _last(target),
        "ownship_health_min": min(ownship) if ownship else None,
        "ownship_health_last": _last(ownship),
    }


def _load_inputs(tag: str, output_name: str) -> tuple[Path, Path, list[dict[str, str]], list[dict[str, str]]]:
    log_dir = ROOT / "artifacts" / "logs" / output_name / tag
    training_log = log_dir / "training_log.csv"
    replay_index = log_dir / "engagement_replays" / "replay_index.csv"
    return log_dir, replay_index, _read_csv(training_log), _read_csv(replay_index)


def analyze(tag: str, output_name: str, tail_count: int) -> dict[str, Any]:
    log_dir, replay_index_path, training_rows, replay_rows = _load_inputs(tag, output_name)
    tail_rows = _tail(training_rows, tail_count)

    summary = {
        "tag": tag,
        "output_name": output_name,
        "log_dir": str(log_dir),
        "training_rows": len(training_rows),
        "replay_rows": len(replay_rows),
        "latest": {
            "iter": _last(_values(training_rows, "iter")),
            "reward_mean": _last(_values(training_rows, "reward_mean")),
            "win_rate": _last(_values(training_rows, "win_rate")),
            "loss_rate": _last(_values(training_rows, "loss_rate")),
            "crash_rate": _last(_values(training_rows, "crash_rate")),
            "ep_wez_steps": _last(_values(training_rows, "ep_wez_steps")),
            "ep_min_distance": _last(_values(training_rows, "ep_min_distance")),
            "ep_altitude_penalty_steps": _last(
                _values(training_rows, "ep_altitude_penalty_steps")
            ),
            "final_ata_deg": _last(_values(training_rows, "final_ata_deg")),
            "final_aa_deg": _last(_values(training_rows, "final_aa_deg")),
            "actor_loss": _last(_values(training_rows, "actor_loss")),
            "critic_loss": _last(_values(training_rows, "critic_loss")),
            "alpha": _last(_values(training_rows, "alpha")),
        },
        "tail_avg": {
            "reward_mean": _avg(_values(tail_rows, "reward_mean")),
            "win_rate": _avg(_values(tail_rows, "win_rate")),
            "loss_rate": _avg(_values(tail_rows, "loss_rate")),
            "crash_rate": _avg(_values(tail_rows, "crash_rate")),
            "ep_wez_steps": _avg(_values(tail_rows, "ep_wez_steps")),
            "ep_min_distance": _avg(_values(tail_rows, "ep_min_distance")),
            "ep_altitude_penalty_steps": _avg(
                _values(tail_rows, "ep_altitude_penalty_steps")
            ),
            "final_ata_deg": _avg(_values(tail_rows, "final_ata_deg")),
        },
        "trend": {
            "reward_mean": _trend(training_rows, "reward_mean", tail_count),
            "ep_wez_steps": _trend(training_rows, "ep_wez_steps", tail_count),
            "crash_rate": _trend(training_rows, "crash_rate", tail_count),
            "ep_altitude_penalty_steps": _trend(
                training_rows, "ep_altitude_penalty_steps", tail_count
            ),
        },
        "replay": {
            "index": str(replay_index_path),
            "health": _health_stats(replay_rows),
            "outcomes": _count_by(replay_rows, "outcome"),
            "end_conditions": _count_by(replay_rows, "end_condition"),
        },
    }
    summary["diagnosis"] = _diagnose(summary)
    return summary


def _count_by(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key) or "n/a"
        counts[value] = counts.get(value, 0) + 1
    return counts


def _diagnose(summary: dict[str, Any]) -> list[str]:
    latest = summary["latest"]
    tail = summary["tail_avg"]
    notes: list[str] = []

    crash_rate = tail.get("crash_rate")
    alt_penalty = tail.get("ep_altitude_penalty_steps")
    wez_steps = tail.get("ep_wez_steps")
    win_rate = tail.get("win_rate")
    reward = summary["trend"]["reward_mean"]["delta"]
    min_dist = tail.get("ep_min_distance")
    final_ata = tail.get("final_ata_deg")

    if crash_rate is not None and crash_rate > 0.05:
        notes.append("Stage 1 failed: crash_rate is still too high.")
    elif alt_penalty is not None and alt_penalty > 1.0:
        notes.append("Stage 1 warning: altitude penalties are still frequent.")
    else:
        notes.append("Stage 1 signal OK: no obvious crash/altitude failure in recent logs.")

    if min_dist is not None and min_dist < 150.0:
        notes.append("Stage 2 warning: frequent overtake/too-close behavior.")
    if final_ata is not None and final_ata > 60.0:
        notes.append("Stage 2 failed: final ATA remains high; pursuit geometry is not stable.")
    elif wez_steps is not None and wez_steps >= 5.0:
        notes.append("Stage 2 improving: WEZ exposure is becoming measurable.")

    if win_rate is not None and win_rate > 0.0:
        notes.append("Stage 3 success signal: at least some kills are appearing.")
    elif wez_steps is not None and wez_steps < 10.0:
        notes.append("Stage 3 not ready: WEZ hold is too short for reliable health reduction.")

    if reward is not None:
        direction = "improving" if reward > 0 else "not improving"
        notes.append(f"Reward trend over window is {direction}: delta={reward:.3f}.")
    if latest.get("alpha") is not None:
        notes.append(f"SAC alpha latest={latest['alpha']:.4f}.")
    return notes


def write_report(summary: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Tailchase Analysis: {summary['tag']}",
        "",
        "## Latest",
    ]
    for key, value in summary["latest"].items():
        lines.append(f"- {key}: {_fmt(value)}")
    lines += ["", "## Recent Average"]
    for key, value in summary["tail_avg"].items():
        lines.append(f"- {key}: {_fmt(value)}")
    lines += ["", "## Replay"]
    for key, value in summary["replay"]["health"].items():
        lines.append(f"- {key}: {_fmt(value)}")
    lines.append(f"- outcomes: {json.dumps(summary['replay']['outcomes'], ensure_ascii=False)}")
    lines.append(
        f"- end_conditions: {json.dumps(summary['replay']['end_conditions'], ensure_ascii=False)}"
    )
    lines += ["", "## Diagnosis"]
    for note in summary["diagnosis"]:
        lines.append(f"- {note}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", help="Run tag under artifacts/logs/<output-name>/<tag>")
    parser.add_argument("--output-name", default="team01")
    parser.add_argument("--tail", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    summary = analyze(args.tag, args.output_name, args.tail)
    if args.report:
        write_report(summary, Path(args.report))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"[analysis] tag={summary['tag']} rows={summary['training_rows']}")
        for note in summary["diagnosis"]:
            print(f"- {note}")
        if args.report:
            print(f"[analysis] report saved to {args.report}")


if __name__ == "__main__":
    main()
