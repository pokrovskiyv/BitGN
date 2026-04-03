"""ISC-style atomic criteria extraction for pre-submission verification."""

from __future__ import annotations

import re

from verify import WriteTracker

_WRITE_RE = re.compile(
    r"\b(?:create|write|add|save|store|move|copy|place|put)"
    r"\s+(?:a\s+|the\s+|an?\s+|new\s+|it\s+)?(?:file\s+|note\s+|entry\s+|summary\s+)?"
    r"(?:called\s+|named\s+|to\s+|in\s+|at\s+|into\s+|under\s+)?"
    r"['\"`]?([/\w][\w./-]+\.\w+)",
    re.IGNORECASE,
)
_DELETE_RE = re.compile(
    r"\b(?:delete|remove|erase)\s+(?:the\s+|a\s+)?(?:file\s+)?"
    r"['\"`]?([/\w][\w./-]+\.\w+)",
    re.IGNORECASE,
)


def extract_criteria(task_text: str) -> list[tuple[str, str]]:
    """Extract verifiable (kind, target_path) pairs from task instruction text."""
    criteria: list[tuple[str, str]] = []
    for m in _WRITE_RE.finditer(task_text):
        criteria.append(("write", m.group(1)))
    for m in _DELETE_RE.finditer(task_text):
        criteria.append(("delete", m.group(1)))
    return criteria


def check_criteria(criteria: list[tuple[str, str]], tracker: WriteTracker) -> list[str]:
    """Return descriptions of unmet criteria based on tracker state."""
    unmet: list[str] = []
    written = {p for p in tracker._writes}
    deleted = set(tracker.deleted_paths())
    for kind, target in criteria:
        if kind == "write":
            if not any(w.endswith(target) or w.endswith("/" + target) for w in written):
                unmet.append(f"expected write to '{target}' not found")
        elif kind == "delete":
            if not any(d.endswith(target) or d.endswith("/" + target) for d in deleted):
                unmet.append(f"expected delete of '{target}' not found")
    return unmet
