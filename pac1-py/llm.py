"""LLM backends: OpenAI-compatible (Nebius, OpenRouter) and Anthropic SDK."""

import json
import os
import random
import re
import time

from pydantic import BaseModel, ValidationError
from settings import SETTINGS

LLM_BACKEND = SETTINGS.llm_backend


def _extract_json(text: str) -> str:
    """Extract JSON object from text that might have markdown fences or preamble."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    if text.startswith("{"):
        return text
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
        return text[start:]
    return text


def _recover_nextstep(raw_json: str, nextstep_type: type[BaseModel]) -> BaseModel:
    """Try to recover a NextStep from malformed JSON by filling missing fields."""
    data = json.loads(raw_json)
    # Qwen3 sometimes uses "name" instead of "tool" in flat tool objects
    if "name" in data and "tool" not in data and "function" not in data:
        data["tool"] = data.pop("name")
    # Qwen3 sometimes wraps params in "parameters": {} envelope
    if "tool" in data and "parameters" in data and "function" not in data:
        params = data.pop("parameters")
        data.update(params)
    # If model output a flat tool object, wrap it in NextStep envelope
    if "tool" in data and "function" not in data:
        data = {
            "current_state": "(auto)",
            "plan_remaining_steps_brief": ["continue"],
            "task_completed": data.get("tool") == "report_completion",
            "function": data,
        }
    # Fix "name" → "tool" inside function object too
    fn = data.get("function", {})
    if "name" in fn and "tool" not in fn:
        fn["tool"] = fn.pop("name")
    # Unwrap "parameters" inside function object too
    if "parameters" in fn and isinstance(fn.get("parameters"), dict):
        params = fn.pop("parameters")
        fn.update(params)
    # Fill missing meta fields
    data.setdefault("current_state", "(auto)")
    data.setdefault("task_completed", False)
    # Fix empty plan_remaining_steps_brief (Qwen3 emits [] when task is done)
    plan = data.get("plan_remaining_steps_brief", [])
    if not plan:
        data["plan_remaining_steps_brief"] = ["(continue)"]
    # Fill missing required fields in ReportTaskCompletion
    fn = data.get("function", {})
    if fn.get("tool") == "report_completion":
        fn.setdefault("completed_steps_laconic", ["(auto)"])
        fn.setdefault("message", "Task completed")
        fn.setdefault("outcome", "OUTCOME_OK")
        # Handle common field name mistakes
        if "outcome_code" in fn and "outcome" not in fn:
            fn["outcome"] = fn.pop("outcome_code")
        data["task_completed"] = True
    return nextstep_type.model_validate(data)


# --- OpenAI-compatible backends (Nebius, OpenRouter) ---

_nebius_usage = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "calls": 0}
_openrouter_usage = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "calls": 0}

_OPENAI_BACKENDS: dict[str, tuple[str, str, dict]] = {
    "nebius": ("https://api.studio.nebius.com/v1/", "NEBIUS_API_KEY", _nebius_usage),
    "openrouter": ("https://openrouter.ai/api/v1", "OPEN_ROUTER_API_KEY", _openrouter_usage),
}
_openai_clients: dict = {}


def get_nebius_usage() -> dict:
    return dict(_nebius_usage)


def get_openrouter_usage() -> dict:
    return dict(_openrouter_usage)


def _call_openai_compat(
    system_static: str,
    system_dynamic: str,
    messages: list[dict],
    model: str,
    nextstep_type: type[BaseModel],
) -> BaseModel:
    """Backend: OpenAI-compatible API (Nebius with json_schema, OpenRouter with json_object)."""
    import openai

    base_url, api_key_env, usage = _OPENAI_BACKENDS[LLM_BACKEND]
    if LLM_BACKEND not in _openai_clients:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"{api_key_env} environment variable is required")
        _openai_clients[LLM_BACKEND] = openai.OpenAI(base_url=base_url, api_key=api_key)
    client = _openai_clients[LLM_BACKEND]

    system = (system_static + "\n\n" + system_dynamic).strip()

    kwargs: dict = dict(model=model, max_tokens=16384)
    kwargs["messages"] = [{"role": "system", "content": system}, *messages]

    schema = nextstep_type.model_json_schema()
    func_prop = schema.get("properties", {}).get("function")
    if func_prop and "anyOf" in func_prop:
        func_prop["discriminator"] = {"propertyName": "tool"}
    strict = LLM_BACKEND != "nebius"  # OpenRouter needs strict; Nebius handles it internally
    kwargs["response_format"] = {
        "type": "json_schema",
        "json_schema": {"name": "next_step", "schema": schema, "strict": strict},
    }
    if LLM_BACKEND == "openrouter":
        kwargs["extra_body"] = {"reasoning": {"effort": "high"}}

    try:
        resp = client.chat.completions.create(**kwargs)
    except openai.APIError as exc:
        raise RuntimeError(f"{LLM_BACKEND} API error: {exc}") from exc

    if not resp.choices:
        raise RuntimeError(f"{LLM_BACKEND} API returned empty choices")
    choice = resp.choices[0]
    if resp.usage:
        usage["input_tokens"] += resp.usage.prompt_tokens
        usage["output_tokens"] += resp.usage.completion_tokens
        details = getattr(resp.usage, "completion_tokens_details", None)
        if details and getattr(details, "reasoning_tokens", None):
            usage["reasoning_tokens"] += details.reasoning_tokens
    usage["calls"] += 1

    reasoning = getattr(choice.message, "reasoning_content", None)
    if reasoning:
        print(
            f"  \x1b[90m[think: {reasoning[:120]}{'...' if len(reasoning) > 120 else ''}]\x1b[0m"
        )

    content = choice.message.content or ""
    if not content.strip():
        raise RuntimeError("empty model response body")
    raw = _extract_json(content)
    try:
        return nextstep_type.model_validate_json(raw)
    except ValidationError:
        return _recover_nextstep(raw, nextstep_type)


# --- Anthropic backend ---

_api_usage = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "calls": 0,
}


def get_api_usage() -> dict:
    return dict(_api_usage)


def get_usage_snapshot() -> dict:
    """Return current token counts for the active backend (for per-task delta computation)."""
    if LLM_BACKEND == "api":
        return dict(_api_usage)
    if LLM_BACKEND == "openrouter":
        return dict(_openrouter_usage)
    return dict(_nebius_usage)


def _call_api(
    system_static: str,
    system_dynamic: str,
    messages: list[dict],
    model: str,
    nextstep_type: type[BaseModel],
) -> BaseModel:
    """Backend: Anthropic API with structured output + adaptive thinking + prompt caching."""
    import anthropic

    if not hasattr(_call_api, "_client"):
        _call_api._client = anthropic.Anthropic()

    static_text = system_static.strip()
    dynamic_text = system_dynamic.strip()

    system_blocks = [{"type": "text", "text": static_text, "cache_control": {"type": "ephemeral"}}]
    if dynamic_text:
        system_blocks.append({"type": "text", "text": dynamic_text})

    kwargs = dict(
        model=model,
        max_tokens=16384,
        system=system_blocks,
        messages=messages,
        output_format=nextstep_type,
    )
    if "haiku" not in model:
        kwargs["thinking"] = {"type": "adaptive"}
    # Retry on 429/5xx with exponential backoff: 1s, 2s, 4s (+ jitter).
    # A single transient error must not drop a task on a 100-task overnight run.
    resp = None
    last_status_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = _call_api._client.messages.parse(**kwargs)
            break
        except anthropic.APIStatusError as exc:
            status = getattr(exc, "status_code", None)
            if (status == 429 or (status is not None and status >= 500)) and attempt < 2:
                last_status_exc = exc
                time.sleep((2**attempt) + random.random())
                continue
            raise RuntimeError(f"Anthropic API error: {exc}") from exc
        except anthropic.APIError as exc:
            raise RuntimeError(f"Anthropic API error: {exc}") from exc
    if resp is None:
        raise RuntimeError(
            f"Anthropic API error after 3 attempts: {last_status_exc}"
        ) from last_status_exc
    _api_usage["input_tokens"] += resp.usage.input_tokens
    _api_usage["output_tokens"] += resp.usage.output_tokens
    _api_usage["cache_creation_input_tokens"] += (
        getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
    )
    _api_usage["cache_read_input_tokens"] += getattr(resp.usage, "cache_read_input_tokens", 0) or 0
    _api_usage["calls"] += 1
    if resp.parsed_output is None:
        raise RuntimeError("Anthropic structured output: no parseable text block in response")
    return resp.parsed_output


def call_llm(
    system_static: str,
    system_dynamic: str,
    messages: list[dict],
    model: str,
    nextstep_type: type[BaseModel],
) -> BaseModel:
    if LLM_BACKEND == "api":
        return _call_api(system_static, system_dynamic, messages, model, nextstep_type)
    return _call_openai_compat(system_static, system_dynamic, messages, model, nextstep_type)
