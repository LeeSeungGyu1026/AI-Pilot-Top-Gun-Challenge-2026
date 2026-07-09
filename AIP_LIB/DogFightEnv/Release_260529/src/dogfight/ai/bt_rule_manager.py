from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import shutil
import sys
from pathlib import Path
from typing import NoReturn


RULE_XML_NAME = "Rule_forTraining.xml"
PREFERRED_RULE_XML_NAME = "Rule.xml"


def _exit_with_rule_xml_error(message: str) -> NoReturn:
    print(f"[bt_rule_manager] {message}", file=sys.stderr)
    raise SystemExit(1)


def _resolve_rule_xml_source(
    rule_xml_path: str | Path | None,
    workspace_root: Path,
) -> Path:
    default_source = (workspace_root / RULE_XML_NAME).resolve()

    if not rule_xml_path:
        if default_source.exists():
            return default_source
        _exit_with_rule_xml_error(
            f"Rule XML path is empty and fallback does not exist: {default_source}"
        )

    source = Path(rule_xml_path)
    if not source.is_absolute():
        source = workspace_root / source
    source = source.resolve()

    if source.is_dir():
        source = (source / RULE_XML_NAME).resolve()

    if source.suffix.lower() == ".xml" and source.exists():
        return source

    if default_source.exists():
        print(
            "[bt_rule_manager] "
            f"Rule XML not found or not an .xml file: {source}. "
            f"Using fallback: {default_source}",
            file=sys.stderr,
        )
        return default_source

    _exit_with_rule_xml_error(
        "Rule XML not found and fallback is unavailable. "
        f"requested={source}, fallback={default_source}"
    )


@contextmanager
def activate_rule_xml(
    rule_xml_path: str | Path | None,
    workspace_root: str | Path,
) -> Iterator[None]:
    """Temporarily activate a BT rule XML as the workspace rule file."""
    workspace_root = Path(workspace_root).resolve()
    source = _resolve_rule_xml_source(rule_xml_path, workspace_root)

    # The native C++ BT tries ./Rule.xml first and only falls back to
    # ./Rule_forTraining.xml. Keep both names synchronized during the run so a
    # stale Rule.xml cannot silently override the requested experiment rule.
    targets = [
        workspace_root / RULE_XML_NAME,
        workspace_root / PREFERRED_RULE_XML_NAME,
    ]
    backups: list[tuple[Path, Path | None]] = []
    activated_targets: list[Path] = []
    for target in targets:
        target = target.resolve()
        if source == target:
            backups.append((target, None))
            activated_targets.append(target)
            continue
        backup = None
        if target.exists():
            backup = target.with_name(f"{target.name}.bak")
            shutil.copy2(target, backup)
        shutil.copy2(source, target)
        backups.append((target, backup))
        activated_targets.append(target)

    print(
        "[bt_rule_manager] activated Rule XML: "
        f"{source} -> {', '.join(str(path) for path in activated_targets)}",
        file=sys.stderr,
    )
    try:
        yield
    finally:
        for target, backup in reversed(backups):
            if backup and backup.exists():
                shutil.copy2(backup, target)
                backup.unlink()
            elif source != target and target.exists():
                target.unlink()
