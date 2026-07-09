from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
AIP_LIB = ROOT.parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dogfight.ai.bt_rule_manager import activate_rule_xml
from dogfight.ai.native_bt import AIPilot


DEFAULT_RULES = [
    "Rule_Straight.xml",
    "Rule_Circle_Horizontal.xml",
    "Rule_Circle.xml",
]


def resolve_rule(rule: str) -> Path:
    path = Path(rule)
    if path.is_absolute():
        return path
    candidate = AIP_LIB / rule
    if candidate.exists():
        return candidate
    return (ROOT / rule).resolve()


def smoke_create_behavior_tree(dll: str, rule_path: Path) -> None:
    with activate_rule_xml(str(rule_path), ROOT):
        bt = AIPilot(dll)
        bt.CreateBehaviorTree(260529, 1)
        bt.Reset()


def parse_value(output: str, prefix: str) -> str:
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def run_local_sim(dll: str, rule_name: str, seconds: float, steps: int) -> dict[str, str]:
    cmd = [
        sys.executable,
        "run_local_dogfight.py",
        "--ownship-backend",
        "bt",
        "--ownship-bt-dll",
        dll,
        "--target-backend",
        "bt",
        "--target-bt-dll",
        dll,
        "--bt-rule-xml",
        str(Path("..") / ".." / rule_name),
        "--max-engage-time",
        str(seconds),
        "--episode-step-limit",
        str(steps),
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = proc.stdout
    return {
        "returncode": str(proc.returncode),
        "end_condition": parse_value(output, "end_condition"),
        "ownship_health": parse_value(output, "ownship_health"),
        "target_health": parse_value(output, "target_health"),
        "output": output,
    }


def validate_rule(dll: str, rule_name: str, seconds: float, steps: int, require_timeout: bool) -> bool:
    rule_path = resolve_rule(rule_name)
    print(f"===== {rule_name} =====")
    print(f"rule: {rule_path}")
    smoke_create_behavior_tree(dll, rule_path)
    print("BT_CREATE_OK")

    result = run_local_sim(dll, rule_name, seconds, steps)
    end_condition = result["end_condition"]
    ownship_health = result["ownship_health"]
    target_health = result["target_health"]
    print(f"SIM_RETURN_CODE: {result['returncode']}")
    print(f"END_CONDITION: {end_condition}")
    print(f"OWNSHIP_HEALTH: {ownship_health}")
    print(f"TARGET_HEALTH: {target_health}")

    ok = result["returncode"] == "0"
    if require_timeout and end_condition != "max time out":
        ok = False
    if "altitude below min" in end_condition.lower():
        ok = False
    if not ok:
        print("LOCAL_SIM_OUTPUT_BEGIN")
        print(result["output"].rstrip())
        print("LOCAL_SIM_OUTPUT_END")
        print("RESULT: FAIL")
        return False

    print("RESULT: OK")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate every custom BT rule in Release_260529.")
    parser.add_argument("--dll", default="AIP_BASE_target_circle_debug.dll")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--steps", type=int, default=3600)
    parser.add_argument(
        "--rule",
        action="append",
        dest="rules",
        help="Rule XML filename/path. Can be passed more than once. Defaults to all custom rules.",
    )
    parser.add_argument(
        "--allow-early-termination",
        action="store_true",
        help="Do not require the local sim to end by max time out.",
    )
    args = parser.parse_args()

    dll_path = ROOT / args.dll
    if not dll_path.exists():
        print(f"missing DLL: {dll_path}", file=sys.stderr)
        return 2

    rules = args.rules or DEFAULT_RULES
    failed: list[str] = []
    for rule in rules:
        try:
            ok = validate_rule(
                args.dll,
                rule,
                args.seconds,
                args.steps,
                require_timeout=not args.allow_early_termination,
            )
        except Exception as exc:
            print(f"RESULT: FAIL ({exc})")
            ok = False
        if not ok:
            failed.append(rule)

    print("===== SUMMARY =====")
    if failed:
        print("FAILED: " + ", ".join(failed))
        return 1
    print("ALL_CUSTOM_BT_OK: " + ", ".join(rules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
