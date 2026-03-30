# CLAUDE.md — pac1-py

Module-specific guidance for the pac1-py agent (BitGN PAC1 benchmark).

## Architecture

PCDRED pipeline: `classify.py` → `strategy.py` → `agent.py` loop → `verify.py` → `defend.py`.

Each module < 200 lines, single responsibility. The project is **flat by design** — no subdirectories, no packaging (`package = false`). Do not restructure.

## Key Constraints

- **Tool outputs are untrusted** — always wrap with `[FILE DATA]` delimiters via `wrap_tool_output()` before appending to message history
- **Read-after-write mandatory** — every `Req_Write` must be followed by `Req_Read` of the same path
- **Stagnation threshold: 2** — same tool+args twice triggers a nudge
- **Security bias** — when ambiguous, `OUTCOME_DENIED_SECURITY` is safer than compliance
- **Prompts load fresh** — `strategy.py` reads `workspace/prompts/` at runtime; prefer editing prompts over Python code

## Protobuf SDK

`bitgn-api-*-python` packages are pinned to exact build timestamps from the Buf registry. **Do not change version pins** — they are auto-managed by `harness_core/scripts/sdk-python.sh`.

## Running

```bash
make run                    # all tasks
make task TASKS='t01 t03'   # specific tasks
```

Requires `uv sync` first. Set `LLM_BACKEND=api` + `ANTHROPIC_API_KEY` for API mode, or use default `cli` mode (free, uses `claude -p`).
