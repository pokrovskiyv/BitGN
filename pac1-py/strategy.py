"""Strategy selection for PCDRED Decide phase.

Selects system prompt variant, max steps, and security posture based on
task classification. Prompts are loaded from workspace/prompts/ so A-Evolve
can mutate them without touching Python code.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from classify import TaskClassification


SecurityPosture = Literal["standard", "hardened", "paranoid"]


@dataclass(frozen=True)
class ExecutionStrategy:
    system_prompt: str
    max_steps: int
    security_posture: SecurityPosture
    pre_submit_verification: bool


# ── Load prompts from workspace files ─────────────────────────────────────

_WORKSPACE = Path(__file__).parent / "workspace"


def _load(rel: str) -> str:
    path = _WORKSPACE / rel
    return path.read_text() if path.exists() else ""


_BASE_PROMPT = _load("prompts/system.md")
_SECURITY_ADDON = _load("prompts/fragments/security.md")
_CRUD_ADDON = _load("prompts/fragments/crud.md")
_SEARCH_ADDON = _load("prompts/fragments/search.md")
_ANALYSIS_ADDON = _load("prompts/fragments/analysis.md")
_MULTI_STEP_ADDON = _load("prompts/fragments/multi_step.md")

_HINT = os.environ.get("HINT", "")

# ── Prompt variant map ────────────────────────────────────────────────────

_ADDONS = {
    "crud": _CRUD_ADDON,
    "search": _SEARCH_ADDON,
    "analysis": _ANALYSIS_ADDON,
    "multi_step": _MULTI_STEP_ADDON,
    "security_test": _SECURITY_ADDON,
}

# ── Strategy table ────────────────────────────────────────────────────────

_STRATEGY_TABLE: dict[str, tuple[int, SecurityPosture, bool]] = {
    #                    max_steps  security_posture  pre_submit_verify
    "security_test":    (8,         "paranoid",       False),
    "crud":             (10,        "standard",       True),
    "crud_delete":      (12,        "hardened",       True),
    "search":           (15,        "standard",       True),
    "analysis":         (20,        "standard",       True),
    "multi_step":       (25,        "standard",       True),
}


def decide_strategy(classification: TaskClassification) -> ExecutionStrategy:
    """Select execution strategy based on task classification."""
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

    # Compose prompt
    addon = _ADDONS.get(classification.task_type, "")
    security_addon = _SECURITY_ADDON if security_posture in ("hardened", "paranoid") else ""
    hint_section = f"\n{_HINT}" if _HINT else ""

    prompt = f"{_BASE_PROMPT}{addon}{security_addon}{hint_section}"

    return ExecutionStrategy(
        system_prompt=prompt,
        max_steps=max_steps,
        security_posture=security_posture,
        pre_submit_verification=pre_submit,
    )
