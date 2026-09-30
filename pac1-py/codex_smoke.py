"""Preflight check for the Codex CLI LLM backend."""

from __future__ import annotations

import sys

from pydantic import BaseModel

from llm import call_codex_cli_structured, get_codex_cli_binary
from settings import SETTINGS


class SmokeResult(BaseModel):
    ok: str


def main() -> int:
    try:
        result = call_codex_cli_structured(
            "",
            "",
            [{"role": "user", "content": 'Return {"ok":"yes"}.'}],
            SETTINGS.primary_model,
            SmokeResult,
        )
    except Exception as exc:
        print(
            f"codex_cli smoke failed for {SETTINGS.primary_model} via "
            f"{get_codex_cli_binary()}: {exc}",
            file=sys.stderr,
        )
        return 1
    if result.ok != "yes":
        print(f"codex_cli smoke returned unexpected payload: {result.model_dump_json()}")
        return 1
    print(f"codex_cli smoke OK: {SETTINGS.primary_model} via {get_codex_cli_binary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
