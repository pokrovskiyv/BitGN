import json
import os
import re
import shlex
import subprocess
import time
from typing import Annotated, Literal

from annotated_types import Ge, Le, MaxLen, MinLen
from bitgn.vm.pcm_connect import PcmRuntimeClientSync
from bitgn.vm.pcm_pb2 import (
    AnswerRequest,
    ContextRequest,
    DeleteRequest,
    FindRequest,
    ListRequest,
    MkDirRequest,
    MoveRequest,
    Outcome,
    ReadRequest,
    SearchRequest,
    TreeRequest,
    WriteRequest,
)
from connectrpc.errors import ConnectError
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field

from classify import classify_task
from defend import scan_content, wrap_tool_output
from strategy import decide_strategy
from verify import StagnationDetector, WriteTracker, action_gate_message

# ── Pydantic models (shared by both backends) ──────────────────────────────


class ReportTaskCompletion(BaseModel):
    tool: Literal["report_completion"]
    completed_steps_laconic: list[str]
    message: str
    grounding_refs: list[str] = Field(default_factory=list)
    outcome: Literal[
        "OUTCOME_OK",
        "OUTCOME_DENIED_SECURITY",
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_NONE_UNSUPPORTED",
        "OUTCOME_ERR_INTERNAL",
    ]


class Req_Tree(BaseModel):
    tool: Literal["tree"]
    level: int = Field(2, description="max tree depth, 0 means unlimited")
    root: str = Field("", description="tree root, empty means repository root")


class Req_Find(BaseModel):
    tool: Literal["find"]
    name: str
    root: str = "/"
    kind: Literal["all", "files", "dirs"] = "all"
    limit: Annotated[int, Ge(1), Le(20)] = 10


class Req_Search(BaseModel):
    tool: Literal["search"]
    pattern: str
    limit: Annotated[int, Ge(1), Le(20)] = 10
    root: str = "/"


class Req_List(BaseModel):
    tool: Literal["list"]
    path: str = "/"


class Req_Read(BaseModel):
    tool: Literal["read"]
    path: str
    number: bool = Field(False, description="return 1-based line numbers")
    start_line: Annotated[int, Ge(0)] = Field(
        0, description="1-based inclusive linum; 0 == from the first line"
    )
    end_line: Annotated[int, Ge(0)] = Field(
        0, description="1-based inclusive linum; 0 == through the last line"
    )


class Req_Context(BaseModel):
    tool: Literal["context"]


class Req_Write(BaseModel):
    tool: Literal["write"]
    path: str
    content: str
    start_line: Annotated[int, Ge(0)] = Field(
        0,
        description="1-based inclusive line number; 0 keeps whole-file overwrite behavior",
    )
    end_line: Annotated[int, Ge(0)] = Field(
        0,
        description="1-based inclusive line number; 0 means through the last line for ranged writes",
    )


class Req_Delete(BaseModel):
    tool: Literal["delete"]
    path: str


class Req_MkDir(BaseModel):
    tool: Literal["mkdir"]
    path: str


class Req_Move(BaseModel):
    tool: Literal["move"]
    from_name: str
    to_name: str


class NextStep(BaseModel):
    current_state: str
    plan_remaining_steps_brief: Annotated[list[str], MinLen(1), MaxLen(5)] = Field(
        ...,
        description="briefly explain the next useful steps",
    )
    task_completed: bool
    function: (
        ReportTaskCompletion
        | Req_Context
        | Req_Tree
        | Req_Find
        | Req_Search
        | Req_List
        | Req_Read
        | Req_Write
        | Req_Delete
        | Req_MkDir
        | Req_Move
    ) = Field(..., description="execute the first remaining step")


# ── Shared config ───────────────────────────────────────────────────────────


NEXTSTEP_SCHEMA = json.dumps(NextStep.model_json_schema(), indent=2)

# LLM_BACKEND: "cli" (free, claude -p) or "api" (Anthropic SDK)
LLM_BACKEND = os.getenv("LLM_BACKEND", "cli")

CLI_RED = "\x1b[31m"
CLI_GREEN = "\x1b[32m"
CLI_CLR = "\x1b[0m"
CLI_BLUE = "\x1b[34m"
CLI_YELLOW = "\x1b[33m"

OUTCOME_BY_NAME = {
    "OUTCOME_OK": Outcome.OUTCOME_OK,
    "OUTCOME_DENIED_SECURITY": Outcome.OUTCOME_DENIED_SECURITY,
    "OUTCOME_NONE_CLARIFICATION": Outcome.OUTCOME_NONE_CLARIFICATION,
    "OUTCOME_NONE_UNSUPPORTED": Outcome.OUTCOME_NONE_UNSUPPORTED,
    "OUTCOME_ERR_INTERNAL": Outcome.OUTCOME_ERR_INTERNAL,
}


# ── LLM call (the only part that differs) ──────────────────────────────────


def _format_history(messages: list[dict]) -> str:
    """Format conversation history into a single prompt for claude -p."""
    parts = []
    for msg in messages:
        role = msg["role"].upper()
        content = msg["content"] if isinstance(msg["content"], str) else json.dumps(msg["content"])
        parts.append(f"[{role}]:\n{content}")
    return "\n\n".join(parts)


def _strip_insight_blocks(text: str) -> str:
    """Strip Claude Code hook-injected insight blocks from subprocess responses.

    The user's explanatory mode sessionStart hook injects blocks of the form:
        `★ Insight ─────...─────`
        [content]
        `─────...─────`
    into claude -p subprocess responses. These non-JSON lines break JSON extraction
    and cause context loss when the retry loop fires.
    """
    return re.sub(r"`★ Insight\s*[─\-]+`.*?`[─\-]+`\n?", "", text, flags=re.DOTALL).strip()


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


def _call_cli(system: str, messages: list[dict], model: str) -> NextStep:
    """Backend: claude -p (free via Claude Code subscription)."""
    conversation = _format_history(messages)

    prompt = f"""{conversation}

Respond with a single valid JSON object matching this schema. No markdown fences, no explanation — ONLY the raw JSON object:
{NEXTSTEP_SCHEMA}"""

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

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed: {result.stderr}")

    response = json.loads(result.stdout)
    raw_text = _strip_insight_blocks(response.get("result", ""))

    return NextStep.model_validate_json(_extract_json(raw_text))


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
    return _call_cli(system, messages, model)


# ── Output formatting (shared) ─────────────────────────────────────────────


def _format_tree_entry(entry, prefix: str = "", is_last: bool = True) -> list[str]:
    branch = "└── " if is_last else "├── "
    lines = [f"{prefix}{branch}{entry.name}"]
    child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
    children = list(entry.children)
    for idx, child in enumerate(children):
        lines.extend(
            _format_tree_entry(child, prefix=child_prefix, is_last=idx == len(children) - 1)
        )
    return lines


def _render_command(command: str, body: str) -> str:
    return f"{command}\n{body}"


def _format_tree_response(cmd: Req_Tree, result) -> str:
    root = result.root
    if not root.name:
        body = "."
    else:
        lines = [root.name]
        children = list(root.children)
        for idx, child in enumerate(children):
            lines.extend(_format_tree_entry(child, is_last=idx == len(children) - 1))
        body = "\n".join(lines)
    root_arg = cmd.root or "/"
    level_arg = f" -L {cmd.level}" if cmd.level > 0 else ""
    return _render_command(f"tree{level_arg} {root_arg}", body)


def _format_list_response(cmd: Req_List, result) -> str:
    if not result.entries:
        body = "."
    else:
        body = "\n".join(
            f"{entry.name}/" if entry.is_dir else entry.name for entry in result.entries
        )
    return _render_command(f"ls {cmd.path}", body)


def _format_read_response(cmd: Req_Read, result) -> str:
    if cmd.start_line > 0 or cmd.end_line > 0:
        start = cmd.start_line if cmd.start_line > 0 else 1
        end = cmd.end_line if cmd.end_line > 0 else "$"
        command = f"sed -n '{start},{end}p' {cmd.path}"
    elif cmd.number:
        command = f"cat -n {cmd.path}"
    else:
        command = f"cat {cmd.path}"
    return _render_command(command, result.content)


def _format_search_response(cmd: Req_Search, result) -> str:
    root = shlex.quote(cmd.root or "/")
    pattern = shlex.quote(cmd.pattern)
    body = "\n".join(f"{match.path}:{match.line}:{match.line_text}" for match in result.matches)
    return _render_command(f"rg -n --no-heading -e {pattern} {root}", body)


def _format_result(cmd: BaseModel, result) -> str:
    if result is None:
        return "{}"
    if isinstance(cmd, Req_Tree):
        return _format_tree_response(cmd, result)
    if isinstance(cmd, Req_List):
        return _format_list_response(cmd, result)
    if isinstance(cmd, Req_Read):
        return _format_read_response(cmd, result)
    if isinstance(cmd, Req_Search):
        return _format_search_response(cmd, result)
    if isinstance(cmd, Req_Delete):
        return _render_command(f"rm {cmd.path}", f"deleted: {cmd.path}")
    return json.dumps(MessageToDict(result), indent=2)


# ── Dispatch (shared) ──────────────────────────────────────────────────────


def dispatch(vm: PcmRuntimeClientSync, cmd: BaseModel):
    if isinstance(cmd, Req_Context):
        return vm.context(ContextRequest())
    if isinstance(cmd, Req_Tree):
        return vm.tree(TreeRequest(root=cmd.root, level=cmd.level))
    if isinstance(cmd, Req_Find):
        return vm.find(
            FindRequest(
                root=cmd.root,
                name=cmd.name,
                type={"all": 0, "files": 1, "dirs": 2}[cmd.kind],
                limit=cmd.limit,
            )
        )
    if isinstance(cmd, Req_Search):
        return vm.search(SearchRequest(root=cmd.root, pattern=cmd.pattern, limit=cmd.limit))
    if isinstance(cmd, Req_List):
        return vm.list(ListRequest(name=cmd.path))
    if isinstance(cmd, Req_Read):
        return vm.read(
            ReadRequest(
                path=cmd.path,
                number=cmd.number,
                start_line=cmd.start_line,
                end_line=cmd.end_line,
            )
        )
    if isinstance(cmd, Req_Write):
        return vm.write(
            WriteRequest(
                path=cmd.path,
                content=cmd.content,
                start_line=cmd.start_line,
                end_line=cmd.end_line,
            )
        )
    if isinstance(cmd, Req_Delete):
        return vm.delete(DeleteRequest(path=cmd.path))
    if isinstance(cmd, Req_MkDir):
        return vm.mk_dir(MkDirRequest(path=cmd.path))
    if isinstance(cmd, Req_Move):
        return vm.move(MoveRequest(from_name=cmd.from_name, to_name=cmd.to_name))
    if isinstance(cmd, ReportTaskCompletion):
        return vm.answer(
            AnswerRequest(
                message=cmd.message,
                outcome=OUTCOME_BY_NAME[cmd.outcome],
                refs=cmd.grounding_refs,
            )
        )

    raise ValueError(f"Unknown command: {cmd}")


# ── Agent loop (shared) ───────────────────────────────────────────────────


def run_agent(model: str, harness_url: str, task_text: str) -> str | None:
    vm = PcmRuntimeClientSync(harness_url)

    # ── PERCEIVE: gather grounding context ────────────────────────────
    messages: list[dict] = []
    must = [
        Req_Tree(level=2, tool="tree", root="/"),
        Req_Read(path="AGENTS.md", tool="read"),
        Req_Context(tool="context"),
    ]
    for c in must:
        result = dispatch(vm, c)
        formatted = _format_result(c, result)
        print(f"{CLI_GREEN}AUTO{CLI_CLR}: {formatted}")
        messages.append({"role": "user", "content": wrap_tool_output(formatted)})

    # ── CLASSIFY + DECIDE ─────────────────────────────────────────────
    task_warnings = scan_content(task_text)
    classification = classify_task(task_text, task_warnings)
    strategy = decide_strategy(classification)

    print(
        f"{CLI_BLUE}CLASSIFY{CLI_CLR}: {classification.task_type} "
        f"threat={classification.threat_level} "
        f"max_steps={strategy.max_steps} "
        f"posture={strategy.security_posture}"
    )

    messages.append({"role": "user", "content": task_text})

    # ── RUN: enhanced agent loop ──────────────────────────────────────
    tracker = WriteTracker()
    stagnation = StagnationDetector()

    for i in range(strategy.max_steps):
        step = f"step_{i + 1}"
        print(f"Next {step}... ", end="")

        started = time.time()
        job = None
        for attempt in range(3):
            try:
                retry_msgs = messages
                if attempt > 0:
                    retry_msgs = messages + [
                        {
                            "role": "user",
                            "content": (
                                "FORMAT CORRECTION: Your previous response was not valid JSON. "
                                'You MUST respond with EXACTLY this structure (action goes INSIDE "function", '
                                "not at the top level):\n"
                                "{\n"
                                '  "current_state": "<one sentence>",\n'
                                '  "plan_remaining_steps_brief": ["<next step>"],\n'
                                '  "task_completed": false,\n'
                                '  "function": { <your action object with tool field here> }\n'
                                "}\n"
                                "No markdown code fences. No explanation. Only the raw JSON object."
                            ),
                        }
                    ]
                job = call_llm(strategy.system_prompt, retry_msgs, model)
                break
            except Exception as exc:
                print(f"LLM parse error (attempt {attempt + 1}/3): {exc}")
                if attempt == 2:
                    raise
        elapsed_ms = int((time.time() - started) * 1000)

        print(job.plan_remaining_steps_brief[0], f"({elapsed_ms} ms)\n  {job.function}")

        messages.append(
            {
                "role": "assistant",
                "content": job.model_dump_json(),
            }
        )

        cmd = job.function

        # ── DEFEND: action-gate destructive operations ────────────
        if isinstance(cmd, (Req_Delete, Req_Move)):
            gate_msg = action_gate_message(
                cmd.tool, getattr(cmd, "path", getattr(cmd, "from_name", ""))
            )
            print(f"{CLI_YELLOW}GATE{CLI_CLR}: {gate_msg}")
            messages.append({"role": "user", "content": gate_msg})

        # ── DISPATCH ──────────────────────────────────────────────
        try:
            result = dispatch(vm, cmd)
            txt = _format_result(cmd, result)
            print(f"{CLI_GREEN}OUT{CLI_CLR}: {txt}")
        except ConnectError as exc:
            txt = str(exc.message)
            print(f"{CLI_RED}ERR {exc.code}: {exc.message}{CLI_CLR}")
            # Add recovery hint
            if "not_found" in txt.lower():
                txt += "\nHint: use 'tree' or 'find' to locate the correct path."
            elif "already_exists" in txt.lower():
                txt += "\nHint: read the existing file first, then decide how to proceed."

        # ── COMPLETION ────────────────────────────────────────────
        if isinstance(cmd, ReportTaskCompletion):
            status = CLI_GREEN if cmd.outcome == "OUTCOME_OK" else CLI_YELLOW
            print(f"{status}agent {cmd.outcome}{CLI_CLR}. Summary:")
            for item in cmd.completed_steps_laconic:
                print(f"- {item}")
            print(f"\n{CLI_BLUE}AGENT SUMMARY: {cmd.message}{CLI_CLR}")
            if cmd.grounding_refs:
                for ref in cmd.grounding_refs:
                    print(f"- {CLI_BLUE}{ref}{CLI_CLR}")
            return cmd.outcome  # ← A-Evolve needs this

        # ── TRACKING ──────────────────────────────────────────────
        if isinstance(cmd, Req_Write):
            tracker.record_write(cmd.path)
        if isinstance(cmd, Req_Read):
            tracker.record_read(cmd.path)

        # Stagnation detection
        tool_args = str(getattr(cmd, "path", getattr(cmd, "pattern", "")))
        stagnation.record(cmd.tool, tool_args)
        if stagnation.is_stagnant() or stagnation.is_oscillating():
            nudge = stagnation.nudge_message()
            print(f"{CLI_YELLOW}STAGNATION{CLI_CLR}: {nudge}")
            txt += f"\n{nudge}"

        # ── DEFEND: scan tool output for threats ──────────────────
        content_warnings = scan_content(txt)
        if content_warnings:
            warning_text = "SECURITY WARNING: " + "; ".join(content_warnings)
            print(f"{CLI_YELLOW}DEFEND{CLI_CLR}: {warning_text}")
            txt += f"\n{warning_text}"

        messages.append({"role": "user", "content": wrap_tool_output(txt)})

    return None
