from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_TAG = "codex_ic_s4_loiter_guard_validation_v1"
BUNDLE = "artifacts/models/team01/codex_ic_s4_loiter_guard_v1"
EXPERIMENT_YAML = "experiments/codex_ic_s4_loiter_guard_v1.yaml"
OUT_DIR = ROOT / "artifacts" / "eval" / RUN_TAG


CASES = [
    {
        "name": "codex_ic_s4_loiter_guard_bt_eval_v1",
        "episodes": 30,
        "target": "bt",
        "purpose": "Check whether BT performance survived the loiter fine-tune.",
    },
    {
        "name": "codex_ic_s4_loiter_guard_autopilot_eval_v1",
        "episodes": 20,
        "target": "autopilot",
        "purpose": "Check whether autopilot ownship-altitude losses improved.",
    },
    {
        "name": "codex_ic_s4_loiter_guard_loiter_eval_v1",
        "episodes": 30,
        "target": "loiter",
        "purpose": "Quantify whether the loiter draw/loss collapse improved.",
    },
]


def run_case(case: dict) -> dict:
    args = [
        sys.executable,
        "scripts/codex_run_eval.py",
        "--ownship-bundle-dir",
        BUNDLE,
        "--episodes",
        str(case["episodes"]),
        "--target-backend",
        case["target"],
        "--observation-mode",
        "custom",
        "--observation-module",
        "student.my_observation",
        "--experiment-yaml",
        EXPERIMENT_YAML,
        "--eval-name",
        case["name"],
    ]

    stdout_path = OUT_DIR / f"codex_ladder_{case['name']}_stdout.log"
    stderr_path = OUT_DIR / f"codex_ladder_{case['name']}_stderr.log"
    started = datetime.now().isoformat(timespec="seconds")
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(args, cwd=ROOT, stdout=stdout, stderr=stderr, text=True)
    ended = datetime.now().isoformat(timespec="seconds")

    summary_path = ROOT / "artifacts" / "eval" / case["name"] / "codex_summary.json"
    episodes_path = ROOT / "artifacts" / "eval" / case["name"] / "codex_episodes.csv"
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    end_counts = {}
    if episodes_path.exists():
        with episodes_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = row.get("end_condition", "")
                end_counts[key] = end_counts.get(key, 0) + 1

    return {
        "case": case,
        "started": started,
        "ended": ended,
        "returncode": proc.returncode,
        "stdout": str(stdout_path.relative_to(ROOT)),
        "stderr": str(stderr_path.relative_to(ROOT)),
        "summary_path": str(summary_path.relative_to(ROOT)),
        "episodes_path": str(episodes_path.relative_to(ROOT)),
        "summary": summary,
        "episode_end_counts": end_counts,
    }


def write_summary(results: list[dict]) -> None:
    lines = [
        f"# Codex Eval Ladder Summary: {RUN_TAG}",
        "",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "| Case | Return | Win | Loss | Draw | Mean reward | Mean steps | End conditions |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for result in results:
        summary = result.get("summary") or {}
        end_conditions = summary.get("end_conditions") or result.get("episode_end_counts") or {}
        lines.append(
            "| {case} | {ret} | {win} | {loss} | {draw} | {reward} | {steps} | {ends} |".format(
                case=result["case"]["name"],
                ret=result["returncode"],
                win=summary.get("win_rate", "n/a"),
                loss=summary.get("loss_rate", "n/a"),
                draw=summary.get("draw_rate", "n/a"),
                reward=summary.get("mean_reward", "n/a"),
                steps=summary.get("mean_steps", "n/a"),
                ends=json.dumps(end_conditions, sort_keys=True),
            )
        )
    lines += [
        "",
        "Gate targets:",
        "",
        "- BT win rate >= 0.90.",
        "- Autopilot win rate >= 0.90 and loss/crash rate <= 0.05.",
        "- Loiter win rate >= 0.60, draw rate <= 0.30, and loss/crash rate <= 0.05.",
        "- If gates pass, freeze as PPO stabilization candidate before considering SAC.",
        "",
    ]
    (OUT_DIR / "codex_ladder_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / "codex_ladder_manifest.json"
    results: list[dict] = []
    for case in CASES:
        result = run_case(case)
        results.append(result)
        manifest_path.write_text(
            json.dumps(
                {
                    "run_tag": RUN_TAG,
                    "bundle": BUNDLE,
                    "experiment_yaml": EXPERIMENT_YAML,
                    "updated": datetime.now().isoformat(timespec="seconds"),
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        write_summary(results)
        if result["returncode"] != 0:
            return result["returncode"]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
