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
    r"reschedule|capture|distill|schedule|queue(?:\s+up)?|enqueue|migrate|stage|batch)\b",
    re.IGNORECASE,
)
_DELETE_SIGNALS = re.compile(r"\b(delete|remove|drop|clear|purge|erase)\b", re.IGNORECASE)
_SEARCH_SIGNALS = re.compile(
    r"\b(find|search|locate|look\s+for|where\s+is|which\s+files?|what(?:'s|\s+is)|"
    r"which\b|who\s+is|who\s+are|when\s+(?:is|did|was|were)|can\s+you\s+tell\s+me|"
    r"quote\s+(?:me|the)|show\s+me(?:\s+the)?|tell\s+me(?:\s+the)?|give\s+me(?:\s+the)?|"
    r"i\s+need(?:\s+the)?|need\s+the|reply\s+with\s+the|return\s+(?:the|only)|"
    r"how\s+(?:much|long|often|far|old))\b",
    re.IGNORECASE,
)
_LOOKUP_SIGNALS = re.compile(
    r"\b(legal\s+entity|exact\s+legal\s+name|account\s+manager|managed\s+by|"
    r"primary\s+contact|email\s+address|who\s+runs?|who\s+owns?|owned\s+by|"
    r"start\s+date|end\s+date|due\s+date|launch\s+date|deadline|dob|date\s+of\s+birth)\b",
    re.IGNORECASE,
)
_ANALYSIS_SIGNALS = re.compile(
    r"\b(analyze|summarize|compare|count|list\s+all|report|describe|explain|"
    r"how\s+many|how\s+much|total(?:\s+(?:amount|cost|spend|revenue|income))?|"
    r"subtotal|sum\s+of|sums|aggregate|revenue|spent|spend(?:ing)?|earned|earnings|"
    r"income|paid\s+(?:to|for)|pay\s+(?:to|for)|made\s+from|balance|average|avg|mean|"
    r"number\s+of|total\s+number|line\s+count|"
    # Multilingual monetary / aggregation
    r"wie\s*viel(?:e)?|wieviel|summe|gesamt|einnahmen|ausgaben|verdient|"
    r"combien|cu[aá]nto)\b|"
    # CJK literals (no \b — word boundaries don't apply to ideographs)
    r"多少钱|多少|总共|合计|赚了|收入|支出|いくら|合計",
    re.IGNORECASE,
)
_READ_ONLY_DATE_LOOKUP_SIGNALS = re.compile(
    r"\b(next|upcoming|coming\s+up\s+next)\b.*\b(birthday|anniversary|renewal|date)\b|"
    r"\b(birthday|anniversary|renewal|date)\b.*\b(next|upcoming|coming\s+up\s+next)\b",
    re.IGNORECASE,
)
_MULTI_STEP_SIGNALS = re.compile(
    r"\b(then|after\s+that|also|and\s+then|finally|first.*then|step\s+\d|"
    r"next\s+(?:step|phase|task|action)|process|when\s+done|accordingly|"
    r"queue\s+up\s+these|migrate\s+these|for\s+migration)\b",
    re.IGNORECASE,
)
_COMMUNICATION_SIGNALS = re.compile(
    r"\b((?:e-mail|email)(?!\s+address)\s+(?:to\s+)?|"
    r"send\s+(email|message|follow[- ]?up|reminder|note)|"
    r"write\s+(email|message|note)|reply\s+to|forward\s+to|"
    r"ping\b|nudge\b|reach\s+out\b|follow\s+up\s+with\b|check\s+in\s+with\b|"
    r"outbox|outbound|channel|discord|telegram|slack)\b",
    re.IGNORECASE,
)
_INBOX_PROCESSING_SIGNALS = re.compile(
    r"\b(process\s+(the\s+)?inbox|from\s+(the\s+)?inbox|inbox\s+file|"
    r"(take\s+care\s+of|work\s+through)\s+(the\s+)?(?:inbox|incoming)\s+queue|"
    r"(?:incoming|inbox)\s+queue|pending\s+inbox\s+items?|mailbox|"
    r"message\s+backlog|waiting\s+messages?|pending\s+requests?|"
    r"newly\s+arrived\s+requests?|unread\s+requests?|"
    # New: bare imperatives like "handle the next inbox item", "take care of the next message in inbox"
    r"(?:handle|take\s+care\s+of|work|review|address|act\s+on|deal\s+with)\s+(?:the\s+)?"
    r"(?:next|latest|newest|oldest|first|pending|unread|current|following)?\s*"
    r"(?:inbox|inbound|incoming)?\s*"
    r"(?:item|message|note|request|memo|email|letter|mail|envelope|entry)|"
    r"next\s+message\s+in\s+(?:the\s+)?inbox|"
    r"inbound\s+(?:note|message|item|memo)|"
    r"review\s+the\s+next\s+inbound|"
    r"work\s+(?:the\s+)?(?:oldest|newest|next|first|latest|top)\s+(?:inbox\s+)?(?:message|item))\b|"
    # Multilingual inbox (CJK, German, Spanish, French)
    r"受信トレイ|次の受信|収件箱|消息|"
    r"\bposteingang\b|\bbandeja\s+de\s+entrada\b|\bboite\s+(?:de\s+)?reception\b",
    re.IGNORECASE,
)
_PROCESS_LIKE_SIGNALS = re.compile(
    r"\b(process|triage|clear|handle|work(?:\s+(?:through|the|on))?|go\s+through|"
    r"take\s+care\s+of|review|act\s+on|address|deal\s+with|"
    r"queue(?:\s+up)?|migrate)\b",
    re.IGNORECASE,
)
_INBOX_OBJECT_SIGNALS = re.compile(
    r"\b(inbox|inbound|incoming|mailbox|queue|backlog|waiting\s+messages?|pending\s+requests?|"
    r"newly\s+arrived\s+requests?|unread\s+requests?|messages?|requests?|notes?|items?|"
    r"next\s+(?:inbox|inbound|incoming|item|message|note|email))\b|messages/",
    re.IGNORECASE,
)
_QUESTIONISH_LOOKUP_SIGNALS = re.compile(
    r"^\s*(?:what(?:'s|\s+is)|which|who|where|when|can\s+you\s+tell\s+me|"
    r"how\s+(?:much|long|often|many|far|old)|"
    r"quote\s+(?:me|the)|show\s+me|tell\s+me|give\s+me|i\s+need|need\s+the|"
    r"reply\s+with|return\s+(?:the|only))\b",
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
        "exfiltration",
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
    has_lookup = bool(_LOOKUP_SIGNALS.search(task_text))
    has_analysis = bool(_ANALYSIS_SIGNALS.search(task_text))
    has_read_only_date_lookup = bool(_READ_ONLY_DATE_LOOKUP_SIGNALS.search(task_text))
    has_multi_step = bool(_MULTI_STEP_SIGNALS.search(task_text))
    has_communication = bool(_COMMUNICATION_SIGNALS.search(task_text))
    has_inbox_processing = bool(_INBOX_PROCESSING_SIGNALS.search(task_text)) or (
        bool(_PROCESS_LIKE_SIGNALS.search(task_text))
        and bool(_INBOX_OBJECT_SIGNALS.search(task_text))
    )
    is_questionish_lookup = bool(_QUESTIONISH_LOOKUP_SIGNALS.search(task_text))

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

    # Read-only comparative date lookups ("next birthday", "coming up next")
    # are search/lookup tasks, not procedural multi-step workflows.
    if has_read_only_date_lookup and not has_write:
        return TaskClassification(
            task_type="search",
            estimated_steps=15,
            threat_level=threat_level,
            requires_write=False,
            requires_delete=False,
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
    if (has_search or has_lookup) and (not has_write or is_questionish_lookup):
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
