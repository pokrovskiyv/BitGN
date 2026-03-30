"""LLM call backends and JSON extraction helpers.

Extracted from agent_loop.py to keep each module under 200 lines.
Provides _call_cli (free via Claude Code subscription) and _call_api
(Anthropic SDK with adaptive thinking).
"""

import json
import os
import re
import subprocess

from pydantic import BaseModel

LLM_BACKEND = os.getenv("LLM_BACKEND", "cli")


def _format_history(messages: list[dict]) -> str:
    parts = []
    for msg in messages:
        role = msg["role"].upper()
        content = msg["content"] if isinstance(msg["content"], str) else json.dumps(msg["content"])
        parts.append(f"[{role}]:\n{content}")
    return "\n\n".join(parts)


def _extract_json(text: str) -> str:
    """Extract JSON object from text that might have markdown fences or preamble."""
    text = text.strip()
    # Phase 1: markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Phase 2: direct JSON
    if text.startswith("{"):
        return text
    # Phase 3: find balanced JSON object (string-aware brace counting)
    start = text.find("{")
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return text[start:]  # unclosed fallback
    return text


# Regex to strip hook-injected insight blocks from claude -p output
_INSIGHT_BLOCK_RE = re.compile(r"★ Insight ─+.*?─{5,}", re.DOTALL)


def _call_cli(
    system: str, messages: list[dict], model: str, nextstep_type: type[BaseModel]
) -> BaseModel:
    """Backend: claude -p (free via Claude Code subscription)."""
    schema = json.dumps(nextstep_type.model_json_schema(), indent=2)
    conversation = _format_history(messages)
    prompt = f"""{conversation}

Respond with a single valid JSON object matching this schema. No markdown fences, no explanation — ONLY the raw JSON object:
{schema}"""

    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--max-turns",
        "1",
        "--system-prompt",
        system.strip(),
    ]
    if model:
        cmd.extend(["--model", model])

    result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=240)
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed: {result.stderr}")

    response = json.loads(result.stdout)
    raw_text = response.get("result", "")
    raw_text = _INSIGHT_BLOCK_RE.sub("", raw_text)
    return nextstep_type.model_validate_json(_extract_json(raw_text))


def _call_api(
    system: str, messages: list[dict], model: str, nextstep_type: type[BaseModel]
) -> BaseModel:
    """Backend: Anthropic API with structured output + adaptive thinking."""
    import anthropic

    if not hasattr(_call_api, "_client"):
        _call_api._client = anthropic.Anthropic()

    resp = _call_api._client.messages.parse(
        model=model,
        max_tokens=16384,
        system=system.strip(),
        messages=messages,
        output_format=nextstep_type,
        thinking={"type": "adaptive"},
    )
    return resp.parsed_output


def call_llm(
    system: str, messages: list[dict], model: str, nextstep_type: type[BaseModel]
) -> BaseModel:
    if LLM_BACKEND == "api":
        return _call_api(system, messages, model, nextstep_type)
    return _call_cli(system, messages, model, nextstep_type)
