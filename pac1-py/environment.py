"""Lightweight environment model extracted from AGENTS.md and tree output.

Provides structured constraints for strategy selection and action gating,
replacing hardcoded sensitive path sets with dynamic extraction.
"""

import re
from dataclasses import dataclass, field

# ── Extraction patterns ──────────────────────────────────────────────────

_SENSITIVE_PATH_PATS = [
    re.compile(
        r"(?:do\s+not|never|don'?t|must\s+not)\s+"
        r"(?:modify|edit|change|delete|write\s+to|alter)\s+"
        r"[`'\"]?([^\s`'\"]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"[`'\"]([^\s`'\"]+)[`'\"]?\s+(?:is|are)\s+(?:read[- ]only|protected|immutable)",
        re.IGNORECASE,
    ),
]

_CONSTRAINT_PAT = re.compile(
    r"(?:you\s+must|always|never|do\s+not|required\s+to)\s+(.{10,80}?)(?:\.|$)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class EnvironmentModel:
    """Structured representation of AGENTS.md rules and VM layout."""

    sensitive_paths: frozenset[str] = frozenset({"AGENTS.md"})
    constraints: tuple[str, ...] = ()


def extract_environment(agents_md: str) -> EnvironmentModel:
    """Parse AGENTS.md into structured constraints.

    Always includes AGENTS.md as a baseline sensitive path.
    Caps extracted constraints at 10 to prevent prompt bloat.
    """
    sensitive: set[str] = {"AGENTS.md"}

    for pat in _SENSITIVE_PATH_PATS:
        for match in pat.finditer(agents_md):
            path = match.group(1).strip(".,;:")
            if path and len(path) > 1:
                sensitive.add(path)

    constraints: list[str] = []
    for match in _CONSTRAINT_PAT.finditer(agents_md):
        constraint = match.group(0).strip()
        if constraint and len(constraint) > 15 and constraint not in constraints:
            constraints.append(constraint)

    return EnvironmentModel(
        sensitive_paths=frozenset(sensitive),
        constraints=tuple(constraints[:10]),
    )
