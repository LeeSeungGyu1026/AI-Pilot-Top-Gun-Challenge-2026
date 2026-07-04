"""Write a file:// friendly Codex training monitor that refreshes itself."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import time
from datetime import datetime
from pathlib import Path


def _load_train_monitor():
    path = Path(__file__).with_name("train_monitor.py")
    spec = importlib.util.spec_from_file_location("codex_train_monitor_source", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _render(status: dict, source_url: str) -> str:
    updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = status.get("lines") or []
    metrics_rows = []
    for line in lines[-30:]:
        if isinstance(line, dict):
            metrics_rows.append(
                "<tr>"
                + "".join(
                    f"<td>{html.escape(_fmt(line.get(key)))}</td>"
                    for key in ("iteration", "win_rate", "timeout_rate", "loss_rate", "episode_reward_mean")
                )
                + "</tr>"
            )
    if not metrics_rows:
        metrics_rows.append("<tr><td colspan='5'>No iteration metrics yet.</td></tr>")

    raw_json = html.escape(json.dumps(status, ensure_ascii=False, indent=2))
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<title>codex static train monitor</title>
<style>
body {{ margin: 0; background: #0d1117; color: #c9d1d9; font-family: Consolas, monospace; }}
header {{ padding: 12px 16px; background: #161b22; border-bottom: 1px solid #30363d; }}
h1 {{ margin: 0 0 8px; font-size: 18px; }}
.grid {{ display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 8px; padding: 16px; }}
.stat {{ background: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 6px; }}
.label {{ color: #8b949e; font-size: 12px; }}
.value {{ font-size: 20px; margin-top: 4px; }}
table {{ width: calc(100% - 32px); margin: 0 16px 16px; border-collapse: collapse; }}
th, td {{ border: 1px solid #30363d; padding: 6px 8px; text-align: right; }}
th {{ background: #161b22; color: #8b949e; }}
td:first-child, th:first-child {{ text-align: left; }}
pre {{ margin: 16px; padding: 12px; background: #010409; border: 1px solid #30363d; overflow: auto; }}
</style>
</head>
<body>
<header>
  <h1>codex static train monitor</h1>
  <div>updated: {html.escape(updated)} / source: {html.escape(source_url)}</div>
  <div>{html.escape(str(status.get("rundir", "")))}</div>
</header>
<section class="grid">
  <div class="stat"><div class="label">running</div><div class="value">{html.escape(_fmt(status.get("running")))}</div></div>
  <div class="stat"><div class="label">iteration</div><div class="value">{html.escape(_fmt(status.get("iteration")))}/{html.escape(_fmt(status.get("total_iterations")))}</div></div>
  <div class="stat"><div class="label">elapsed sec</div><div class="value">{html.escape(_fmt(status.get("elapsed_sec")))}</div></div>
  <div class="stat"><div class="label">eta sec</div><div class="value">{html.escape(_fmt(status.get("eta_sec")))}</div></div>
  <div class="stat"><div class="label">exit code</div><div class="value">{html.escape(_fmt(status.get("exit_code")))}</div></div>
</section>
<table>
  <thead><tr><th>iteration</th><th>win_rate</th><th>timeout_rate</th><th>loss_rate</th><th>reward_mean</th></tr></thead>
  <tbody>{''.join(metrics_rows)}</tbody>
</table>
<pre>{raw_json}</pre>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rundir", type=Path, required=True)
    parser.add_argument("--experiment-yaml", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval-sec", type=float, default=10.0)
    parser.add_argument("--tail-lines", type=int, default=500)
    args = parser.parse_args()

    monitor = _load_train_monitor()
    total_iterations = monitor.find_total_iterations(args.rundir, args.experiment_yaml)
    source_url = f"file:///{args.output.resolve().as_posix()}"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    while True:
        status = monitor.build_status(args.rundir, total_iterations, args.tail_lines)
        tmp = args.output.with_suffix(args.output.suffix + ".tmp")
        tmp.write_text(_render(status, source_url), encoding="utf-8")
        # BUGFIX (2026-07-04): on Windows, os.replace fails with PermissionError
        # (WinError 5) while a browser/indexer holds the target HTML open. That
        # crashed the whole monitor loop (observed in the v13b run). Retry
        # briefly, then fall back to a plain overwrite; never die on it.
        try:
            tmp.replace(args.output)
        except PermissionError:
            time.sleep(1.0)
            try:
                tmp.replace(args.output)
            except PermissionError:
                try:
                    args.output.write_text(
                        tmp.read_text(encoding="utf-8"), encoding="utf-8"
                    )
                except OSError:
                    pass
        time.sleep(args.interval_sec)


if __name__ == "__main__":
    main()
