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
    system_prompt_static: str  # base + outcomes + reasoning (same for all tasks)
    system_prompt_dynamic: str  # task addon + security + hints (varies per task)
    max_steps: int
    security_posture: SecurityPosture
    pre_submit_verification: bool


# ── Load prompts from workspace files ─────────────────────────────────────

_WORKSPACE = Path(__file__).parent / "workspace"


def _load(rel: str) -> str:
    path = _WORKSPACE / rel
    return path.read_text() if path.exists() else ""


_HINT = os.environ.get("HINT", "")

# ── Strategy table ────────────────────────────────────────────────────────

_COMPLETION_RESERVE = 3  # extra steps reserved for completion gate cascade

_STRATEGY_TABLE: dict[str, tuple[int, SecurityPosture, bool]] = {
    #                    max_steps  security_posture  pre_submit_verify
    "security_test": (8, "paranoid", False),
    "crud": (14, "standard", True),
    "crud_delete": (24, "hardened", True),
    "search": (15, "standard", True),
    "communication": (22, "standard", True),
    "inbox_processing": (28, "hardened", True),
    "analysis": (20, "standard", True),
    "multi_step": (25, "standard", True),
}


def decide_strategy(classification: TaskClassification) -> ExecutionStrategy:
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
        "inbox_processing": _load("prompts/fragments/inbox_processing.md"),
        "security_test": security_addon,
    }

    # Pick strategy key
    if classification.task_type == "security_test":
        key = "security_test"
    elif classification.task_type == "crud" and classification.requires_delete:
        key = "crud_delete"
    else:
        key = classification.task_type

    max_steps, security_posture, pre_submit = _STRATEGY_TABLE[key]
    max_steps += _COMPLETION_RESERVE

    # Override security posture if threat detected
    if classification.threat_level == "high":
        security_posture = "paranoid"
    elif classification.threat_level == "low" and security_posture == "standard":
        security_posture = "hardened"

    # Compose prompt: base + task-type addon + always-on fragments + security + hints
    addon = addons.get(classification.task_type, "")
    outcomes_addon = _load("prompts/fragments/outcomes.md")
    reasoning_addon = _load("prompts/fragments/reasoning.md")
    # Always inject security reminder (except security_test — already has it as primary addon)
    security_section = security_addon if classification.task_type != "security_test" else ""
    hint_section = f"\n{_HINT}" if _HINT else ""

    # Target hints from classify.py — inject as soft routing guidance
    target_section = ""
    if classification.target_hints:
        hints_str = ", ".join(classification.target_hints)
        target_section = f"\nTarget references from task: {hints_str}. Prioritize these."

    static = f"{base_prompt}{outcomes_addon}{reasoning_addon}"
    dynamic = f"{addon}{target_section}{security_section}{hint_section}"

    return ExecutionStrategy(
        system_prompt_static=static,
        system_prompt_dynamic=dynamic,
        max_steps=max_steps,
        security_posture=security_posture,
        pre_submit_verification=pre_submit,
    )
