"""Parallel experiment launcher for DogFightEnv.

Reads a sweep YAML that references a base experiment YAML, expands a
parameter grid (plus optional repeats), writes one generated experiment
YAML per variant, and runs them through ``scripts/run_experiment.py``
with a bounded number of concurrent processes.

Each variant gets a unique ``output.tag``, so artifacts (logs, models,
checkpoints, dashboard) never collide between runs.

Usage (from the Release root):

    python scripts\\run_parallel.py experiments\\sweeps\\example_sac_sweep.yaml --dry-run
    python scripts\\run_parallel.py experiments\\sweeps\\example_sac_sweep.yaml

Sweep YAML schema:

    name: lr_sweep                          # sweep name (tag prefix)
    base: experiments/student_sac_mlp.yaml  # base experiment, relative to Release root
    max_parallel: 2                         # concurrent training processes
    repeats: 1                              # runs per variant (stochastic seeds)
    overrides:                              # applied to every variant (nested or dotted)
      runtime.iterations: 50
    grid:                                   # cartesian product, dotted keys
      algo.lr: [3.0e-4, 1.0e-3]
      algo.mlp.fcnet_hiddens: [[256, 256], [512, 512]]

NOTE: do not run ``ray stop --force`` while a sweep is active — it kills
the Ray sessions of *all* running training processes on this machine.
"""

from __future__ import annotations

import argparse
import copy
import functools
import itertools
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUN_EXPERIMENT = ROOT / "scripts" / "run_experiment.py"

# Subprocesses write straight to the console; flush so parent output interleaves in order.
print = functools.partial(print, flush=True)


class SweepError(ValueError):
    """Raised when a sweep YAML is invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SweepError(f"YAML not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SweepError(f"YAML root must be a mapping: {path}")
    return data


def set_by_path(cfg: dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a nested value using a dotted key like ``algo.mlp.fcnet_hiddens``."""
    keys = dotted_key.split(".")
    node = cfg
    for key in keys[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[keys[-1]] = value


def apply_overrides(cfg: dict[str, Any], overrides: dict[str, Any], prefix: str = "") -> None:
    """Apply overrides; keys may be dotted, values may be nested mappings."""
    for key, value in overrides.items():
        full_key = f"{prefix}{key}"
        if isinstance(value, dict):
            apply_overrides(cfg, value, prefix=f"{full_key}.")
        else:
            set_by_path(cfg, full_key, value)


def value_label(value: Any) -> str:
    """Short, filesystem-safe label for one parameter value."""
    if isinstance(value, (list, tuple)):
        text = "x".join(str(item) for item in value)
    elif isinstance(value, float):
        text = f"{value:g}"
    else:
        text = str(value)
    return re.sub(r"[^A-Za-z0-9_.\-]+", "-", text)


def build_variants(sweep: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand grid x repeats into [{label, params}] entries."""
    grid = sweep.get("grid") or {}
    if not isinstance(grid, dict):
        raise SweepError("grid must be a mapping of dotted keys to value lists")
    repeats = int(sweep.get("repeats", 1))
    if repeats < 1:
        raise SweepError("repeats must be >= 1")

    keys = list(grid.keys())
    value_lists = []
    for key in keys:
        values = grid[key]
        if not isinstance(values, list) or not values:
            raise SweepError(f"grid.{key} must be a non-empty list")
        value_lists.append(values)

    combos = list(itertools.product(*value_lists)) if keys else [()]
    variants = []
    for combo in combos:
        params = dict(zip(keys, combo))
        parts = [f"{key.split('.')[-1]}-{value_label(value)}" for key, value in params.items()]
        for rep in range(repeats):
            label_parts = list(parts)
            if repeats > 1:
                label_parts.append(f"r{rep}")
            label = "_".join(label_parts) if label_parts else f"run{rep}"
            variants.append({"label": label, "params": params})
    return variants


def generate_experiment_yaml(
    base_cfg: dict[str, Any],
    sweep_name: str,
    variant: dict[str, Any],
    overrides: dict[str, Any],
    out_dir: Path,
) -> tuple[Path, str]:
    cfg = copy.deepcopy(base_cfg)
    apply_overrides(cfg, overrides)
    apply_overrides(cfg, variant["params"])

    tag = f"{sweep_name}_{variant['label']}"
    cfg.setdefault("output", {})
    cfg["output"]["tag"] = tag
    cfg["name"] = f"{cfg.get('name', 'experiment')}_{tag}"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{tag}.yaml"
    out_path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return out_path, tag


def _tail_progress_line(log_path: Path) -> str | None:
    """Return the most recent training-progress line from a run log."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for line in reversed(text.splitlines()):
        # train_rllib lines start with "iter=[", train_curriculum with "stage=["
        if line.startswith(("iter=[", "stage=[")) or "Traceback" in line:
            return line.strip()
    return None


def _prepare_curriculum_state(run: dict[str, Any]) -> None:
    """Archive stale curriculum state so a relaunch never trips the platform's
    'State file exists' latch (train_curriculum refuses to overwrite without
    --resume). The old directory is renamed, not deleted."""
    if run.get("script") != "train_curriculum" or run.get("resume"):
        return
    state_dir = ROOT / "artifacts" / "curriculum" / str(run["output_name"]) / run["tag"]
    if not (state_dir / "curriculum_state.json").exists():
        return
    archived = state_dir.with_name(
        f"{state_dir.name}__stale_{datetime.now():%m%d_%H%M%S}"
    )
    state_dir.rename(archived)
    print(f"[archive]  stale curriculum state moved: {archived.relative_to(ROOT)}")


def _kill_tree(proc: subprocess.Popen) -> None:
    """Terminate a run and all of its children (train_rllib + Ray workers)."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
        )
    else:
        proc.terminate()


def run_sweep(args: argparse.Namespace) -> int:
    sweep_path = Path(args.sweep_yaml)
    if not sweep_path.is_absolute():
        sweep_path = (Path.cwd() / sweep_path).resolve()
    sweep = load_yaml(sweep_path)

    sweep_name = str(sweep.get("name") or sweep_path.stem)
    base_rel = sweep.get("base")
    if not base_rel:
        raise SweepError("sweep YAML requires a 'base' experiment path")
    base_path = (ROOT / str(base_rel)).resolve()
    base_cfg = load_yaml(base_path)

    overrides = sweep.get("overrides") or {}
    if not isinstance(overrides, dict):
        raise SweepError("overrides must be a mapping")
    max_parallel = int(args.max_parallel or sweep.get("max_parallel", 2))
    if max_parallel < 1:
        raise SweepError("max_parallel must be >= 1")

    variants = build_variants(sweep)
    generated_dir = ROOT / "experiments" / "generated" / sweep_name
    sweep_out_dir = ROOT / "artifacts" / "sweeps" / sweep_name
    sweep_out_dir.mkdir(parents=True, exist_ok=True)

    runs = []
    for variant in variants:
        yaml_path, tag = generate_experiment_yaml(
            base_cfg, sweep_name, variant, overrides, generated_dir
        )
        runs.append(
            {
                "tag": tag,
                "params": variant["params"],
                "script": str(base_cfg.get("script", "train_rllib")),
                "output_name": str(base_cfg.get("output", {}).get("name", "")),
                "resume": bool(base_cfg.get("runtime", {}).get("resume", False)),
                "experiment_yaml": str(yaml_path.relative_to(ROOT)),
                "log_file": str((sweep_out_dir / f"{tag}.log").relative_to(ROOT)),
                "status": "pending",
                "returncode": None,
            }
        )

    output_name = base_cfg.get("output", {}).get("name", "?")
    print(f"[sweep]    {sweep_name}: {len(runs)} run(s), max_parallel={max_parallel}")
    print(f"[base]     {base_rel} (output.name={output_name})")
    for run in runs:
        print(f"  - {run['tag']}  params={run['params'] or '(repeat only)'}")
    print(f"[yaml]     experiments/generated/{sweep_name}/")
    print(f"[logs]     artifacts/sweeps/{sweep_name}/")
    print(f"[models]   artifacts/models/{output_name}/<tag>/")

    if args.dry_run:
        for run in runs:
            cmd = [sys.executable, str(RUN_EXPERIMENT), str(ROOT / run["experiment_yaml"]), "--dry-run"]
            subprocess.run(cmd, cwd=ROOT)
        print("[dry-run] no training started.")
        return 0

    manifest_path = sweep_out_dir / "manifest.json"

    def write_manifest() -> None:
        manifest_path.write_text(
            json.dumps(
                {
                    "sweep": sweep_name,
                    "sweep_yaml": str(sweep_path),
                    "base": str(base_rel),
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "max_parallel": max_parallel,
                    "runs": runs,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    pending = list(runs)
    active: list[tuple[dict[str, Any], subprocess.Popen, Any]] = []
    write_manifest()
    print(
        "[hint]     run output goes to the log files (console stays quiet); "
        "progress is echoed below every ~60s."
    )

    heartbeat_interval = 60.0
    last_heartbeat = time.monotonic()
    last_progress: dict[str, str] = {}

    try:
        while pending or active:
            while pending and len(active) < max_parallel:
                run = pending.pop(0)
                _prepare_curriculum_state(run)
                log_handle = (ROOT / run["log_file"]).open("w", encoding="utf-8")
                proc = subprocess.Popen(
                    [sys.executable, str(RUN_EXPERIMENT), str(ROOT / run["experiment_yaml"])],
                    cwd=ROOT,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                )
                run["status"] = "running"
                active.append((run, proc, log_handle))
                print(f"[start]    {run['tag']} (pid={proc.pid})")
                write_manifest()

            time.sleep(2.0)
            still_active = []
            for run, proc, log_handle in active:
                code = proc.poll()
                if code is None:
                    still_active.append((run, proc, log_handle))
                    continue
                log_handle.close()
                run["returncode"] = code
                run["status"] = "ok" if code == 0 else "failed"
                print(f"[done]     {run['tag']} -> {run['status']} (exit={code})")
                write_manifest()
            active = still_active

            if active and time.monotonic() - last_heartbeat >= heartbeat_interval:
                last_heartbeat = time.monotonic()
                for run, _, _ in active:
                    line = _tail_progress_line(ROOT / run["log_file"])
                    if line and line != last_progress.get(run["tag"]):
                        last_progress[run["tag"]] = line
                        print(f"[progress] {run['tag']}: {line}")
    except KeyboardInterrupt:
        print("[abort]    terminating active runs (and their Ray workers)...")
        for run, proc, log_handle in active:
            _kill_tree(proc)
            run["status"] = "aborted"
            log_handle.close()
        write_manifest()
        return 130

    failed = [run for run in runs if run["status"] != "ok"]
    print(f"[summary]  {len(runs) - len(failed)}/{len(runs)} run(s) succeeded.")
    print(f"[manifest] {manifest_path.relative_to(ROOT)}")
    if failed:
        for run in failed:
            print(f"  FAILED: {run['tag']} (see {run['log_file']})")
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a DogFight experiment sweep in parallel.")
    parser.add_argument("sweep_yaml", help="Path to sweep YAML file.")
    parser.add_argument("--dry-run", action="store_true", help="Generate YAMLs and show commands only.")
    parser.add_argument("--max-parallel", type=int, default=None, help="Override sweep max_parallel.")
    return parser.parse_args()


def main() -> int:
    try:
        return run_sweep(parse_args())
    except SweepError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
