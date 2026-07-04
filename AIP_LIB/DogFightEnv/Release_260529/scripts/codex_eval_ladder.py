from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_TAG = "codex_ic_s3_validation_ladder_v1"
OUT_DIR = ROOT / "artifacts" / "eval" / RUN_TAG


CASES = [
    {
        "name": "codex_ic_s3_bt_nomirror_eval_v1",
        "episodes": 30,
        "target": "bt",
        "experiment_yaml": None,
        "purpose": "Reproduce the non-mirrored BT geometry mismatch under a Codex-owned name.",
    },
    {
        "name": "codex_ic_s3_bt_mirror_long_eval_v1",
        "episodes": 50,
        "target": "bt",
        "experiment_yaml": "experiments/ic_s3_bt.yaml",
        "purpose": "Longer mirrored BT check for stability of target-grounding wins.",
    },
    {
        "name": "codex_ic_s3_autopilot_eval_v1",
        "episodes": 20,
        "target": "autopilot",
        "experiment_yaml": "experiments/ic_s3_bt.yaml",
        "purpose": "Check whether the policy still handles the easier autopilot target on the same initial geometry.",
    },
    {
        "name": "codex_ic_s3_loiter_eval_v1",
        "episodes": 20,
        "target": "loiter",
        "experiment_yaml": "experiments/ic_s3_bt.yaml",
        "purpose": "Check whether the policy avoids collapsing on a non-BT target mode.",
    },
]


def run_case(case: dict) -> dict:
    args = [
        sys.executable,
        "scripts/codex_run_eval.py",
        "--ownship-bundle-dir",
        "artifacts/models/team01/ic_s3_bt_v1",
        "--episodes",
        str(case["episodes"]),
        "--target-backend",
        case["target"],
        "--observation-mode",
        "custom",
        "--observation-module",
        "student.my_observation",
        "--eval-name",
        case["name"],
    ]
    if case["experiment_yaml"]:
        args += ["--experiment-yaml", case["experiment_yaml"]]

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
        "- Mirrored BT long eval win rate >= 0.90.",
        "- No validation slice loss/crash rate above 0.05.",
        "- Non-mirrored BT remains materially different from mirrored BT, confirming geometry sensitivity.",
        "- If wins remain target-grounding only, mark the candidate as scoring-sensitive before promotion.",
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
