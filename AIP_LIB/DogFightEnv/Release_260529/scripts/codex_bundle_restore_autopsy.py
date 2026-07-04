# -*- coding: utf-8 -*-
"""Codex diagnostic: verify lightweight bundle restore reaches trainable modules.

This script intentionally does not train. It builds the RLlib Algorithm from an
experiment YAML, applies a lightweight bundle with the production loader, and
compares hashes before/after on the trainable RLModule and local EnvRunner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

os.environ["PYTHONPATH"] = os.pathsep.join(
    [str(ROOT), str(SRC), os.environ.get("PYTHONPATH", "")]
)

from ray.tune.registry import register_env

import train_rllib
from DogFightEnvWrapper import DogFightWrapper
from dogfight.ai.checkpoint_io import (
    apply_lightweight_policy_bundle,
    load_lightweight_policy_bundle,
)
from dogfight.ai.rllib_utils import build_algorithm_config, normalize_algorithm_name
from dogfight.ai.training.config_io import deep_update, load_experiment_env_config
from scripts.run_experiment import build_argv, load_experiment


def _to_numpy(value: Any):
    if hasattr(value, "detach"):
        return value.detach().cpu().numpy()
    if hasattr(value, "numpy") and not isinstance(value, np.ndarray):
        try:
            return value.numpy()
        except Exception:
            pass
    return value


def _state_hash(state: Any) -> str:
    digest = hashlib.sha256()

    def walk(value: Any, path: str = "") -> None:
        value = _to_numpy(value)
        if isinstance(value, dict):
            for key in sorted(value.keys(), key=str):
                digest.update(f"K:{path}/{key}\n".encode("utf-8"))
                walk(value[key], f"{path}/{key}")
            return
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                digest.update(f"I:{path}/{index}\n".encode("utf-8"))
                walk(item, f"{path}/{index}")
            return
        if isinstance(value, np.ndarray):
            arr = np.ascontiguousarray(value)
            digest.update(str(arr.dtype).encode("ascii"))
            digest.update(str(arr.shape).encode("ascii"))
            digest.update(arr.tobytes())
            return
        digest.update(repr(value).encode("utf-8", errors="replace"))

    walk(state)
    return digest.hexdigest()


def _flatten_arrays(state: Any, prefix: str = "") -> dict[str, np.ndarray]:
    state = _to_numpy(state)
    if isinstance(state, dict):
        out = {}
        for key, value in state.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten_arrays(value, child))
        return out
    if isinstance(state, (list, tuple)):
        out = {}
        for index, value in enumerate(state):
            child = f"{prefix}.{index}" if prefix else str(index)
            out.update(_flatten_arrays(value, child))
        return out
    if isinstance(state, np.ndarray):
        return {prefix: np.asarray(state)}
    return {}


def _compare_arrays(expected: Any, actual: Any) -> dict[str, Any]:
    exp = _flatten_arrays(expected)
    act = _flatten_arrays(actual)
    exp_keys = set(exp)
    act_keys = set(act)
    common = sorted(exp_keys & act_keys)
    mismatched = []
    max_abs = 0.0
    for key in common:
        if exp[key].shape != act[key].shape:
            mismatched.append({"key": key, "expected_shape": exp[key].shape, "actual_shape": act[key].shape})
            continue
        delta = float(np.max(np.abs(exp[key] - act[key]))) if exp[key].size else 0.0
        max_abs = max(max_abs, delta)
        if delta > 1e-8:
            mismatched.append({"key": key, "max_abs": delta})
    return {
        "expected_key_count": len(exp_keys),
        "actual_key_count": len(act_keys),
        "common_key_count": len(common),
        "missing_keys": sorted(exp_keys - act_keys),
        "unexpected_keys": sorted(act_keys - exp_keys),
        "mismatch_count": len(mismatched),
        "max_abs_diff": max_abs,
        "first_mismatches": mismatched[:12],
    }


def _get_module(algorithm):
    if hasattr(algorithm, "get_module"):
        try:
            return algorithm.get_module("default_policy")
        except Exception:
            try:
                return algorithm.get_module()
            except Exception:
                return None
    return None


def _get_env_runner_module(algorithm):
    env_runner = getattr(algorithm, "env_runner", None)
    if env_runner is None:
        return None
    module = getattr(env_runner, "module", None)
    if module is not None:
        return module
    get_module = getattr(env_runner, "get_module", None)
    if get_module is not None:
        try:
            return get_module()
        except Exception:
            return None
    return None


def _gaussian_entropy_from_pi_bias(state: Any):
    arrays = _flatten_arrays(state)
    bias = arrays.get("pi.net.mlp.0.bias")
    if bias is None or bias.shape[0] < 8:
        return None
    log_std = np.asarray(bias[-4:], dtype=np.float64)
    entropy = float(np.sum(0.5 * np.log(2.0 * math.pi * math.e) + log_std))
    return {"log_std": log_std.tolist(), "entropy_estimate": entropy}


def _build_algorithm_from_experiment(exp_path: Path):
    exp = load_experiment(exp_path)
    script_path, argv = build_argv(exp, exp_path)
    if script_path.name != "train_rllib.py":
        raise RuntimeError(f"expected train_rllib.py experiment, got {script_path}")

    old_argv = sys.argv[:]
    try:
        sys.argv = ["train_rllib.py", *argv]
        args = train_rllib.parse_args()
    finally:
        sys.argv = old_argv

    algorithm_name = normalize_algorithm_name(args.algorithm)
    env_config = {
        "observation_mode": args.observation_mode,
        "target_mode": args.target_mode,
        "target_behavior_dll": args.target_behavior_dll,
        "ownship_control_mode": "rl",
        "max_engage_time": args.max_engage_time,
        "episode_step_limit": args.episode_step_limit,
    }
    deep_update(env_config, load_experiment_env_config(args.experiment_yaml, ROOT))
    if args.reward_module:
        env_config["reward_module"] = args.reward_module
    if args.observation_module:
        env_config["observation_module"] = args.observation_module

    preview = train_rllib.env_creator(env_config)
    env_config["reward"] = dict(preview.config["reward"])
    env_config["wez"] = dict(preview.config["wez"])
    if args.observation_module:
        env_config["observation_mode"] = preview.config["observation_mode"]
        env_config["observation_module"] = args.observation_module
        env_config["observation_summary"] = dict(preview.config["observation_summary"])
    preview.close()

    register_env("dogfight-single-agent-v0", train_rllib.env_creator)
    config = build_algorithm_config(
        algorithm_name=algorithm_name,
        env_name="dogfight-single-agent-v0",
        env_config=env_config,
        args=train_rllib._build_algorithm_args(args),
    )
    train_rllib._ensure_ray_runtime_env()
    return config.build_algo()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-yaml", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    exp_path = Path(args.experiment_yaml)
    bundle_path = Path(args.bundle)
    if not exp_path.is_absolute():
        exp_path = ROOT / exp_path
    if not bundle_path.is_absolute():
        bundle_path = ROOT / bundle_path

    metadata, weights = load_lightweight_policy_bundle(bundle_path)
    algorithm = _build_algorithm_from_experiment(exp_path)
    try:
        train_module = _get_module(algorithm)
        env_module = _get_env_runner_module(algorithm)
        if train_module is None:
            raise RuntimeError("algorithm.get_module() did not expose a trainable module")

        train_before = train_module.get_state()
        env_before = env_module.get_state() if env_module is not None else None

        apply_metadata = apply_lightweight_policy_bundle(algorithm, bundle_path)

        train_after = train_module.get_state()
        env_after = env_module.get_state() if env_module is not None else None

        report = {
            "experiment_yaml": str(exp_path),
            "bundle": str(bundle_path),
            "bundle_metadata_iteration": metadata.get("metadata", {}).get("iteration"),
            "bundle_hash": _state_hash(weights),
            "train_module_hash_before": _state_hash(train_before),
            "train_module_hash_after": _state_hash(train_after),
            "env_runner_module_hash_before": _state_hash(env_before) if env_before is not None else None,
            "env_runner_module_hash_after": _state_hash(env_after) if env_after is not None else None,
            "train_module_matches_bundle_after": _state_hash(train_after) == _state_hash(weights),
            "env_runner_module_matches_bundle_after": (
                _state_hash(env_after) == _state_hash(weights) if env_after is not None else None
            ),
            "train_module_changed_by_apply": _state_hash(train_before) != _state_hash(train_after),
            "env_runner_module_changed_by_apply": (
                _state_hash(env_before) != _state_hash(env_after) if env_after is not None else None
            ),
            "train_compare_after": _compare_arrays(weights, train_after),
            "env_runner_compare_after": _compare_arrays(weights, env_after) if env_after is not None else None,
            "bundle_pi_bias_entropy": _gaussian_entropy_from_pi_bias(weights),
            "train_after_pi_bias_entropy": _gaussian_entropy_from_pi_bias(train_after),
            "env_after_pi_bias_entropy": _gaussian_entropy_from_pi_bias(env_after) if env_after is not None else None,
            "apply_metadata_algorithm_class": apply_metadata.get("algorithm_class"),
        }
    finally:
        try:
            algorithm.stop()
        except Exception:
            pass
        try:
            import ray

            ray.shutdown()
        except Exception:
            pass

    output_path = Path(args.output_json)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
