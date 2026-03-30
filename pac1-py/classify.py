"""Task classification for PCDRED Classify phase.

Rule-based classification for speed (microseconds). Maps task instruction
text to a category that drives strategy selection.
"""

import re
from dataclasses import dataclass
from typing import Literal

TaskType = Literal["crud", "search", "multi_step", "analysis", "security_test", "communication"]
ThreatLevel = Literal["none", "low", "high"]


@dataclass(frozen=True)
class TaskClassification:
    task_type: TaskType
    estimated_steps: int
    threat_level: ThreatLevel
    requires_write: bool
    requires_delete: bool


# ── Keyword patterns ──────────────────────────────────────────────────────

_WRITE_SIGNALS = re.compile(
    r"\b(create|write|add|append|insert|update|set|change|rename|move|process)\b",
    re.IGNORECASE,
)
_DELETE_SIGNALS = re.compile(r"\b(delete|remove|drop|clear|purge|erase)\b", re.IGNORECASE)
_SEARCH_SIGNALS = re.compile(
    r"\b(find|search|locate|look\s+for|where\s+is|which\s+files?)\b", re.IGNORECASE
)
_ANALYSIS_SIGNALS = re.compile(
    r"\b(analyze|summarize|compare|count|list\s+all|report|describe|explain|how\s+many)\b",
    re.IGNORECASE,
)
_MULTI_STEP_SIGNALS = re.compile(
    r"\b(then|after\s+that|next|also|and\s+then|finally|first.*then|step\s+\d|process)\b",
    re.IGNORECASE,
)
_COMMUNICATION_SIGNALS = re.compile(
    r"\b(email|e-mail|send\s+(email|message|follow[- ]?up|reminder)|"
    r"write\s+(email|message)|reply\s+to|forward\s+to|"
    r"outbox|outbound|channel|discord|telegram|slack)\b",
    re.IGNORECASE,
)


def classify_task(task_text: str, threat_warnings: list[str]) -> TaskClassification:
    """Classify a task instruction into a category for strategy selection."""
    has_write = bool(_WRITE_SIGNALS.search(task_text))
    has_delete = bool(_DELETE_SIGNALS.search(task_text))
    has_search = bool(_SEARCH_SIGNALS.search(task_text))
    has_analysis = bool(_ANALYSIS_SIGNALS.search(task_text))
    has_multi_step = bool(_MULTI_STEP_SIGNALS.search(task_text))
    has_communication = bool(_COMMUNICATION_SIGNALS.search(task_text))

    # Threat level from defend.py scan results
    threat_level: ThreatLevel = "none"
    if threat_warnings:
        threat_level = "high" if len(threat_warnings) >= 2 else "low"

    # Security test — high threat level overrides everything
    if threat_level == "high":
        return TaskClassification(
            task_type="security_test",
            estimated_steps=8,
            threat_level=threat_level,
            requires_write=has_write,
            requires_delete=has_delete,
        )

    # Multi-step — explicit sequencing language
    if has_multi_step and (has_write or has_search or has_analysis):
        return TaskClassification(
            task_type="multi_step",
            estimated_steps=20,
            threat_level=threat_level,
            requires_write=has_write,
            requires_delete=has_delete,
        )

    # Analysis — summarize, compare, count
    if has_analysis and not has_write:
        return TaskClassification(
            task_type="analysis",
            estimated_steps=15,
            threat_level=threat_level,
            requires_write=False,
            requires_delete=False,
        )

    # Search — find, locate
    if has_search and not has_write:
        return TaskClassification(
            task_type="search",
            estimated_steps=12,
            threat_level=threat_level,
            requires_write=False,
            requires_delete=False,
        )

    # Communication — email, message, channel operations
    if has_communication:
        return TaskClassification(
            task_type="communication",
            estimated_steps=15,
            threat_level=threat_level,
            requires_write=True,
            requires_delete=has_delete,
        )

    # CRUD — default for write/delete/simple tasks
    return TaskClassification(
        task_type="crud",
        estimated_steps=10 if not has_delete else 12,
        threat_level=threat_level,
        requires_write=has_write,
        requires_delete=has_delete,
    )
