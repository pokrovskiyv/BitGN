# Domain Plugin Architecture

**Date**: 2026-03-30
**Status**: Approved (design only, implement post-competition)
**Depends on**: PCDRED Meta-Model (2026-03-29)

## 1. Problem Statement

BitGN has two agents (pac1-py, sandbox-py) that share harness infrastructure but diverge in every concrete dimension: protobuf clients, tool sets, output formatting, security, classification, strategy. Adding new domains (messenger, calendar, email, browser) would require duplicating entire agent.py files. The current architecture is a closed-world pipeline optimized for filesystem tasks.

**Goal**: Plugin architecture where each domain registers its tools, threats, strategies, and formatters — while preserving the competition-ready runtime, A-Evolve integration, and flat project structure.

## 2. Current State (Why Two Agents Diverge)

| Dimension | pac1-py (filesystem) | sandbox-py (mini) |
|-----------|---------------------|-------------------|
| Protobuf client | `PcmRuntimeClientSync` / `pcm_pb2` | `MiniRuntimeClientSync` / `mini_pb2` |
| Tools | 11 (tree, find, search, list, read, write, delete, mkdir, move, context, answer) | 7 (tree, search, list, read, write, delete, answer) |
| Output format | Unix-style (`cat`, `rg`, `tree` ASCII) | Raw JSON (`MessageToDict`) |
| Security | Full PCDRED: 30+ regex patterns, `wrap_tool_output()`, advisory warnings | None |
| Classification | Rule-based, 5 types (`classify.py`) | None |
| Strategy | Strategy table + prompt fragments (`strategy.py`) | Hardcoded 30-step loop, 7-line prompt |
| A-Evolve | Full integration (`evolve.py`, `bitgn_agent.py`) | None |
| Dispatch | 11-branch `isinstance` chain | 7-branch `isinstance` chain |

Shared: `HarnessServiceClientSync` outer loop, Pydantic `NextStep` structured output, dual LLM backends (nebius/api), message history replay pattern.

## 3. Architecture Decisions

### ADR-1: `typing.Protocol` over ABC

Structural subtyping. No import dependency between domain modules. Each agent directory defines its domain object independently. `@runtime_checkable` for safety.

**Why not ABC?** Flat project constraint (`package = false`). No shared base module importable across pac1 and sandbox. Protocol lets each domain satisfy the interface without inheritance.

### ADR-2: Dict-based tool registry over isinstance chains

`dict[str, ToolHandler]` — adding a tool = one dict entry. No dispatcher modification. Eliminates 11-branch if/elif in pac1, 7-branch in sandbox.

**Why not class-per-tool pattern?** Over-engineering for this scale. ToolHandler dataclass is the right atomic unit — small enough to inline, rich enough to carry execute + format + destructive flag.

### ADR-3: Dynamic Pydantic union from registry

Build `NextStep.function` union at domain init from registered tool models. Preserves structured output (LLM gets JSON Schema). ~1ms overhead, negligible vs ~2-10s LLM latency.

**Why not catch-all `dict`?** Loses all schema guidance for LLM. The entire value of `NextStep` is constraining the LLM to emit valid tool calls.

### ADR-4: Synchronous polling for reactive domains

Keep `run_agent()` synchronous. Add `poll_events()` injection point for reactive domains (messenger). Preserves A-Evolve signature constraint.

**Why not async?** `run_agent(model, harness_url, task_text)` is called synchronously by `bitgn_agent.py`. Making it async breaks A-Evolve. BitGN VM uses unary ConnectRPC — no streaming channel. Polling is the natural fit.

### ADR-5: Open `str` task types over `Literal` union

Domains add task types without touching type definitions. Strategy lookup uses matching string keys from domain-contributed rules.

**Why not keep Literal?** Adding a messenger task type ("channel_management") requires modifying the Literal — a change in a shared type definition. Open strings let domains register types independently.

### ADR-6: Frozen dataclass tuples for threat profiles

Immutable, consistent with codebase patterns (`TaskClassification`, `ExecutionStrategy` are already `frozen=True`). Tuples (not lists) for frozen dataclass compatibility.

## 4. Domain Protocol

```python
# domain_protocol.py (~60 lines)
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol, runtime_checkable
from pydantic import BaseModel


@dataclass(frozen=True)
class ToolHandler:
    model: type[BaseModel]
    execute: Callable[[Any, BaseModel], Any]
    format: Callable[[BaseModel, Any], str]
    destructive: bool = False


@dataclass(frozen=True)
class ThreatPattern:
    category: str
    pattern: str
    severity: Literal["advisory", "blocking"] = "advisory"


@dataclass(frozen=True)
class ThreatProfile:
    domain_name: str
    patterns: tuple[ThreatPattern, ...]
    protected_resources: tuple[str, ...] = ()
    scan_encoded: bool = True
    scan_unicode: bool = True


@dataclass(frozen=True)
class TaskTypeRule:
    task_type: str
    pattern: str
    priority: int = 0
    estimated_steps: int = 10


@dataclass(frozen=True)
class StrategyEntry:
    task_type: str
    max_steps: int
    security_posture: str
    pre_submit_verify: bool = True
    prompt_fragment_path: str = ""


@dataclass(frozen=True)
class LoopMode:
    kind: Literal["batch", "reactive"]
    max_steps: int
    poll_interval_ms: int = 0


@runtime_checkable
class DomainProtocol(Protocol):
    name: str
    nextstep_type: type[BaseModel]
    tool_registry: dict[str, ToolHandler]
    threat_profile: ThreatProfile | None
    classification_rules: tuple[TaskTypeRule, ...]
    strategy_entries: tuple[StrategyEntry, ...]
    loop_mode: LoopMode

    def create_client(self, harness_url: str) -> Any: ...
    def boot_messages(self, client: Any) -> list[dict]: ...
    def dispatch(self, client: Any, cmd: BaseModel) -> Any: ...
    def format_result(self, cmd: BaseModel, result: Any) -> str: ...
    def is_completion(self, cmd: BaseModel) -> bool: ...
    def completion_outcome(self, cmd: BaseModel) -> str | None: ...
    def wrap_output(self, content: str) -> str: ...
    def poll_events(self, client: Any) -> list[dict] | None: ...
```

## 5. Migration Plan

Five phases, each independently deployable and testable via `make run`.

### Phase 1: Extract shared agent loop

**New file**: `agent_loop.py` (~120 lines)

Extract from `pac1-py/agent.py`:
- `_format_history()`, `_extract_json()` — prompt formatting
- `_call_nebius()`, `_call_api()`, `call_llm()` — parameterized by `nextstep_type`
- Main agent loop — parameterized by `DomainProtocol`

```python
def call_llm(system: str, messages: list[dict], model: str,
             nextstep_type: type[BaseModel]) -> BaseModel:
    ...

def run_agent_loop(model: str, harness_url: str, task_text: str,
                   domain: DomainProtocol) -> str | None:
    client = domain.create_client(harness_url)
    messages = domain.boot_messages(client)
    ...
```

### Phase 2: Create filesystem domain

**New file**: `domain_fs.py` (~180 lines)

Move from `agent.py`:
- All `Req_*` Pydantic models + `ReportTaskCompletion`
- All `_format_*` functions + `_render_command()` + `_format_tree_entry()`
- `dispatch()` rewritten as `TOOL_REGISTRY` dict
- `OUTCOME_BY_NAME`
- Boot sequence (tree + AGENTS.md + context)

```python
class FilesystemDomain:
    name = "filesystem"
    tool_registry = {
        "tree": ToolHandler(model=Req_Tree, execute=..., format=_format_tree_response),
        "read": ToolHandler(model=Req_Read, execute=..., format=_format_read_response),
        "delete": ToolHandler(model=Req_Delete, execute=..., format=..., destructive=True),
        ...
    }
    loop_mode = LoopMode(kind="batch", max_steps=25)
```

### Phase 3: Thin out agent.py

`agent.py` becomes ~15 lines:

```python
from agent_loop import run_agent_loop
from domain_fs import FilesystemDomain

_domain = FilesystemDomain()

def run_agent(model: str, harness_url: str, task_text: str) -> str | None:
    return run_agent_loop(model, harness_url, task_text, domain=_domain)
```

Preserves `from agent import run_agent` for `bitgn_agent.py`, `main.py`, `evolve.py`.

### Phase 4: Create sandbox domain (optional, separate PR)

**New file** in `sandbox-py/`: `domain_mini.py` (~100 lines)

Extracts sandbox tool models, raw JSON formatting, dispatch into `MiniDomain`. Zero risk to pac1.

### Phase 5: Parameterize classify/strategy/defend

- `classify_task(task_text, threat_warnings, rules)` — domain contributes `classification_rules`
- `decide_strategy(classification, strategy_entries)` — domain contributes `strategy_entries`
- `scan_content(content, profile)` — domain contributes `threat_profile`

## 6. A-Evolve Compatibility

| Constraint | Preserved? | How |
|-----------|-----------|-----|
| `run_agent(model, harness_url, task_text)` signature | Yes | `agent.py` thin wrapper |
| `workspace/` at `pac1-py/workspace/` | Yes | Unchanged path |
| `workspace/prompts/system.md` + `fragments/` | Yes | Same files, same hot-reload |
| `Trajectory.conversation[0]` schema | Yes | `bitgn_agent.py` untouched |
| Flat project structure (`package = false`) | Yes | All new files in project root |
| Fresh prompt reload per call | Yes | `_load()` pattern preserved |

**Unchanged files**: `bitgn_agent.py`, `bitgn_benchmark.py`, `evolve.py`, `verify.py`, `main.py`, `pyproject.toml`, all `workspace/prompts/*`.

## 7. Workspace Layout (Future Domains)

```
pac1-py/workspace/prompts/fragments/
├── crud.md              # filesystem domain (existing)
├── search.md
├── analysis.md
├── multi_step.md
├── security.md          # cross-cutting (existing)
└── messenger/           # future domain fragments
    ├── channel_mgmt.md
    └── message_search.md
```

Each domain's `StrategyEntry` references paths relative to `workspace/prompts/fragments/`. A-Evolve mutates any file under `workspace/` without domain awareness.

## 8. Future Domain Example: Messenger

```python
class MessengerDomain:
    name = "messenger"

    tool_registry = {
        "send_message": ToolHandler(model=Req_SendMessage, ...),
        "read_channel": ToolHandler(model=Req_ReadChannel, ...),
        "list_channels": ToolHandler(model=Req_ListChannels, ...),
        "report_completion": ToolHandler(model=ReportCompletion, ...),
    }

    threat_profile = ThreatProfile(
        domain_name="messenger",
        patterns=(
            ThreatPattern("impersonation", r"(pretend|act as|pose as).*?(admin|moderator)"),
            ThreatPattern("mass_send", r"send.*?(all|every|each)\s+(contact|user|member)"),
            ThreatPattern("unauthorized_read", r"read.*?(private|dm|confidential)"),
        ),
        protected_resources=("#admin-channel", "system-bot"),
    )

    classification_rules = (
        TaskTypeRule("channel_mgmt", r"\b(create|archive|rename)\s+channel\b", priority=10),
        TaskTypeRule("message_search", r"\b(find|search)\s+message\b", priority=10),
    )

    strategy_entries = (
        StrategyEntry("channel_mgmt", max_steps=12, security_posture="hardened"),
        StrategyEntry("message_search", max_steps=15, security_posture="standard"),
    )

    loop_mode = LoopMode(kind="reactive", max_steps=20, poll_interval_ms=500)
```

## 9. Verification

After each migration phase:
1. `cd pac1-py && make run` — full benchmark, compare to baseline
2. `docs/run_history.json` — zero score regression
3. `uv run python evolve.py --dry-run` — A-Evolve workspace discovery works
4. For sandbox (Phase 4): `cd sandbox-py && make run`

## 10. Risk Factors

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dynamic union breaks LLM structured output | Agent can't parse tool calls | Test with both nebius and api backends in Phase 2 |
| Registry dispatch slower than isinstance | Negligible (dict lookup vs isinstance chain) | Benchmark if concerned |
| Protocol conformance missed at runtime | Agent loop crashes | `@runtime_checkable` + assert at init |
| A-Evolve workspace path assumption | Evolution cycles fail | Phase 3 verification: `evolve.py --dry-run` |
| Flat project grows beyond comfort | Navigation difficulty | Max 10 files; domains are one file each |
