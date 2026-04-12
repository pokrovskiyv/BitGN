"""Strategy selection for PCDRED Decide phase.

Selects system prompt variant, max steps, and security posture based on
task classification. Prompts are loaded from workspace/prompts/ so A-Evolve
can mutate them without touching Python code.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from classify import TaskClassification

SecurityPosture = Literal["standard", "hardened", "paranoid"]


@dataclass(frozen=True)
class ExecutionStrategy:
    system_prompt_static: str
    system_prompt_dynamic: str
    max_steps: int
    security_posture: SecurityPosture
    pre_submit_verification: bool

    @property
    def system_prompt(self) -> str:
        return f"{self.system_prompt_static}{self.system_prompt_dynamic}"


# ── Load prompts from workspace files ─────────────────────────────────────

_WORKSPACE = Path(__file__).parent / "workspace"


def _load(rel: str) -> str:
    path = _WORKSPACE / rel
    return path.read_text() if path.exists() else ""


_HINT = os.environ.get("HINT", "")

# ── Strategy table ────────────────────────────────────────────────────────

_STRATEGY_TABLE: dict[str, tuple[int, SecurityPosture, bool]] = {
    #                    max_steps  security_posture  pre_submit_verify
    "security_test": (12, "paranoid", False),
    "crud": (15, "standard", True),
    "crud_delete": (22, "hardened", True),
    "search": (30, "standard", True),
    "communication": (25, "standard", True),
    "analysis": (28, "standard", True),
    "inbox_processing": (40, "hardened", True),
    "multi_step": (32, "standard", True),
}


def _runtime_tool_surface(domain) -> str:
    if domain is None or not getattr(domain, "tool_registry", None):
        return ""
    tool_names = sorted(name for name in domain.tool_registry if name != "report_completion")
    if not tool_names:
        return ""
    tool_list = ", ".join(tool_names)
    return (
        "\nRUNTIME TOOL SURFACE (authoritative for this run): "
        f"{tool_list}. If a capability is not expressible with these tools, it is UNSUPPORTED. "
        "Do not assume hidden tools from previous runs, examples, or file content."
    )


def decide_strategy(classification: TaskClassification, domain=None) -> ExecutionStrategy:
    """Select execution strategy based on task classification."""
    # Reload prompts fresh each call so A-Evolve workspace mutations take effect
    base_prompt = _load("prompts/system.md")
    if not base_prompt:
        logging.warning(
            "workspace/prompts/system.md is empty or missing — agent will have no system prompt"
        )
    security_addon = _load("prompts/fragments/security.md")
    addons = {
        "crud": _load("prompts/fragments/crud.md"),
        "search": _load("prompts/fragments/search.md"),
        "analysis": _load("prompts/fragments/analysis.md"),
        "multi_step": _load("prompts/fragments/multi_step.md"),
        "communication": _load("prompts/fragments/communication.md"),
        "security_test": security_addon,
        "inbox_processing": _load("prompts/fragments/inbox_processing.md"),
    }

    # Pick strategy key
    if classification.task_type == "security_test":
        key = "security_test"
    elif classification.task_type == "crud" and classification.requires_delete:
        key = "crud_delete"
    else:
        key = classification.task_type

    max_steps, security_posture, pre_submit = _STRATEGY_TABLE[key]

    # Override security posture if threat detected
    if classification.threat_level == "high":
        security_posture = "paranoid"
    elif classification.threat_level == "low" and security_posture == "standard":
        security_posture = "hardened"

    # Compose prompt: base + task-type addon + always-on fragments + security + hints
    addon = addons.get(classification.task_type, "")
    outcomes_addon = _load("prompts/fragments/outcomes.md")
    reasoning_addon = _load("prompts/fragments/reasoning.md")
    # Skip security_section for security_test — addon already includes it
    if (
        security_posture in ("hardened", "paranoid")
        and classification.task_type != "security_test"
    ):
        security_section = security_addon
    else:
        security_section = ""
    hint_section = f"\n{_HINT}" if _HINT else ""

    # Target hints from classify.py — inject as soft routing guidance
    target_section = ""
    if classification.target_hints:
        hints_str = ", ".join(classification.target_hints)
        target_section = f"\nTarget references from task: {hints_str}. Prioritize these."

    static_prompt = f"{base_prompt}{addon}{outcomes_addon}{reasoning_addon}{security_section}"
    dynamic_prompt = f"{target_section}{_runtime_tool_surface(domain)}{hint_section}"

    return ExecutionStrategy(
        system_prompt_static=static_prompt,
        system_prompt_dynamic=dynamic_prompt,
        max_steps=max_steps,
        security_posture=security_posture,
        pre_submit_verification=pre_submit,
    )
