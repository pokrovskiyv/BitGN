"""Domain plugin protocol and supporting types.

Defines the interface that any domain (filesystem, messenger, calendar)
must satisfy to plug into the generic agent loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol, runtime_checkable

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolHandler:
    """One registered tool in a domain."""

    model: type[BaseModel]
    execute: Callable[[Any, BaseModel], Any]
    format: Callable[[BaseModel, Any], str]
    destructive: bool = False


@dataclass(frozen=True)
class ThreatPattern:
    """One regex threat pattern contributed by a domain."""

    category: str
    pattern: str
    severity: Literal["advisory", "blocking"] = "advisory"


@dataclass(frozen=True)
class ThreatProfile:
    """A domain's complete threat surface."""

    domain_name: str
    patterns: tuple[ThreatPattern, ...]
    protected_resources: tuple[str, ...] = ()
    scan_encoded: bool = True
    scan_unicode: bool = True


@dataclass(frozen=True)
class TaskTypeRule:
    """One classification rule contributed by a domain."""

    task_type: str
    pattern: str
    priority: int = 0
    estimated_steps: int = 10


@dataclass(frozen=True)
class StrategyEntry:
    """One strategy table row contributed by a domain."""

    task_type: str
    max_steps: int
    security_posture: str
    pre_submit_verify: bool = True
    prompt_fragment_path: str = ""


@dataclass(frozen=True)
class LoopMode:
    """How the agent loop operates for this domain."""

    kind: Literal["batch", "reactive"]
    max_steps: int
    poll_interval_ms: int = 0


@runtime_checkable
class DomainProtocol(Protocol):
    """What a domain must provide to the agent loop."""

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
