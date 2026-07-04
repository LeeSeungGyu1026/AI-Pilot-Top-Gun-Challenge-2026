# -*- coding: utf-8 -*-
"""Codex preflight check for RLlib/Torch training availability."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
REPORT = ROOT / "reports" / "codex_torch_ready_status.json"


def _recent_code_integrity_events() -> list[dict]:
    command = (
        "Get-WinEvent -FilterHashtable "
        "@{LogName='Microsoft-Windows-CodeIntegrity/Operational'; "
        "StartTime=(Get-Date).AddMinutes(-30)} -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Message -match 'c10.dll|torch|python.exe|Smart App Control' } | "
        "Select-Object -First 8 TimeCreated,Id,Message | ConvertTo-Json -Depth 3"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return [{"error": str(exc)}]
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        data = json.loads(completed.stdout)
    except Exception:
        return [{"raw": completed.stdout.strip()}]
    return data if isinstance(data, list) else [data]


def main() -> int:
    completed = subprocess.run(
        [str(PYTHON), "-c", "import torch; print(torch.__version__)"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    ok = completed.returncode == 0
    report = {
        "ok": ok,
        "python": str(PYTHON),
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "recent_code_integrity_events": [] if ok else _recent_code_integrity_events(),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if ok:
        print(f"[codex][torch-ready] OK: {completed.stdout.strip()}")
        print(f"[codex][torch-ready] report: {REPORT}")
        return 0
    print("[codex][torch-ready] FAILED: torch cannot be imported; RLlib training will fail.")
    print(f"[codex][torch-ready] report: {REPORT}")
    print(completed.stderr.strip())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
