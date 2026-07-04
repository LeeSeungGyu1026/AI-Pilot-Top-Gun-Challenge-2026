"""Multi-episode local evaluation: RL bundle vs BT (or any backend pair).

Runs N local engagements with the same backend wiring as
``run_local_dogfight.py`` and aggregates win/loss/draw rates, end
conditions, rewards, and episode lengths. Results are saved under
``artifacts/eval/<eval-name>/`` as ``summary.json`` + ``episodes.csv``.

Usage (from the Release root):

    python scripts\\run_eval.py ^
      --ownship-bundle-dir artifacts\\models\\team01\\sac_mlp_v1 ^
      --episodes 20 --eval-name sac_mlp_v1_vs_bt

Custom observation policies need the same flags as training:

    python scripts\\run_eval.py --ownship-bundle-dir <dir> --episodes 20 ^
      --observation-mode custom --observation-module student.my_observation
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from DogFightEnvWrapper import DogFightWrapper
from dogfight.ai.bt_action_provider import BTActionProvider
from dogfight.ai.bt_rule_manager import activate_rule_xml
from dogfight.ai.hybrid_action_provider import HybridActionProvider
from dogfight.ai.rllib_utils import build_algorithm_from_bundle
from dogfight.ai.rl_action_provider import RLActionProvider
from dogfight.ai.student_hooks import load_observation_hook


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate N local dogfight evaluations.")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--eval-name", default=None, help="Output folder name under artifacts/eval/.")
    parser.add_argument("--ownship-backend", choices=["rl", "bt", "hybrid"], default="rl")
    parser.add_argument(
        "--target-backend",
        choices=["rl", "bt", "hybrid", "fixed", "loiter", "autopilot"],
        default="bt",
        help=(
            "Opponent type. rl/bt/hybrid use action providers; "
            "fixed/loiter/autopilot are driven by the environment itself "
            "(same as the corresponding training target_mode) — useful as an "
            "eval ladder: fixed -> loiter -> autopilot -> bt -> rl checkpoints."
        ),
    )
    parser.add_argument("--ownship-bundle-dir")
    parser.add_argument("--target-bundle-dir")
    parser.add_argument("--ownship-bt-dll", default="AIP_BASE.dll")
    parser.add_argument("--target-bt-dll", default="AIP_BASE_target.dll")
    parser.add_argument("--bt-rule-xml", default=None)
    parser.add_argument(
        "--observation-mode",
        default="tactical16",
        choices=["classic12", "relative14", "tactical16", "custom"],
    )
    parser.add_argument("--observation-module", default="")
    parser.add_argument("--hybrid-mode", choices=["residual", "blend", "switch"], default="residual")
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--residual-scale", type=float, default=0.35)
    parser.add_argument("--max-engage-time", type=float, default=300.0)
    parser.add_argument("--episode-step-limit", type=int, default=18000)
    parser.add_argument("--min-altitude", type=float, default=300.0)
    parser.add_argument(
        "--experiment-yaml",
        default=None,
        help=(
            "Optional experiment YAML. Its env_config geometry/target keys "
            "(offensive_saddle, initial_scenario, target_autopilot, target_loiter, "
            "wez, step_ratio, observation_size) are merged in so evaluation MIRRORS "
            "the training distribution WITH per-episode randomization. Without this, "
            "the eval spawns at a single fixed geometry and every episode is identical."
        ),
    )
    return parser.parse_args()


# env_config keys pulled from --experiment-yaml so eval matches the training stage.
# target_weave IS merged so eval tests the SAME (maneuvering) opponent as training — without
# it, eval ran vs a straight target and gave misleading numbers. range_discipline is
# deliberately EXCLUDED: it's a training-only shaping crutch; eval must measure natural win/loss.
_EVAL_ENV_CONFIG_KEYS = (
    "offensive_saddle", "initial_scenario", "target_autopilot", "target_loiter",
    "target_weave", "wez", "step_ratio", "observation_size", "action_slew_limit",
)


def _load_experiment_env_config(path: str) -> dict:
    import yaml
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    ec = data.get("env_config", {}) or {}
    return {k: ec[k] for k in _EVAL_ENV_CONFIG_KEYS if k in ec}


def build_provider(side: str, backend: str, args: argparse.Namespace):
    bundle_dir = getattr(args, f"{side}_bundle_dir")
    bt_dll = getattr(args, f"{side}_bt_dll")
    if backend in ("fixed", "loiter", "autopilot"):
        return None  # environment-driven target, no action provider
    if backend == "bt":
        return BTActionProvider(dll_name=bt_dll)
    if backend == "rl":
        if not bundle_dir:
            raise SystemExit(f"--{side}-bundle-dir is required when {side}-backend=rl")
        return RLActionProvider(
            bundle_dir=bundle_dir,
            algorithm_factory=build_algorithm_from_bundle,
        )
    if backend == "hybrid":
        if not bundle_dir:
            raise SystemExit(f"--{side}-bundle-dir is required when {side}-backend=hybrid")
        return HybridActionProvider(
            primary_provider=RLActionProvider(
                bundle_dir=bundle_dir,
                algorithm_factory=build_algorithm_from_bundle,
            ),
            secondary_provider=BTActionProvider(dll_name=bt_dll),
            mode=args.hybrid_mode,
            alpha=args.alpha,
            residual_scale=args.residual_scale,
        )
    raise SystemExit(f"Unsupported backend: {backend}")


def classify(info: dict) -> str:
    """Competition-aligned outcome.

    Forcing the opponent into the ground while surviving counts as a WIN (not a
    draw) per the competition rules — the platform's own classifier scores it as
    a draw, which undercounts true performance, so we correct it here.
    """
    own_hp = float(info.get("ownship_health", 0.0) or 0.0)
    tgt_hp = float(info.get("target_health", 0.0) or 0.0)
    end = str(info.get("end_condition", ""))
    if tgt_hp <= 0.0 < own_hp:
        return "win"
    if end == "target altitude below min" and own_hp > 0.0:
        return "win"
    if own_hp <= 0.0 < tgt_hp:
        return "loss"
    if end in ("ownship altitude below min", "FDM Update Fail") and tgt_hp > 0.0:
        return "loss"
    return "draw"


def main() -> int:
    args = parse_args()
    eval_name = args.eval_name or f"eval_{datetime.now():%y%m%d_%H%M%S}"
    out_dir = ROOT / "artifacts" / "eval" / eval_name
    out_dir.mkdir(parents=True, exist_ok=True)

    observation_hook = (
        load_observation_hook(args.observation_module) if args.observation_module else None
    )
    ownship_provider = build_provider("ownship", args.ownship_backend, args)
    target_provider = build_provider("target", args.target_backend, args)

    eval_env_config = {
        "observation_mode": observation_hook["mode"] if observation_hook else args.observation_mode,
        "observation_module": args.observation_module,
        "ownship_control_mode": "rl",
        # provider-driven opponents use env mode "rl"; fixed/loiter/
        # autopilot are simulated by the env exactly as in training
        "target_mode": (
            args.target_backend
            if args.target_backend in ("fixed", "loiter", "autopilot")
            else "rl"
        ),
        "max_engage_time": args.max_engage_time,
        "episode_step_limit": args.episode_step_limit,
        "min_altitude": args.min_altitude,
    }
    if args.experiment_yaml:
        merged = _load_experiment_env_config(args.experiment_yaml)
        eval_env_config.update(merged)
        print(f"[eval] merged training geometry from {args.experiment_yaml}: {sorted(merged)}")

    episodes: list[dict] = []
    with activate_rule_xml(args.bt_rule_xml, ROOT):
        env = DogFightWrapper(
            env_config=eval_env_config,
            observation_fn=observation_hook["build_observation"] if observation_hook else None,
            observation_size=observation_hook["size"] if observation_hook else None,
            observation_low=observation_hook["low"] if observation_hook else None,
            observation_high=observation_hook["high"] if observation_hook else None,
            ownship_action_provider=ownship_provider,
            target_action_provider=target_provider,
        )
        try:
            for ep in range(args.episodes):
                start = time.time()
                _, info = env.reset()
                terminated = truncated = False
                total_reward = 0.0
                steps = 0
                while not (terminated or truncated):
                    _, reward, terminated, truncated, info = env.step(
                        np.zeros(4, dtype=np.float32)
                    )
                    total_reward += reward
                    steps += 1
                record = {
                    "episode": ep,
                    "outcome": classify(info),
                    "end_condition": info.get("end_condition", ""),
                    "steps": steps,
                    "total_reward": round(total_reward, 4),
                    "ownship_health": info.get("ownship_health"),
                    "target_health": info.get("target_health"),
                    "wall_time_s": round(time.time() - start, 1),
                }
                episodes.append(record)
                print(
                    f"[ep {ep + 1}/{args.episodes}] {record['outcome']:5s} "
                    f"end={record['end_condition']} steps={steps} reward={total_reward:.2f}"
                )
        finally:
            env.close()

    outcomes = Counter(e["outcome"] for e in episodes)
    n = max(len(episodes), 1)
    summary = {
        "eval_name": eval_name,
        "created": datetime.now().isoformat(timespec="seconds"),
        "episodes": len(episodes),
        "ownship": {
            "backend": args.ownship_backend,
            "bundle_dir": args.ownship_bundle_dir,
        },
        "target": {
            "backend": args.target_backend,
            "bundle_dir": args.target_bundle_dir,
            "bt_dll": args.target_bt_dll,
        },
        "observation_mode": args.observation_mode,
        "observation_module": args.observation_module,
        "win_rate": outcomes["win"] / n,
        "loss_rate": outcomes["loss"] / n,
        "draw_rate": outcomes["draw"] / n,
        "end_conditions": dict(Counter(e["end_condition"] for e in episodes)),
        "mean_reward": float(np.mean([e["total_reward"] for e in episodes])) if episodes else 0.0,
        "mean_steps": float(np.mean([e["steps"] for e in episodes])) if episodes else 0.0,
    }

    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (out_dir / "episodes.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(episodes[0].keys()) if episodes else [])
        writer.writeheader()
        writer.writerows(episodes)

    print()
    print(f"[summary] win {summary['win_rate']:.0%} / loss {summary['loss_rate']:.0%} / draw {summary['draw_rate']:.0%}")
    print(f"[end]     {summary['end_conditions']}")
    print(f"[saved]   {out_dir.relative_to(ROOT)}\\summary.json, episodes.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
