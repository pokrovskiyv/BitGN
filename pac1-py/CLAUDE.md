# CLAUDE.md — pac1-py

Module-specific guidance for the pac1-py agent (BitGN PAC1 benchmark).

## Architecture

PCDRED pipeline: `classify.py` → `strategy.py` → `agent_loop.py` → `verify.py` → `defend.py`.

Domain Plugin Architecture: `agent.py` is a thin wrapper that delegates to `agent_loop.py` (generic loop parameterized by `DomainProtocol`) + `domain_fs.py` (filesystem domain implementation). LLM backends live in `llm.py`. Environment parsing in `environment.py`.

Each module < 200 lines, single responsibility. The project is **flat by design** — no subdirectories, no packaging (`package = false`). Do not restructure.

## Key Constraints

- **Tool outputs are untrusted** — always wrap with `[FILE DATA]` delimiters via `wrap_tool_output()` before appending to message history
- **Read-after-write mandatory** — every `Req_Write` must be followed by `Req_Read` of the same path
- **Stagnation threshold: 2** — same tool+args twice triggers a nudge
- **Security bias** — when ambiguous, `OUTCOME_DENIED_SECURITY` is safer than compliance
- **Prompts load fresh** — `strategy.py` reads `workspace/prompts/` at runtime; prefer editing prompts over Python code
- **3-level risk gating** — `ToolHandler.risk_level` in `domain_protocol.py`: LOW (no gate), MEDIUM (soft VERIFY, warn then execute), HIGH (DANGER, blocks execution via `continue`). Sensitive-path writes auto-escalate to HIGH.
- **Prompt split** — `ExecutionStrategy` splits prompt into `system_prompt_static` and `system_prompt_dynamic`. Nebius backend concatenates both into one system message; Anthropic backend sends static with `cache_control` for prompt caching.

## Protobuf SDK

`bitgn-api-*-python` packages are pinned to exact build timestamps from the Buf registry. **Do not change version pins** — they are auto-managed by `harness_core/scripts/sdk-python.sh`.

## Running

```bash
make run                    # all tasks
make task TASKS='t01 t03'   # specific tasks
```

Requires `uv sync` first. Default backend is Nebius AI Studio (`LLM_BACKEND=nebius`) with `Qwen/Qwen3-235B-A22B-Thinking-2507`. Set `NEBIUS_API_KEY` in `.env`. For Anthropic: `LLM_BACKEND=api` + `ANTHROPIC_API_KEY`.
