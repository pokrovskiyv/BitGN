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

Requires `uv sync` first. Default backend is Nebius AI Studio (`LLM_BACKEND=nebius`) with `Qwen/Qwen3-235B-A22B-Thinking-2507`. Set `NEBIUS_API_KEY` in env. For Anthropic: `LLM_BACKEND=api` + `ANTHROPIC_API_KEY`.
