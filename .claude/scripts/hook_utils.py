from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def read_event() -> dict[str, Any]:
    try:
        raw = sys.stdin.read().strip()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _search_key(data: Any, target_keys: set[str]) -> str:
    if isinstance(data, dict):
        for key, value in data.items():
            if key in target_keys and isinstance(value, str) and value.strip():
                return value.strip()
            found = _search_key(value, target_keys)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _search_key(value, target_keys)
            if found:
                return found
    return ""


def extract_command(event: dict[str, Any]) -> str:
    return _search_key(event, {"command", "cmd", "bash_command", "input"})


def extract_file_path(event: dict[str, Any]) -> str:
    return _search_key(event, {"file_path", "filePath", "path"})


def is_benchmark_command(command: str) -> bool:
    cmd = command.lower()
    return any(
        token in cmd
        for token in (
            "make run",
            "make task",
            "uv run python main.py",
            "python main.py --parallel",
            "python main.py --resume",
        )
    )


def emit_context(message: str, *, event_name: str) -> None:
    if not message.strip():
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": message.strip(),
                }
            }
        )
    )

