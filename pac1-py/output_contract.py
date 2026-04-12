"""Output-contract extraction and validation for completion messages."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerContract:
    raw_only: bool = False
    one_per_line: bool = False
    sorted_alphabetically: bool = False
    expect_number: bool = False
    expect_email: bool = False
    expect_date_iso: bool = False
    requires_exact_count: bool = False


_RAW_ONLY_RE = re.compile(
    r"\b(?:return|answer|reply|respond)(?:\s+with)?\s+(?:only|just)\b|"
    r"\b(?:plain|raw)\s+text\s+only\b|"
    r"\b(?:names?|address|email|date)\s+only\b",
    re.IGNORECASE,
)
_ONE_PER_LINE_RE = re.compile(
    r"\b(?:one\s+per\s+line|each\s+on\s+its\s+own\s+line|"
    r"newline[- ]separated|line[- ]separated)\b",
    re.IGNORECASE,
)
_SORTED_ALPHA_RE = re.compile(
    r"\b(?:sorted\s+alphabetically|alphabetical(?:ly)?\s+order|a-z)\b",
    re.IGNORECASE,
)
_NUMBER_ONLY_RE = re.compile(
    r"\b(?:answer|return|reply|respond)\s+only\s+(?:with\s+)?(?:the\s+)?number\b|"
    r"\bdigits?\s+only\b|"
    r"\b(?:exact\s+count|count)\s+as\s+an?\s+integer\b|"
    r"\bas\s+an?\s+integer\b|"
    r"\b(?:plain|raw)\s+integer\b|"
    r"\binteger\s+only\b|"
    r"\bnumeric\s+only\b",
    re.IGNORECASE,
)
_EMAIL_ONLY_RE = re.compile(
    r"\b(?:answer|return|reply|respond)\s+only\s+(?:with\s+)?(?:the\s+)?email\b|"
    r"\b(?:return|reply|respond)\s+just\s+the\s+(?:email|address)\b|"
    r"\b(?:email|address)\s+only\b|"
    r"\bjust\s+the\s+(?:email|address)\b",
    re.IGNORECASE,
)
_DATE_ISO_RE = re.compile(
    r"\b(?:yyyy-mm-dd|iso\s*8601|iso\s+date(?:\s+format)?|iso\s+format)\b",
    re.IGNORECASE,
)
_COUNTING_RE = re.compile(r"\b(how\s+many|count|exact\s+count)\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
_DATE_ISO_VALUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PREFIX_RE = re.compile(
    r"^(?:the\s+answer\s+is|answer\s*:|result\s*:|email\s*:|date\s*:|"
    r"name\s*:|address\s*:|the\s+name\s+is|the\s+address\s+is|"
    r"the\s+email\s+is|the\s+date\s+is|the\s+accounts?\s+are|accounts?\s*:)",
    re.IGNORECASE,
)


def extract_answer_contract(task_text: str) -> AnswerContract:
    expect_number = bool(_NUMBER_ONLY_RE.search(task_text))
    expect_email = bool(_EMAIL_ONLY_RE.search(task_text))
    expect_date_iso = bool(_DATE_ISO_RE.search(task_text))
    return AnswerContract(
        raw_only=bool(_RAW_ONLY_RE.search(task_text))
        or expect_number
        or expect_email
        or expect_date_iso,
        one_per_line=bool(_ONE_PER_LINE_RE.search(task_text)),
        sorted_alphabetically=bool(_SORTED_ALPHA_RE.search(task_text)),
        expect_number=expect_number,
        expect_email=expect_email,
        expect_date_iso=expect_date_iso,
        requires_exact_count=bool(_COUNTING_RE.search(task_text)),
    )


def check_answer_contract(task_text: str, message: str) -> list[str]:
    contract = extract_answer_contract(task_text)
    text = message.strip()
    if not text:
        return ["completion message is empty"]

    unmet: list[str] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if contract.raw_only:
        if _PREFIX_RE.search(text):
            unmet.append("answer must be raw value only, without explanatory prefix")
        if text.startswith(("```", "-", "*")):
            unmet.append("answer must not use markdown fences or bullets")

    if contract.expect_number and not re.fullmatch(r"\d+", text):
        unmet.append("answer must contain only digits")

    if contract.expect_email and not _EMAIL_RE.fullmatch(text):
        unmet.append("answer must be a single email address")

    if contract.expect_date_iso and not _DATE_ISO_VALUE_RE.fullmatch(text):
        unmet.append("answer must be in YYYY-MM-DD format")

    if contract.one_per_line:
        if len(lines) < 1:
            unmet.append("answer must contain one item per line")
        elif any(line.startswith(("-", "*")) for line in lines):
            unmet.append("line-based answers must not use bullets")
        elif any(": " in line for line in lines):
            unmet.append("line-based answers must contain raw items only")
        elif "," in text and len(lines) == 1:
            unmet.append("multiple items must be returned one per line, not comma-separated")

    if contract.sorted_alphabetically and len(lines) > 1:
        normalized = [line.casefold() for line in lines]
        if normalized != sorted(normalized):
            unmet.append("line-based answer must be sorted alphabetically")

    return unmet
