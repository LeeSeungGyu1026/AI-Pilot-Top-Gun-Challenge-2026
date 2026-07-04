"""Codex wrapper for train_monitor.py with a configurable bind host."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default="0.0.0.0")
    known, remaining = parser.parse_known_args()

    monitor_path = Path(__file__).with_name("train_monitor.py")
    sys.argv = [str(monitor_path), *remaining]
    source = monitor_path.read_text(encoding="utf-8")
    source = source.replace(
        'ThreadingHTTPServer(("127.0.0.1", args.port), handler)',
        'ThreadingHTTPServer((codex_bind_host, args.port), handler)',
    )
    source = source.replace(
        'print(f"serving http://127.0.0.1:{args.port}")',
        'print(f"serving http://{codex_bind_host}:{args.port}")',
    )
    globals_for_run = {
        "__file__": str(monitor_path),
        "__name__": "__main__",
        "codex_bind_host": known.host,
    }
    exec(compile(source, str(monitor_path), "exec"), globals_for_run)


if __name__ == "__main__":
    main()
