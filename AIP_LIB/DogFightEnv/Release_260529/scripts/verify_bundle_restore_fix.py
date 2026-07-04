# -*- coding: utf-8 -*-
"""Verify platform bug #7 fix: --init-bundle must reach the LEARNER and the
REMOTE env runners (the ones that actually sample), not just the local runner.

Builds the Algorithm from an experiment YAML exactly like training, applies a
lightweight bundle with the production loader, then compares the bundle's
actor weights against (1) the learner module, (2) every remote env runner
module, (3) the local env runner module. Also verifies save_lightweight
extraction now includes the critic (vf) keys.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from dogfight.ai.checkpoint_io import (
    _extract_policy_weights,
    apply_lightweight_policy_bundle,
    load_lightweight_policy_bundle,
)
from scripts.codex_bundle_restore_autopsy import (
    _build_algorithm_from_experiment,
    _compare_arrays,
    _flatten_arrays,
)


def _actor_only(state) -> dict:
    """Keep only the actor-side keys (encoder + pi) so an actor-only bundle can
    be compared against a full learner module state."""
    flat = _flatten_arrays(state)
    return {
        k: v
        for k, v in flat.items()
        if k.startswith(("encoder.actor_encoder", "pi"))
    }


def _summarize(name: str, bundle_actor: dict, actual_state) -> dict:
    actual_actor = _actor_only(actual_state)
    cmp = _compare_arrays(bundle_actor, actual_actor)
    ok = (
        cmp["mismatch_count"] == 0
        and not cmp["missing_keys"]
        and cmp["common_key_count"] == len(bundle_actor)
    )
    return {"target": name, "match": ok, **cmp}


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

    _, weights = load_lightweight_policy_bundle(bundle_path)
    bundle_actor = _actor_only(weights)

    algorithm = _build_algorithm_from_experiment(exp_path)
    results = []
    try:
        apply_lightweight_policy_bundle(algorithm, bundle_path)

        # 1) learner (source of truth for every future update)
        learner_weights = algorithm.learner_group.get_weights(
            module_ids=["default_policy"]
        )["default_policy"]
        results.append(_summarize("learner", bundle_actor, learner_weights))

        # 2) every REMOTE env runner (these do the actual sampling)
        remote_states = algorithm.env_runner_group.foreach_env_runner(
            lambda er: er.module.get_state(),
            local_env_runner=False,
        )
        for idx, state in enumerate(remote_states):
            results.append(
                _summarize(f"remote_env_runner_{idx}", bundle_actor, state)
            )

        # 3) local env runner (what the old code exclusively touched)
        local_module = getattr(algorithm.env_runner, "module", None)
        if local_module is not None:
            results.append(
                _summarize("local_env_runner", bundle_actor, local_module.get_state())
            )

        # 4) save path: extraction must now include critic (vf) keys
        extracted = _flatten_arrays(_extract_policy_weights(algorithm))
        has_vf = any(k.startswith("vf") for k in extracted)
        results.append(
            {
                "target": "save_path_extraction",
                "match": has_vf,
                "extracted_key_count": len(extracted),
                "has_vf_keys": has_vf,
                "sample_keys": sorted(extracted)[:20],
            }
        )
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

    all_ok = all(r["match"] for r in results)
    report = {
        "experiment_yaml": str(exp_path),
        "bundle": str(bundle_path),
        "all_ok": all_ok,
        "results": results,
    }
    output_path = Path(args.output_json)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
