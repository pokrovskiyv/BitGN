"""Second Opinion — pre-completion outcome verifier.

Spawns a one-shot LLM call with a "verifier" role to check whether the
agent chose the correct outcome before report_completion is dispatched.
Uses a dedicated Anthropic client independent of the main agent's LLM backend.
"""

import random
import re
import time
from pathlib import Path

from pydantic import BaseModel

from classify import TaskClassification
from settings import SETTINGS

VERIFIER_MODEL = SETTINGS.verifier_model
VERIFIER_POLICY = SETTINGS.verifier_policy

_WORKSPACE = Path(__file__).parent / "workspace"
_client = None
_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}


class VerifierVerdict(BaseModel):
    agree: bool
    reasoning: str
    suggested_outcome: str | None = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def get_verifier_usage() -> dict:
    return dict(_usage)


def _load_verifier_prompt() -> str:
    path = _WORKSPACE / "prompts" / "fragments" / "verifier.md"
    return path.read_text() if path.exists() else ""


_INBOXISH_RE = re.compile(r"\b(inbox|queue|pending\s+items|incoming\s+queue)\b", re.IGNORECASE)


def needs_second_opinion(
    classification: TaskClassification,
    outcome: str,
    task_text: str,
) -> bool:
    """Decide whether to spawn a verifier agent for this completion."""
    if VERIFIER_POLICY == "off":
        return False
    if VERIFIER_POLICY == "always":
        return True
    # Keep the verifier trigger generic so it transfers to unseen task families.
    if outcome != "OUTCOME_OK":
        return True
    if classification.threat_level != "none":
        return True
    if classification.requires_delete:
        return True
    if classification.task_type in {"communication", "inbox_processing", "multi_step"}:
        return True
    if _INBOXISH_RE.search(task_text):
        return True
    return False


def get_second_opinion(
    task_text: str,
    outcome: str,
    completion_message: str,
    recent_evidence: list[str],
    available_tools: tuple[str, ...],
    _primary_model: str,
) -> VerifierVerdict:
    """Ask an independent verifier whether the proposed outcome is correct."""
    verifier_prompt = _load_verifier_prompt()
    if not verifier_prompt:
        return VerifierVerdict(agree=True, reasoning="verifier prompt missing")

    evidence_block = "\n---\n".join(recent_evidence[-6:]) if recent_evidence else "(none)"
    tool_surface = ", ".join(t for t in available_tools if t != "report_completion") or "(unknown)"

    user_content = (
        f"TASK INSTRUCTION:\n{task_text}\n\n"
        f"RUNTIME TOOL SURFACE:\n{tool_surface}\n\n"
        f"PROPOSED OUTCOME: {outcome}\n"
        f"AGENT MESSAGE: {completion_message}\n\n"
        f"RECENT TOOL OUTPUTS (what the agent saw):\n{evidence_block}\n\n"
        f"Do you AGREE or DISAGREE with the proposed outcome? "
        f"If you disagree, suggest the correct outcome."
    )

    try:
        import anthropic

        client = _get_client()
        parse_kwargs = dict(
            model=VERIFIER_MODEL,
            max_tokens=1024,
            system=[{"type": "text", "text": verifier_prompt}],
            messages=[{"role": "user", "content": user_content}],
            output_format=VerifierVerdict,
        )
        # Retry on 429/5xx with exponential backoff: 1s, 2s, 4s (+ jitter).
        resp = None
        last_status_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.messages.parse(**parse_kwargs)
                break
            except anthropic.APIStatusError as exc:
                status = getattr(exc, "status_code", None)
                if (status == 429 or (status is not None and status >= 500)) and attempt < 2:
                    last_status_exc = exc
                    time.sleep((2**attempt) + random.random())
                    continue
                raise
        if resp is None:
            return VerifierVerdict(
                agree=True, reasoning=f"verifier retries exhausted ({last_status_exc})"
            )
        _usage["input_tokens"] += getattr(resp.usage, "input_tokens", 0) or 0
        _usage["output_tokens"] += getattr(resp.usage, "output_tokens", 0) or 0
        _usage["calls"] += 1
        if resp.parsed_output is None:
            return VerifierVerdict(agree=True, reasoning="verifier returned no output")
        return resp.parsed_output
    except Exception as exc:
        # Broken verifier → skip (neutral). The agent already passed
        # pre_completion_gate + evidence challenge; don't override its decision.
        return VerifierVerdict(agree=True, reasoning=f"verifier unavailable ({exc})")
