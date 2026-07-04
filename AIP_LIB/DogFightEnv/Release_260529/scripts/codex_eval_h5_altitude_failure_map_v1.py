from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN_TAG = "codex_ic_s5_h5_altitude_failure_map_v1"
BUNDLE = "artifacts/models/team01/codex_freeze_ic_s4_mixed_anchor_guard_v1_20260620_0853"
BASE_EXPERIMENT_YAML = "experiments/codex_ic_s4_mixed_anchor_guard_v1.yaml"
PLAN = "reports/codex_loop_plan_20260620_153223_codex_ic_s5_h5_altitude_failure_map_v1.md"
OUT_DIR = ROOT / "artifacts" / "eval" / RUN_TAG
GENERATED_DIR = ROOT / "experiments" / "codex_generated_ic_s5_h5_altitude_failure_map_v1"


BT_CASES = [
    {
        "target": "bt",
        "scenario_index": idx,
        "episodes": 30,
        "purpose": "Map H5 ownship-altitude failures against BT by legacy scenario index.",
    }
    for idx in range(5)
]
LOITER_CASES = [
    {
        "target": "loiter",
        "scenario_index": idx,
        "episodes": 30,
        "purpose": "Map H5 ownship-altitude failures against loiter by legacy scenario index.",
    }
    for idx in range(8)
]
CONTROL_CASES = [
    {
        "target": "autopilot",
        "scenario_index": None,
        "episodes": 20,
        "purpose": "Sanity-control check using the original H5 mixed geometry.",
    }
]
CASES = BT_CASES + LOITER_CASES + CONTROL_CASES


def _case_name(case: dict) -> str:
    idx = case["scenario_index"]
    suffix = "mixed" if idx is None else f"idx{idx}"
    return f"codex_h5_altitude_map_{case['target']}_{suffix}_v1"


def _write_case_yaml(base_cfg: dict, case: dict) -> str:
    case_name = _case_name(case)
    cfg = deepcopy(base_cfg)
    cfg["name"] = case_name
    cfg.setdefault("output", {})["tag"] = case_name
    cfg.setdefault("env_config", {})
    initial = cfg["env_config"].setdefault("initial_scenario", {})
    if case["scenario_index"] is not None:
        initial["mode"] = "ref_old_random"
        initial["legacy_use_random_scenario"] = True
        initial["legacy_use_first_scenario_only"] = False
        initial["legacy_scenario_indices"] = [int(case["scenario_index"])]
    cfg["notes"] = (
        "codex H7a diagnostic YAML generated for per-scenario altitude-failure map; "
        f"target={case['target']} scenario_index={case['scenario_index']}"
    )

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = GENERATED_DIR / f"codex_{case_name}.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return str(yaml_path.relative_to(ROOT))


def _read_summary_and_counts(case_name: str) -> tuple[dict, dict]:
    summary_path = ROOT / "artifacts" / "eval" / case_name / "codex_summary.json"
    episodes_path = ROOT / "artifacts" / "eval" / case_name / "codex_episodes.csv"
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    end_counts: dict[str, int] = {}
    if episodes_path.exists():
        with episodes_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                end = row.get("end_condition", "")
                end_counts[end] = end_counts.get(end, 0) + 1
    return summary, end_counts


def _summarize_failures(results: list[dict]) -> dict:
    failing_cases = []
    total_ownship_altitude = 0
    total_fdm_fail = 0
    for result in results:
        counts = result.get("episode_end_counts") or {}
        ownship_alt = int(counts.get("ownship altitude below min", 0))
        fdm_fail = int(counts.get("FDM Update Fail", 0))
        total_ownship_altitude += ownship_alt
        total_fdm_fail += fdm_fail
        if ownship_alt or fdm_fail:
            failing_cases.append(
                {
                    "case": result["case"]["name"],
                    "target": result["case"]["target"],
                    "scenario_index": result["case"]["scenario_index"],
                    "ownship_altitude_below_min": ownship_alt,
                    "fdm_update_fail": fdm_fail,
                }
            )
    return {
        "total_ownship_altitude_below_min": total_ownship_altitude,
        "total_fdm_update_fail": total_fdm_fail,
        "failing_cases": failing_cases,
    }


def _write_summary(results: list[dict]) -> None:
    lines = [
        f"# Codex Eval Ladder Summary: {RUN_TAG}",
        "",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "| Case | Target | Scenario | Return | Win | Loss | Draw | Ownship Alt | FDM Fail | Timeouts | Mean Steps |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        case = result["case"]
        summary = result.get("summary") or {}
        counts = result.get("episode_end_counts") or {}
        lines.append(
            "| {case_name} | {target} | {scenario} | {ret} | {win} | {loss} | {draw} | {ownship_alt} | {fdm} | {timeouts} | {steps} |".format(
                case_name=case["name"],
                target=case["target"],
                scenario="mixed" if case["scenario_index"] is None else case["scenario_index"],
                ret=result["returncode"],
                win=summary.get("win_rate", "n/a"),
                loss=summary.get("loss_rate", "n/a"),
                draw=summary.get("draw_rate", "n/a"),
                ownship_alt=counts.get("ownship altitude below min", 0),
                fdm=counts.get("FDM Update Fail", 0),
                timeouts=counts.get("max time out", 0),
                steps=summary.get("mean_steps", "n/a"),
            )
        )

    failures = _summarize_failures(results)
    lines += [
        "",
        "## Failure Totals",
        "",
        f"- ownship altitude below min: {failures['total_ownship_altitude_below_min']}",
        f"- FDM Update Fail: {failures['total_fdm_update_fail']}",
        "",
        "## Decision Hint",
        "",
    ]
    if failures["failing_cases"]:
        lines.append("Failures are currently localized to:")
        lines.append("")
        for item in failures["failing_cases"]:
            lines.append(
                "- {case}: target={target}, scenario={scenario}, ownship_alt={ownship_alt}, fdm={fdm}".format(
                    case=item["case"],
                    target=item["target"],
                    scenario=item["scenario_index"],
                    ownship_alt=item["ownship_altitude_below_min"],
                    fdm=item["fdm_update_fail"],
                )
            )
    else:
        lines.append("No ownship-altitude/FDM failures have appeared yet in completed cases.")
    lines.append("")
    (OUT_DIR / "codex_ladder_summary.md").write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(results: list[dict]) -> None:
    manifest = {
        "run_tag": RUN_TAG,
        "hypothesis": (
            "codex-H7a: ownship-altitude losses in frozen H5 are concentrated "
            "in a small set of target/scenario slices."
        ),
        "plan": PLAN,
        "bundle": BUNDLE,
        "base_experiment_yaml": BASE_EXPERIMENT_YAML,
        "generated_yaml_dir": str(GENERATED_DIR.relative_to(ROOT)),
        "updated": datetime.now().isoformat(timespec="seconds"),
        "failure_summary": _summarize_failures(results),
        "results": results,
    }
    (OUT_DIR / "codex_ladder_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_summary(results)


def _run_case(case: dict) -> dict:
    case_name = _case_name(case)
    case = dict(case)
    case["name"] = case_name
    base_cfg = yaml.safe_load((ROOT / BASE_EXPERIMENT_YAML).read_text(encoding="utf-8")) or {}
    case_yaml = _write_case_yaml(base_cfg, case)

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
        case_yaml,
        "--eval-name",
        case_name,
    ]

    stdout_path = OUT_DIR / f"codex_ladder_{case_name}_stdout.log"
    stderr_path = OUT_DIR / f"codex_ladder_{case_name}_stderr.log"
    started = datetime.now().isoformat(timespec="seconds")
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(args, cwd=ROOT, stdout=stdout, stderr=stderr, text=True)
    ended = datetime.now().isoformat(timespec="seconds")

    summary, end_counts = _read_summary_and_counts(case_name)
    return {
        "case": case,
        "started": started,
        "ended": ended,
        "returncode": proc.returncode,
        "command": args,
        "case_experiment_yaml": case_yaml,
        "stdout": str(stdout_path.relative_to(ROOT)),
        "stderr": str(stderr_path.relative_to(ROOT)),
        "summary_path": str((ROOT / "artifacts" / "eval" / case_name / "codex_summary.json").relative_to(ROOT)),
        "episodes_path": str((ROOT / "artifacts" / "eval" / case_name / "codex_episodes.csv").relative_to(ROOT)),
        "summary": summary,
        "episode_end_counts": end_counts,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "codex_ladder_pid.txt").write_text(str(os.getpid()), encoding="utf-8")

    results: list[dict] = []
    _write_manifest(results)
    for case in CASES:
        result = _run_case(case)
        results.append(result)
        _write_manifest(results)
        if result["returncode"] != 0:
            return int(result["returncode"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
