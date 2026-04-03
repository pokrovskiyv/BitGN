import json
import os
import re
import time
from typing import Annotated, Literal

from annotated_types import Ge, Le, MaxLen, MinLen
from bitgn.vm.mini_connect import MiniRuntimeClientSync
from bitgn.vm.mini_pb2 import (
    AnswerRequest,
    DeleteRequest,
    ListRequest,
    OutlineRequest,
    ReadRequest,
    SearchRequest,
    WriteRequest,
)
from connectrpc.errors import ConnectError
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field

# ── Pydantic models (shared by both backends) ──────────────────────────────


class ReportTaskCompletion(BaseModel):
    tool: Literal["report_completion"]
    completed_steps_laconic: list[str]
    answer: str
    grounding_refs: list[str] = Field(default_factory=list)
    code: Literal["completed", "failed"]


class Req_Tree(BaseModel):
    tool: Literal["tree"]
    path: str = Field(..., description="folder path")


class Req_Search(BaseModel):
    tool: Literal["search"]
    pattern: str
    count: Annotated[int, Ge(1), Le(10)] = 5
    path: str = "/"


class Req_List(BaseModel):
    tool: Literal["list"]
    path: str


class Req_Read(BaseModel):
    tool: Literal["read"]
    path: str


class Req_Write(BaseModel):
    tool: Literal["write"]
    path: str
    content: str


class Req_Delete(BaseModel):
    tool: Literal["delete"]
    path: str


class NextStep(BaseModel):
    current_state: str
    plan_remaining_steps_brief: Annotated[list[str], MinLen(1), MaxLen(5)] = Field(
        ...,
        description="explain your thoughts on how to accomplish - what steps to execute",
    )
    task_completed: bool
    function: (
        ReportTaskCompletion | Req_Tree | Req_Search | Req_List | Req_Read | Req_Write | Req_Delete
    ) = Field(..., description="execute first remaining step")


# ── Shared config ───────────────────────────────────────────────────────────


system_prompt = """
You are a personal business assistant, helpful and precise.

- always start by discovering available information by running root outline.
- always read `AGENTS.md` at the start
- always reference (ground) in final response all files that contributed to the answer
- Clearly report when tasks are done
"""

LLM_BACKEND = os.getenv("LLM_BACKEND", "nebius")

CLI_RED = "\x1b[31m"
CLI_GREEN = "\x1b[32m"
CLI_CLR = "\x1b[0m"
CLI_BLUE = "\x1b[34m"


# ── LLM call (the only part that differs) ──────────────────────────────────


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
        return text[start:]
    return text


def _call_nebius(system: str, messages: list[dict], model: str) -> NextStep:
    """Backend: Nebius AI Studio (OpenAI-compatible) with structured output."""
    import openai

    if not hasattr(_call_nebius, "_client"):
        api_key = os.getenv("NEBIUS_API_KEY")
        if not api_key:
            raise RuntimeError("NEBIUS_API_KEY environment variable is required")
        _call_nebius._client = openai.OpenAI(
            base_url="https://api.studio.nebius.com/v1/",
            api_key=api_key,
        )

    schema = NextStep.model_json_schema()
    try:
        resp = _call_nebius._client.chat.completions.create(
            model=model,
            max_tokens=16384,
            messages=[{"role": "system", "content": system.strip()}, *messages],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "next_step", "schema": schema, "strict": False},
            },
        )
    except openai.APIError as exc:
        raise RuntimeError(f"Nebius API error: {exc}") from exc

    if not resp.choices:
        raise RuntimeError("Nebius API returned empty choices")
    raw = resp.choices[0].message.content or ""
    return NextStep.model_validate_json(_extract_json(raw))


def _call_api(system: str, messages: list[dict], model: str) -> NextStep:
    """Backend: Anthropic API with structured output + adaptive thinking."""
    import anthropic

    if not hasattr(_call_api, "_client"):
        _call_api._client = anthropic.Anthropic()

    resp = _call_api._client.messages.parse(
        model=model,
        max_tokens=16384,
        system=system.strip(),
        messages=messages,
        output_format=NextStep,
        thinking={"type": "adaptive"},
    )
    return resp.parsed_output


def call_llm(system: str, messages: list[dict], model: str) -> NextStep:
    """Route to the active backend."""
    if LLM_BACKEND == "api":
        return _call_api(system, messages, model)
    return _call_nebius(system, messages, model)


# ── Dispatch (shared) ──────────────────────────────────────────────────────


def dispatch(r: MiniRuntimeClientSync, cmd: BaseModel):
    if isinstance(cmd, Req_Tree):
        return r.outline(OutlineRequest(path=cmd.path))
    if isinstance(cmd, Req_Search):
        return r.search(SearchRequest(path=cmd.path, pattern=cmd.pattern, count=cmd.count))
    if isinstance(cmd, Req_List):
        return r.list(ListRequest(path=cmd.path))
    if isinstance(cmd, Req_Read):
        return r.read(ReadRequest(path=cmd.path))
    if isinstance(cmd, Req_Write):
        return r.write(WriteRequest(path=cmd.path, content=cmd.content))
    if isinstance(cmd, Req_Delete):
        return r.delete(DeleteRequest(path=cmd.path))
    if isinstance(cmd, ReportTaskCompletion):
        return r.answer(AnswerRequest(answer=cmd.answer, refs=cmd.grounding_refs))

    raise ValueError(f"Unknown command: {cmd}")


# ── Agent loop (shared) ───────────────────────────────────────────────────


def run_agent(model: str, harness_url: str, task_text: str):
    vm = MiniRuntimeClientSync(harness_url)

    messages = [
        {"role": "user", "content": task_text},
    ]

    for i in range(30):
        step = f"step_{i + 1}"
        print(f"Next {step}... ", end="")

        started = time.time()
        job = call_llm(system_prompt, messages, model)
        elapsed_ms = int((time.time() - started) * 1000)

        print(job.plan_remaining_steps_brief[0], f"({elapsed_ms} ms)\n  {job.function}")

        messages.append(
            {
                "role": "assistant",
                "content": job.model_dump_json(),
            }
        )

        try:
            result = dispatch(vm, job.function)
            mappe = MessageToDict(result)
            txt = json.dumps(mappe, indent=2)
            print(f"{CLI_GREEN}OUT{CLI_CLR}: {txt}")
        except ConnectError as e:
            txt = str(e.message)
            print(f"{CLI_RED}ERR {e.code}: {e.message}{CLI_CLR}")

        if isinstance(job.function, ReportTaskCompletion):
            print(f"{CLI_GREEN}agent {job.function.code}{CLI_CLR}. Summary:")
            for s in job.function.completed_steps_laconic:
                print(f"- {s}")

            print(f"\n{CLI_BLUE}AGENT ANSWER: {job.function.answer}{CLI_CLR}")
            if job.function.grounding_refs:
                for ref in job.function.grounding_refs:
                    print(f"- {CLI_BLUE}{ref}{CLI_CLR}")
            break

        messages.append({"role": "user", "content": txt})
