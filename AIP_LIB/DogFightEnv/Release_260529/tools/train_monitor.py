"""Live terminal-output viewer for a train-watch run: log tail + elapsed time + ETA.

Points at a train-watch RUNDIR (artifacts/watch/<stamp>/, containing train.log,
started.txt, train.exit) and serves a single web page that polls /api/status and
renders the raw stdout tail plus elapsed/ETA computed from started.txt and the
latest "iter=[N]" line, against runtime.iterations from the experiment YAML.

Usage:
    python tools/train_monitor.py                     # auto-picks latest run under artifacts/watch
    python tools/train_monitor.py --rundir <path>
    python tools/train_monitor.py --experiment-yaml experiments/ic_s3_bt.yaml
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WATCH_DIR = ROOT / "artifacts" / "watch"

ITER_RE = re.compile(r"iter=\[(\d+)\]")
ITERATIONS_FLAG_RE = re.compile(r"--iterations[= ](\d+)")
YAML_ARG_RE = re.compile(r"(\S+\.yaml)")


def find_latest_rundir(watch_dir: Path) -> Optional[Path]:
    if not watch_dir.exists():
        return None
    candidates = [p for p in watch_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _detect_encoding(head: bytes) -> str:
    # PowerShell's `*>` redirection (used by launch_train.ps1) writes UTF-16LE with BOM.
    if head[:2] == b"\xff\xfe":
        return "utf-16-le"
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    return "utf-8"


def tail_lines(path: Path, max_lines: int, max_bytes: int = 400_000) -> list[str]:
    if not path.exists():
        return []
    size = path.stat().st_size
    with open(path, "rb") as f:
        encoding = _detect_encoding(f.read(3))
        char_size = 2 if encoding == "utf-16-le" else 1
        if size > max_bytes:
            offset = size - max_bytes
            offset -= offset % char_size  # keep multi-byte chars aligned
            f.seek(offset)
        else:
            f.seek(0)
        data = f.read()
    text = data.decode(encoding, errors="replace")
    return text.splitlines()[-max_lines:]


def read_started(rundir: Path) -> Optional[datetime]:
    p = _first_existing(rundir, "started.txt", "codex_started.txt")
    if not p.exists():
        return None
    try:
        return datetime.fromisoformat(p.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def read_exit_code(rundir: Path) -> Optional[str]:
    p = _first_existing(rundir, "train.exit", "codex_train.exit")
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip()


def _first_existing(rundir: Path, *names: str) -> Path:
    for name in names:
        candidate = rundir / name
        if candidate.exists():
            return candidate
    return rundir / names[0]


def _iterations_from_yaml(path: Path) -> Optional[int]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    runtime = (data or {}).get("runtime", {}) or {}
    value = runtime.get("iterations")
    return int(value) if value is not None else None


def find_total_iterations(rundir: Path, explicit_yaml: Optional[Path]) -> Optional[int]:
    if explicit_yaml is not None:
        return _iterations_from_yaml(explicit_yaml)
    wrapper = _first_existing(rundir, "_wrapper.ps1", "codex_wrapper.ps1")
    if not wrapper.exists():
        return None
    text = wrapper.read_text(encoding="utf-8", errors="replace")
    m = ITERATIONS_FLAG_RE.search(text)
    if m:
        return int(m.group(1))
    for m in YAML_ARG_RE.finditer(text):
        candidate = (ROOT / m.group(1)).resolve()
        if candidate.exists():
            n = _iterations_from_yaml(candidate)
            if n is not None:
                return n
    return None


def latest_iteration(lines: list[str]) -> Optional[int]:
    for line in reversed(lines):
        m = ITER_RE.search(line)
        if m:
            return int(m.group(1))
    return None


def build_status(rundir: Path, total_iterations: Optional[int], tail_count: int) -> dict:
    lines = tail_lines(_first_existing(rundir, "train.log", "codex_train.log"), tail_count)
    started = read_started(rundir)
    exit_code = read_exit_code(rundir)
    now = datetime.now(timezone.utc)

    elapsed_sec = None
    if started is not None:
        elapsed_sec = (now - started.astimezone(timezone.utc)).total_seconds()

    iteration = latest_iteration(lines)
    eta_sec = None
    if elapsed_sec and iteration is not None and total_iterations and exit_code is None:
        done = iteration + 1
        if 0 < done < total_iterations:
            rate = done / elapsed_sec
            if rate > 0:
                eta_sec = (total_iterations - done) / rate

    return {
        "rundir": str(rundir),
        "lines": lines,
        "elapsed_sec": elapsed_sec,
        "iteration": iteration,
        "total_iterations": total_iterations,
        "eta_sec": eta_sec,
        "exit_code": exit_code,
        "running": exit_code is None,
    }


PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>train monitor</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #0d1117; color: #c9d1d9; font-family: "Cascadia Code", Consolas, monospace; }
  header { padding: 10px 16px; background: #161b22; border-bottom: 1px solid #30363d;
           display: flex; flex-wrap: wrap; gap: 20px; align-items: baseline; }
  header .rundir { color: #8b949e; font-size: 12px; flex-basis: 100%; }
  .stat { font-size: 14px; }
  .stat b { color: #58a6ff; }
  .running { color: #3fb950; }
  .done { color: #d29922; }
  #log { margin: 0; padding: 12px 16px; white-space: pre-wrap; word-break: break-all;
         font-size: 13px; line-height: 1.35; height: calc(100vh - 70px); overflow-y: auto; box-sizing: border-box; }
</style>
</head>
<body>
<header>
  <div class="rundir" id="rundir">-</div>
  <div class="stat">상태: <b id="status">-</b></div>
  <div class="stat">Iteration: <b id="iter">-</b></div>
  <div class="stat">경과 시간: <b id="elapsed">-</b></div>
  <div class="stat">ETA: <b id="eta">-</b></div>
</header>
<pre id="log">연결 중...</pre>
<script>
function fmtDuration(sec) {
  if (sec === null || sec === undefined || !isFinite(sec) || sec < 0) return "n/a";
  sec = Math.round(sec);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return (h > 0 ? h + "h " : "") + m + "m " + s + "s";
}

const logEl = document.getElementById("log");

async function poll() {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    const data = await res.json();

    if (data.error) {
      document.getElementById("rundir").textContent = "-";
      document.getElementById("status").textContent = "실행 중인 학습 없음";
      document.getElementById("status").className = "done";
      logEl.textContent = data.error;
      return;
    }

    document.getElementById("rundir").textContent = data.rundir;
    const statusEl = document.getElementById("status");
    if (data.running) {
      statusEl.textContent = "실행 중";
      statusEl.className = "running";
    } else {
      statusEl.textContent = "종료 (exit=" + data.exit_code + ")";
      statusEl.className = "done";
    }
    document.getElementById("iter").textContent =
      (data.iteration ?? "n/a") + " / " + (data.total_iterations ?? "?");
    document.getElementById("elapsed").textContent = fmtDuration(data.elapsed_sec);
    document.getElementById("eta").textContent = data.running ? fmtDuration(data.eta_sec) : "-";

    const atBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 40;
    logEl.textContent = data.lines.join("\\n");
    if (atBottom) logEl.scrollTop = logEl.scrollHeight;
  } catch (e) {
    document.getElementById("status").textContent = "연결 끊김";
  }
}

poll();
setInterval(poll, 1500);
</script>
</body>
</html>
"""


class _RunResolver:
    """Re-picks the run directory on every request unless pinned via --rundir.

    A single long-lived monitor process is meant to be left running across
    multiple training launches, so "latest under --watch-root" must be
    re-evaluated live -- resolving it once at startup would silently strand
    the monitor on whatever run happened to exist when it was started.
    """

    def __init__(self, pinned_rundir: Optional[Path], watch_root: Path,
                 explicit_yaml: Optional[Path]):
        self._pinned = pinned_rundir.resolve() if pinned_rundir else None
        self._watch_root = watch_root
        self._explicit_yaml = explicit_yaml
        self._iterations_cache: dict[Path, Optional[int]] = {}

    def resolve(self) -> Optional[Path]:
        if self._pinned is not None:
            return self._pinned
        latest = find_latest_rundir(self._watch_root)
        return latest.resolve() if latest else None

    def total_iterations(self, rundir: Path) -> Optional[int]:
        if rundir not in self._iterations_cache:
            self._iterations_cache[rundir] = find_total_iterations(rundir, self._explicit_yaml)
        return self._iterations_cache[rundir]


def make_handler(resolver: _RunResolver, tail_count: int):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/api/status"):
                rundir = resolver.resolve()
                if rundir is None:
                    self._send(200, json.dumps({"error": "no run directory found"}),
                               "application/json; charset=utf-8")
                    return
                total_iterations = resolver.total_iterations(rundir)
                status = build_status(rundir, total_iterations, tail_count)
                self._send(200, json.dumps(status), "application/json; charset=utf-8")
            elif self.path in ("/", "/index.html"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            else:
                self._send(404, "not found", "text/plain; charset=utf-8")

        def log_message(self, fmt: str, *args) -> None:  # noqa: A002
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rundir", type=Path, default=None,
                         help="Pin to a specific train-watch RUNDIR (default: always follow "
                              "the most recently modified run under --watch-root, live)")
    parser.add_argument("--watch-root", type=Path, default=DEFAULT_WATCH_DIR)
    parser.add_argument("--experiment-yaml", type=Path, default=None,
                         help="Experiment YAML to read runtime.iterations from for ETA "
                              "(default: auto-detected per-run from the launch command)")
    parser.add_argument("--port", type=int, default=7864)
    parser.add_argument("--tail-lines", type=int, default=500)
    args = parser.parse_args()

    if args.rundir is not None and not args.rundir.exists():
        print(f"--rundir does not exist: {args.rundir}", file=sys.stderr)
        sys.exit(1)
    if args.rundir is None and find_latest_rundir(args.watch_root) is None:
        print(f"no run directory found yet (looked in {args.watch_root}); "
              f"will keep polling once a run starts", file=sys.stderr)

    resolver = _RunResolver(args.rundir, args.watch_root, args.experiment_yaml)
    mode = f"pinned to {resolver._pinned}" if args.rundir else f"auto-following latest under {args.watch_root}"
    print(f"monitoring: {mode}")

    handler = make_handler(resolver, args.tail_lines)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"serving http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
