"""Second Opinion — pre-completion outcome verifier.

Spawns a one-shot LLM call with a "verifier" role to check whether the
agent chose the correct outcome before report_completion is dispatched.
Uses a dedicated Anthropic client (Haiku) independent of the main agent's LLM backend.
"""

import os
from pathlib import Path

from pydantic import BaseModel

from classify import TaskClassification

VERIFIER_MODEL = os.getenv("VERIFIER_MODEL", "claude-haiku-4-5-20251001")

_WORKSPACE = Path(__file__).parent / "workspace"
_client = None


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


def _load_verifier_prompt() -> str:
    path = _WORKSPACE / "prompts" / "fragments" / "verifier.md"
    return path.read_text() if path.exists() else ""


def needs_second_opinion(classification: TaskClassification, outcome: str) -> bool:
    """Decide whether to spawn a verifier agent for this completion."""
    if classification.task_type == "inbox_processing":
        return True
    if outcome == "OUTCOME_DENIED_SECURITY":
        return True
    if outcome == "OUTCOME_NONE_CLARIFICATION":
        return True
    return False


def get_second_opinion(
    task_text: str,
    outcome: str,
    completion_message: str,
    recent_evidence: list[str],
    model: str,
) -> VerifierVerdict:
    """Ask an independent verifier whether the proposed outcome is correct."""
    verifier_prompt = _load_verifier_prompt()
    if not verifier_prompt:
        return VerifierVerdict(agree=True, reasoning="verifier prompt missing")

    evidence_block = "\n---\n".join(recent_evidence[-4:]) if recent_evidence else "(none)"

    user_content = (
        f"TASK INSTRUCTION:\n{task_text}\n\n"
        f"PROPOSED OUTCOME: {outcome}\n"
        f"AGENT MESSAGE: {completion_message}\n\n"
        f"RECENT TOOL OUTPUTS (what the agent saw):\n{evidence_block}\n\n"
        f"Do you AGREE or DISAGREE with the proposed outcome? "
        f"If you disagree, suggest the correct outcome."
    )

    try:
        client = _get_client()
        resp = client.messages.parse(
            model=VERIFIER_MODEL,
            max_tokens=1024,
            system=[{"type": "text", "text": verifier_prompt}],
            messages=[{"role": "user", "content": user_content}],
            output_format=VerifierVerdict,
        )
        if resp.parsed_output is None:
            return VerifierVerdict(agree=True, reasoning="verifier returned no output")
        return resp.parsed_output
    except Exception as exc:
        # For OUTCOME_OK: broken verifier should NOT auto-approve — force reconsideration
        if outcome == "OUTCOME_OK":
            return VerifierVerdict(
                agree=False,
                reasoning=f"verifier unavailable ({exc}). Re-examine your outcome.",
                suggested_outcome="OUTCOME_DENIED_SECURITY",
            )
        return VerifierVerdict(agree=True, reasoning=f"verifier error: {exc}")
