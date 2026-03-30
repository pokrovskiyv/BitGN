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
    system_prompt: str
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
    # Reload prompts fresh each call so A-Evolve workspace mutations take effect
    base_prompt = _load("prompts/system.md")
    if not base_prompt:
        logging.warning("workspace/prompts/system.md is empty or missing — agent will have no system prompt")
    security_addon = _load("prompts/fragments/security.md")
    addons = {
        "crud":         _load("prompts/fragments/crud.md"),
        "search":       _load("prompts/fragments/search.md"),
        "analysis":     _load("prompts/fragments/analysis.md"),
        "multi_step":   _load("prompts/fragments/multi_step.md"),
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

    # Override security posture if threat detected
    if classification.threat_level == "high":
        security_posture = "paranoid"
    elif classification.threat_level == "low" and security_posture == "standard":
        security_posture = "hardened"

    # Compose prompt
    addon = addons.get(classification.task_type, "")
    security_section = security_addon if security_posture in ("hardened", "paranoid") else ""
    hint_section = f"\n{_HINT}" if _HINT else ""

    prompt = f"{base_prompt}{addon}{security_section}{hint_section}"

    return ExecutionStrategy(
        system_prompt=prompt,
        max_steps=max_steps,
        security_posture=security_posture,
        pre_submit_verification=pre_submit,
    )
