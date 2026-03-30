# CLAUDE.md — sandbox-py

Module-specific guidance for the sandbox-py agent (BitGN mini/sandbox environment).

## Architecture

Simpler than pac1-py — single `agent.py` with reduced toolkit: `tree`, `search`, `list`, `read`, `write`, `delete`, `answer`. No classification or strategy modules. Uses `MiniRuntimeClientSync` and `mini_pb2`.

Flat project, `package = false` — do not restructure.

## Key Differences from pac1-py

- No PCDRED pipeline (no classify/strategy/defend/verify modules)
- Returns raw JSON tool results (no Unix-style formatting)
- Uses `OutlineRequest` instead of `TreeRequest`
- No A-Evolve integration
- Simpler Pydantic `NextStep` model (fewer tool types)

## Running

```bash
make run                    # all tasks
make task TASKS='t01 t03'   # specific tasks
```

Requires `uv sync` first. Same `LLM_BACKEND` / `ANTHROPIC_API_KEY` env vars as pac1-py.
