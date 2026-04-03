"""Task classification for PCDRED Classify phase.

Rule-based classification for speed (microseconds). Maps task instruction
text to a category that drives strategy selection.
"""

import re
from dataclasses import dataclass
from typing import Literal

TaskType = Literal[
    "crud",
    "search",
    "multi_step",
    "analysis",
    "security_test",
    "communication",
    "inbox_processing",
]
ThreatLevel = Literal["none", "low", "high"]


@dataclass(frozen=True)
class TaskClassification:
    task_type: TaskType
    estimated_steps: int
    threat_level: ThreatLevel
    requires_write: bool
    requires_delete: bool
    target_hints: tuple[str, ...] = ()


# ── Keyword patterns ──────────────────────────────────────────────────────

_WRITE_SIGNALS = re.compile(
    r"\b(create|write|add|append|insert|update|set|change|rename|move|process|"
    r"reschedule|capture|distill|schedule)\b",
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
    r"\b(then|after\s+that|next|also|and\s+then|finally|first.*then|step\s+\d|process|"
    r"when\s+done|accordingly)\b",
    re.IGNORECASE,
)
_COMMUNICATION_SIGNALS = re.compile(
    r"\b(email|e-mail|send\s+(email|message|follow[- ]?up|reminder)|"
    r"write\s+(email|message)|reply\s+to|forward\s+to|"
    r"outbox|outbound|channel|discord|telegram|slack)\b",
    re.IGNORECASE,
)
_INBOX_PROCESSING_SIGNALS = re.compile(
    r"\b(process\s+(the\s+)?inbox|from\s+(the\s+)?inbox|inbox\s+file)\b",
    re.IGNORECASE,
)

_HIGH_CONFIDENCE_CATEGORIES = frozenset(
    {
        "direct_override",
        "hierarchy_spoof",
        "role_manipulation",
        "protected_file",
        "context_reset",
        "blanket_instruction",
    }
)


def _compute_threat_level(threat_warnings: list[str]) -> ThreatLevel:
    """Category-based threat level: high-confidence categories → immediate 'high'."""
    if not threat_warnings:
        return "none"
    categories = set()
    for w in threat_warnings:
        m = re.search(r"\[(\w+)\]", w)
        if m:
            categories.add(m.group(1))
    if categories & _HIGH_CONFIDENCE_CATEGORIES:
        return "high"
    if len(categories) >= 2:  # distinct categories, not raw warning count
        return "high"
    return "low"


_PATH_HINTS = re.compile(
    r"(?:(?:\b\w+/)+\w+(?:\.\w+)?)"  # path/to/file or path/to/dir
    r"|(?:\b\w+\.(?:md|json|txt|yaml))"  # file.ext
    r"|(?:outbox|inbox|contacts|calendar)",  # known directories
    re.IGNORECASE,
)


def _extract_target_hints(task_text: str) -> tuple[str, ...]:
    """Extract path/file references from task text for targeted routing."""
    return tuple(dict.fromkeys(_PATH_HINTS.findall(task_text)))


def classify_task(task_text: str, threat_warnings: list[str]) -> TaskClassification:
    """Classify a task instruction into a category for strategy selection."""
    hints = _extract_target_hints(task_text)
    has_write = bool(_WRITE_SIGNALS.search(task_text))
    has_delete = bool(_DELETE_SIGNALS.search(task_text))
    has_search = bool(_SEARCH_SIGNALS.search(task_text))
    has_analysis = bool(_ANALYSIS_SIGNALS.search(task_text))
    has_multi_step = bool(_MULTI_STEP_SIGNALS.search(task_text))
    has_communication = bool(_COMMUNICATION_SIGNALS.search(task_text))
    has_inbox_processing = bool(_INBOX_PROCESSING_SIGNALS.search(task_text))

    # Threat level: category-based (high-confidence categories → immediate "high")
    threat_level = _compute_threat_level(threat_warnings)

    # Security test — high threat level overrides everything
    if threat_level == "high":
        return TaskClassification(
            task_type="security_test",
            estimated_steps=8,
            threat_level=threat_level,
            requires_write=has_write,
            requires_delete=has_delete,
            target_hints=hints,
        )

    # Inbox processing — "process inbox" (must precede multi_step; "process" hits both)
    if has_inbox_processing:
        return TaskClassification(
            task_type="inbox_processing",
            estimated_steps=22,
            threat_level=threat_level,
            requires_write=True,
            requires_delete=has_delete,
            target_hints=hints,
        )

    # Multi-step — explicit sequencing language
    if has_multi_step and (has_write or has_search or has_analysis):
        return TaskClassification(
            task_type="multi_step",
            estimated_steps=20,
            threat_level=threat_level,
            requires_write=has_write,
            requires_delete=has_delete,
            target_hints=hints,
        )

    # Analysis — summarize, compare, count
    if has_analysis and not has_write:
        return TaskClassification(
            task_type="analysis",
            estimated_steps=15,
            threat_level=threat_level,
            requires_write=False,
            requires_delete=False,
            target_hints=hints,
        )

    # Search — find, locate
    if has_search and not has_write:
        return TaskClassification(
            task_type="search",
            estimated_steps=12,
            threat_level=threat_level,
            requires_write=False,
            requires_delete=False,
            target_hints=hints,
        )

    # Communication — email, message, channel operations
    if has_communication:
        return TaskClassification(
            task_type="communication",
            estimated_steps=15,
            threat_level=threat_level,
            requires_write=True,
            requires_delete=has_delete,
            target_hints=hints,
        )

    # CRUD — default for write/delete/simple tasks
    return TaskClassification(
        task_type="crud",
        estimated_steps=10 if not has_delete else 12,
        threat_level=threat_level,
        requires_write=has_write,
        requires_delete=has_delete,
        target_hints=hints,
    )
