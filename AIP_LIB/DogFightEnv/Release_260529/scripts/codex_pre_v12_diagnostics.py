"""Pre-v12 diagnostic evaluation for an RL bundle.

This is intentionally evaluation-only: it loads a frozen/lightweight bundle,
runs local dogfight episodes, and writes diagnostics under
artifacts/eval/<eval-name> without touching any training process or model
directory.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import pickle
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from DogFightEnvWrapper import DogFightWrapper  # noqa: E402
from dogfight.ai.bt_action_provider import BTActionProvider  # noqa: E402
from dogfight.ai.bt_rule_manager import activate_rule_xml  # noqa: E402
from dogfight.ai.action_provider import ActionProvider, ActionResult, clip_action  # noqa: E402
from dogfight.ai.rllib_utils import build_algorithm_from_bundle  # noqa: E402
from dogfight.ai.rl_action_provider import RLActionProvider  # noqa: E402
from dogfight.ai.student_hooks import load_observation_hook  # noqa: E402
from dogfight.sim.state_schema import StateIndex  # noqa: E402


_EVAL_ENV_CONFIG_KEYS = (
    "offensive_saddle",
    "initial_scenario",
    "target_autopilot",
    "target_loiter",
    "target_weave",
    "wez",
    "step_ratio",
    "observation_size",
    "action_slew_limit",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-name", required=True)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--ownship-bundle-dir", required=True)
    parser.add_argument(
        "--target-backend",
        choices=["bt", "fixed", "loiter", "autopilot"],
        default="bt",
    )
    parser.add_argument("--target-bt-dll", default="AIP_BASE_target.dll")
    parser.add_argument("--bt-rule-xml", default=None)
    parser.add_argument("--observation-mode", default="custom")
    parser.add_argument("--observation-module", default="student.my_observation")
    parser.add_argument("--experiment-yaml", default=None)
    parser.add_argument("--max-engage-time", type=float, default=180.0)
    parser.add_argument("--episode-step-limit", type=int, default=5400)
    parser.add_argument("--min-altitude", type=float, default=300.0)
    parser.add_argument("--sample-stride", type=int, default=1)
    parser.add_argument("--explore", action="store_true", help="Sample stochastic policy actions instead of deterministic mean actions.")
    parser.add_argument(
        "--numpy-inference",
        action="store_true",
        help="Evaluate PPO MLP lightweight bundles with NumPy only, avoiding torch/Ray imports during action inference.",
    )
    return parser.parse_args()


def _load_experiment_env_config(path: str | None) -> dict:
    if not path:
        return {}
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    env_config = data.get("env_config", {}) or {}
    return {k: env_config[k] for k in _EVAL_ENV_CONFIG_KEYS if k in env_config}


def _build_target_provider(args: argparse.Namespace):
    if args.target_backend == "bt":
        return BTActionProvider(dll_name=args.target_bt_dll)
    return None


class _NumpyPPOBundleActionProvider(ActionProvider):
    """Minimal NumPy forward path for the default PPO MLP lightweight bundle."""

    def __init__(self, bundle_dir: str, explore: bool = False, seed: int = 20260704):
        self.bundle_dir = Path(bundle_dir)
        self.explore = bool(explore)
        self.rng = np.random.default_rng(seed)
        with gzip.open(self.bundle_dir / "policy_weights.pkl.gz", "rb") as fh:
            self.weights = pickle.load(fh)
        required = [
            "encoder.actor_encoder.net.mlp.0.weight",
            "encoder.actor_encoder.net.mlp.0.bias",
            "encoder.actor_encoder.net.mlp.2.weight",
            "encoder.actor_encoder.net.mlp.2.bias",
            "pi.net.mlp.0.weight",
            "pi.net.mlp.0.bias",
        ]
        missing = [key for key in required if key not in self.weights]
        if missing:
            raise ValueError(f"NumPy PPO inference does not support this bundle; missing keys: {missing}")

    def compute_action(self, context) -> ActionResult:
        obs = np.asarray(context.observation, dtype=np.float32)
        w = self.weights
        x = np.tanh(np.asarray(w["encoder.actor_encoder.net.mlp.0.weight"]) @ obs + np.asarray(w["encoder.actor_encoder.net.mlp.0.bias"]))
        x = np.tanh(np.asarray(w["encoder.actor_encoder.net.mlp.2.weight"]) @ x + np.asarray(w["encoder.actor_encoder.net.mlp.2.bias"]))
        logits = np.asarray(w["pi.net.mlp.0.weight"]) @ x + np.asarray(w["pi.net.mlp.0.bias"])
        mean = logits[:4]
        if self.explore:
            log_std = np.clip(logits[4:], -20.0, 20.0)
            action = mean + np.exp(log_std) * self.rng.standard_normal(4)
        else:
            action = mean
        return ActionResult(
            action=clip_action(action),
            source="rl_numpy",
            confidence=0.9,
            info={"explore": self.explore, "bundle_dir": str(self.bundle_dir)},
        )


def _target_mode(args: argparse.Namespace) -> str:
    if args.target_backend in ("fixed", "loiter", "autopilot"):
        return args.target_backend
    return "rl"


def _classify(info: dict) -> str:
    own_hp = float(info.get("ownship_health", 0.0) or 0.0)
    tgt_hp = float(info.get("target_health", 0.0) or 0.0)
    end = str(info.get("end_condition", ""))
    if tgt_hp <= 0.0 < own_hp:
        return "real_win"
    if end == "target altitude below min" and own_hp > 0.0:
        return "forced_ground"
    if own_hp <= 0.0 < tgt_hp or end in ("ownship altitude below min", "FDM Update Fail"):
        return "loss"
    return "draw"


def _safe_mean(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def _safe_min(values: list[float]) -> float:
    return float(min(values)) if values else 0.0


def _safe_max(values: list[float]) -> float:
    return float(max(values)) if values else 0.0


def _step_metrics(env: DogFightWrapper) -> dict[str, float]:
    distance = float(env._geo_info._get_distance(env._ownship_state, env._target_state))
    ata = abs(float(env._geo_info._get_antenna_train_angle(env._ownship_state, env._target_state, True)))
    target_ata = abs(float(env._geo_info._get_antenna_train_angle(env._target_state, env._ownship_state, True)))
    aspect = abs(float(env._geo_info._get_aspect_angle(env._ownship_state, env._target_state, True)))
    own_alt = float(env._ownship_state[StateIndex.ALT])
    target_alt = float(env._target_state[StateIndex.ALT])
    action = np.asarray(env.get_ownship_action(), dtype=np.float64)
    return {
        "distance_m": distance,
        "ata_deg": ata,
        "target_ata_deg": target_ata,
        "aspect_deg": aspect,
        "own_altitude_m": own_alt,
        "target_altitude_m": target_alt,
        "action_roll": float(action[0]),
        "action_pitch": float(action[1]),
        "action_rudder": float(action[2]),
        "action_throttle": float(action[3]),
    }


def _episode_summary(ep: int, rows: list[dict], info: dict, total_reward: float, wall_time_s: float) -> dict:
    distances = [r["distance_m"] for r in rows]
    atas = [r["ata_deg"] for r in rows]
    target_atas = [r["target_ata_deg"] for r in rows]
    closures = [r["closure_mps"] for r in rows if not math.isnan(r["closure_mps"])]
    action_delta_l1 = [r["action_delta_l1"] for r in rows]
    wez_min = 152.4
    wez_max = 914.4
    in_band = [r for r in rows if wez_min <= r["distance_m"] <= wez_max]
    in_true_cone = [r for r in in_band if r["ata_deg"] <= 1.0]
    in_ata10 = [r for r in in_band if r["ata_deg"] <= 10.0]
    overshoot = [r for r in rows if r["distance_m"] < wez_min]
    ep_components = info.get("ep_reward_components", {}) or {}
    return {
        "episode": ep,
        "outcome": _classify(info),
        "end_condition": info.get("end_condition", ""),
        "steps": len(rows),
        "total_reward": round(float(total_reward), 6),
        "ownship_health": info.get("ownship_health"),
        "target_health": info.get("target_health"),
        "mean_distance_m": round(_safe_mean(distances), 3),
        "min_distance_m": round(_safe_min(distances), 3),
        "max_distance_m": round(_safe_max(distances), 3),
        "mean_ata_deg": round(_safe_mean(atas), 3),
        "min_ata_deg": round(_safe_min(atas), 3),
        "mean_target_ata_deg": round(_safe_mean(target_atas), 3),
        "time_in_band_steps": len(in_band),
        "time_in_band_ata10_steps": len(in_ata10),
        "true_cone_steps": len(in_true_cone),
        "overshoot_steps": len(overshoot),
        "overshoot_rate": round(len(overshoot) / max(len(rows), 1), 6),
        "mean_closure_mps": round(_safe_mean(closures), 3),
        "band_entry_closure_mps": round(next((r["closure_mps"] for r in rows if wez_min <= r["distance_m"] <= wez_max), float("nan")), 3),
        "mean_action_delta_l1": round(_safe_mean(action_delta_l1), 6),
        "max_action_delta_l1": round(_safe_max(action_delta_l1), 6),
        "reward_step": round(float(ep_components.get("step", 0.0)), 6),
        "reward_pursuit": round(float(ep_components.get("pursuit", 0.0)), 6),
        "reward_damage": round(float(ep_components.get("damage", 0.0)), 6),
        "reward_safety": round(float(ep_components.get("safety", 0.0)), 6),
        "reward_terminal": round(float(ep_components.get("terminal", 0.0)), 6),
        "wall_time_s": round(float(wall_time_s), 3),
    }


def main() -> int:
    args = parse_args()
    if "codex" not in args.eval_name:
        raise SystemExit("--eval-name must contain 'codex'")

    out_dir = ROOT / "artifacts" / "eval" / args.eval_name
    out_dir.mkdir(parents=True, exist_ok=True)

    observation_hook = load_observation_hook(args.observation_module)
    if args.numpy_inference:
        ownship_provider = _NumpyPPOBundleActionProvider(
            args.ownship_bundle_dir,
            explore=args.explore,
        )
    else:
        ownship_provider = RLActionProvider(
            bundle_dir=args.ownship_bundle_dir,
            algorithm_factory=build_algorithm_from_bundle,
            explore=args.explore,
        )
    target_provider = _build_target_provider(args)

    env_config = {
        "observation_mode": observation_hook["mode"],
        "observation_module": args.observation_module,
        "ownship_control_mode": "rl",
        "target_mode": _target_mode(args),
        "max_engage_time": args.max_engage_time,
        "episode_step_limit": args.episode_step_limit,
        "min_altitude": args.min_altitude,
        "artifacts_dir": str(out_dir / "codex_tacview"),
    }
    env_config.update(_load_experiment_env_config(args.experiment_yaml))

    episodes: list[dict] = []
    all_steps_path = out_dir / "codex_steps_sample.csv"
    step_fields = [
        "episode",
        "step",
        "distance_m",
        "ata_deg",
        "target_ata_deg",
        "aspect_deg",
        "closure_mps",
        "own_altitude_m",
        "target_altitude_m",
        "action_roll",
        "action_pitch",
        "action_rudder",
        "action_throttle",
        "action_delta_l1",
        "reward",
    ]
    with all_steps_path.open("w", newline="", encoding="utf-8") as step_fh:
        step_writer = csv.DictWriter(step_fh, fieldnames=step_fields)
        step_writer.writeheader()
        with activate_rule_xml(args.bt_rule_xml, ROOT):
            env = DogFightWrapper(
                env_config=env_config,
                observation_fn=observation_hook["build_observation"],
                observation_size=observation_hook["size"],
                observation_low=observation_hook["low"],
                observation_high=observation_hook["high"],
                ownship_action_provider=ownship_provider,
                target_action_provider=target_provider,
            )
            try:
                for ep in range(args.episodes):
                    start = time.time()
                    _, info = env.reset()
                    terminated = truncated = False
                    total_reward = 0.0
                    prev_distance = None
                    prev_action = None
                    rows: list[dict] = []
                    step = 0
                    while not (terminated or truncated):
                        _, reward, terminated, truncated, info = env.step(np.zeros(4, dtype=np.float32))
                        total_reward += float(reward)
                        metrics = _step_metrics(env)
                        dt = float(env._step_ratio) / float(env._sim_hz)
                        closure = float("nan")
                        if prev_distance is not None and dt > 0.0:
                            closure = (prev_distance - metrics["distance_m"]) / dt
                        action_vec = np.asarray([
                            metrics["action_roll"],
                            metrics["action_pitch"],
                            metrics["action_rudder"],
                            metrics["action_throttle"],
                        ])
                        action_delta = 0.0 if prev_action is None else float(np.abs(action_vec - prev_action).sum())
                        prev_distance = metrics["distance_m"]
                        prev_action = action_vec
                        row = {
                            "episode": ep,
                            "step": step,
                            **metrics,
                            "closure_mps": closure,
                            "action_delta_l1": action_delta,
                            "reward": float(reward),
                        }
                        rows.append(row)
                        if step % max(args.sample_stride, 1) == 0:
                            step_writer.writerow({k: row[k] for k in step_fields})
                        step += 1
                    summary = _episode_summary(ep, rows, info, total_reward, time.time() - start)
                    episodes.append(summary)
                    print(
                        f"[ep {ep + 1}/{args.episodes}] {summary['outcome']} "
                        f"end={summary['end_condition']} steps={summary['steps']} "
                        f"band={summary['time_in_band_steps']} true={summary['true_cone_steps']} "
                        f"overshoot={summary['overshoot_rate']:.3f}"
                    )
            finally:
                env.close()

    episode_path = out_dir / "codex_episodes_diagnostics.csv"
    with episode_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(episodes[0].keys()) if episodes else [])
        writer.writeheader()
        writer.writerows(episodes)

    n = max(len(episodes), 1)
    outcomes = Counter(e["outcome"] for e in episodes)
    end_conditions = Counter(e["end_condition"] for e in episodes)
    summary = {
        "eval_name": args.eval_name,
        "created": datetime.now().isoformat(timespec="seconds"),
        "episodes": len(episodes),
        "ownship_bundle_dir": args.ownship_bundle_dir,
        "explore": args.explore,
        "numpy_inference": args.numpy_inference,
        "target_backend": args.target_backend,
        "experiment_yaml": args.experiment_yaml,
        "outcomes": dict(outcomes),
        "end_conditions": dict(end_conditions),
        "real_win_rate": outcomes["real_win"] / n,
        "forced_ground_rate": outcomes["forced_ground"] / n,
        "loss_rate": outcomes["loss"] / n,
        "draw_rate": outcomes["draw"] / n,
        "mean_total_reward": _safe_mean([float(e["total_reward"]) for e in episodes]),
        "mean_time_in_band_steps": _safe_mean([float(e["time_in_band_steps"]) for e in episodes]),
        "mean_time_in_band_ata10_steps": _safe_mean([float(e["time_in_band_ata10_steps"]) for e in episodes]),
        "mean_true_cone_steps": _safe_mean([float(e["true_cone_steps"]) for e in episodes]),
        "mean_overshoot_rate": _safe_mean([float(e["overshoot_rate"]) for e in episodes]),
        "mean_band_entry_closure_mps": _safe_mean([
            float(e["band_entry_closure_mps"]) for e in episodes
            if str(e["band_entry_closure_mps"]).lower() != "nan"
        ]),
        "mean_action_delta_l1": _safe_mean([float(e["mean_action_delta_l1"]) for e in episodes]),
        "mean_reward_components": {
            "step": _safe_mean([float(e["reward_step"]) for e in episodes]),
            "pursuit": _safe_mean([float(e["reward_pursuit"]) for e in episodes]),
            "damage": _safe_mean([float(e["reward_damage"]) for e in episodes]),
            "safety": _safe_mean([float(e["reward_safety"]) for e in episodes]),
            "terminal": _safe_mean([float(e["reward_terminal"]) for e in episodes]),
        },
    }
    (out_dir / "codex_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[saved] {out_dir / 'codex_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
