"""Filesystem domain for PAC1 benchmark.

Implements DomainProtocol for the PCM runtime (typed file-system CRM).
Tool models, dispatch registry, Unix-style formatters, and boot sequence.
"""

import json
import shlex
from typing import Annotated, Any, Literal

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
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field

from defend import scan_content, wrap_tool_output
from domain_protocol import LoopMode, ToolHandler

# ── Tool models ───────────────────────────────────────────────────────────


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
    limit: Annotated[int, Ge(1), Le(50)] = 20


class Req_Search(BaseModel):
    tool: Literal["search"]
    pattern: str
    limit: Annotated[int, Ge(1), Le(50)] = 20
    root: str = "/"


class Req_List(BaseModel):
    tool: Literal["list"]
    path: str = "/"


class Req_Read(BaseModel):
    tool: Literal["read"]
    path: str
    number: bool = Field(False, description="return 1-based line numbers")
    start_line: Annotated[int, Ge(0)] = Field(
        0, description="1-based inclusive; 0 = from first line"
    )
    end_line: Annotated[int, Ge(0)] = Field(
        0, description="1-based inclusive; 0 = through last line"
    )


class Req_Context(BaseModel):
    tool: Literal["context"]


class Req_Write(BaseModel):
    tool: Literal["write"]
    path: str
    content: str
    start_line: Annotated[int, Ge(0)] = Field(0, description="1-based; 0 = whole-file overwrite")
    end_line: Annotated[int, Ge(0)] = Field(0, description="1-based; 0 = through last line")


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
    plan_remaining_steps_brief: Annotated[list[str], MinLen(1), MaxLen(8)] = Field(
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


# ── Outcome mapping ───────────────────────────────────────────────────────

OUTCOME_BY_NAME = {
    "OUTCOME_OK": Outcome.OUTCOME_OK,
    "OUTCOME_DENIED_SECURITY": Outcome.OUTCOME_DENIED_SECURITY,
    "OUTCOME_NONE_CLARIFICATION": Outcome.OUTCOME_NONE_CLARIFICATION,
    "OUTCOME_NONE_UNSUPPORTED": Outcome.OUTCOME_NONE_UNSUPPORTED,
    "OUTCOME_ERR_INTERNAL": Outcome.OUTCOME_ERR_INTERNAL,
}

# ── Formatters ────────────────────────────────────────────────────────────


def _render(command: str, body: str) -> str:
    return f"{command}\n{body}"


def _fmt_tree_entry(entry, prefix: str = "", is_last: bool = True) -> list[str]:
    branch = "└── " if is_last else "├── "
    lines = [f"{prefix}{branch}{entry.name}"]
    child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
    children = list(entry.children)
    for idx, child in enumerate(children):
        lines.extend(_fmt_tree_entry(child, prefix=child_prefix, is_last=idx == len(children) - 1))
    return lines


def _fmt_tree(cmd, result) -> str:
    root = result.root
    if not root.name:
        return _render(f"tree -L {cmd.level} {cmd.root or '/'}", ".")
    lines = [root.name]
    children = list(root.children)
    for idx, child in enumerate(children):
        lines.extend(_fmt_tree_entry(child, is_last=idx == len(children) - 1))
    level_arg = f" -L {cmd.level}" if cmd.level > 0 else ""
    return _render(f"tree{level_arg} {cmd.root or '/'}", "\n".join(lines))


def _fmt_list(cmd, result) -> str:
    if not result.entries:
        return _render(f"ls {cmd.path}", ".")
    body = "\n".join(f"{e.name}/" if e.is_dir else e.name for e in result.entries)
    return _render(f"ls {cmd.path}", body)


def _fmt_read(cmd, result) -> str:
    if cmd.start_line > 0 or cmd.end_line > 0:
        s = cmd.start_line if cmd.start_line > 0 else 1
        e = cmd.end_line if cmd.end_line > 0 else "$"
        return _render(f"sed -n '{s},{e}p' {cmd.path}", result.content)
    command = f"cat -n {cmd.path}" if cmd.number else f"cat {cmd.path}"
    return _render(command, result.content)


def _fmt_search(cmd, result) -> str:
    root = shlex.quote(cmd.root or "/")
    pattern = shlex.quote(cmd.pattern)
    body = "\n".join(f"{m.path}:{m.line}:{m.line_text}" for m in result.matches)
    return _render(f"rg -n --no-heading -e {pattern} {root}", body)


# ── Dispatch helpers ──────────────────────────────────────────────────────


def _exec_context(vm, cmd):
    return vm.context(ContextRequest())


def _exec_tree(vm, cmd):
    return vm.tree(TreeRequest(root=cmd.root, level=cmd.level))


def _exec_find(vm, cmd):
    return vm.find(
        FindRequest(
            root=cmd.root,
            name=cmd.name,
            type={"all": 0, "files": 1, "dirs": 2}[cmd.kind],
            limit=cmd.limit,
        )
    )


def _exec_search(vm, cmd):
    return vm.search(SearchRequest(root=cmd.root, pattern=cmd.pattern, limit=cmd.limit))


def _exec_list(vm, cmd):
    return vm.list(ListRequest(name=cmd.path))


def _exec_read(vm, cmd):
    return vm.read(
        ReadRequest(
            path=cmd.path, number=cmd.number, start_line=cmd.start_line, end_line=cmd.end_line
        )
    )


def _exec_write(vm, cmd):
    return vm.write(
        WriteRequest(
            path=cmd.path, content=cmd.content, start_line=cmd.start_line, end_line=cmd.end_line
        )
    )


def _exec_delete(vm, cmd):
    return vm.delete(DeleteRequest(path=cmd.path))


def _exec_mkdir(vm, cmd):
    return vm.mk_dir(MkDirRequest(path=cmd.path))


def _exec_move(vm, cmd):
    return vm.move(MoveRequest(from_name=cmd.from_name, to_name=cmd.to_name))


def _exec_answer(vm, cmd):
    return vm.answer(
        AnswerRequest(
            message=cmd.message, outcome=OUTCOME_BY_NAME[cmd.outcome], refs=cmd.grounding_refs
        )
    )


def _fmt_default(cmd, result) -> str:
    return "{}" if result is None else json.dumps(MessageToDict(result), indent=2)


def _fmt_write(cmd, result) -> str:
    return _render(f"tee {cmd.path}", f"written: {cmd.path} (OK, now read to verify)")


def _fmt_delete(cmd, result) -> str:
    return _render(f"rm {cmd.path}", f"deleted: {cmd.path}")


# ── Tool registry ─────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, ToolHandler] = {
    "context": ToolHandler(model=Req_Context, execute=_exec_context, format=_fmt_default),
    "tree": ToolHandler(model=Req_Tree, execute=_exec_tree, format=_fmt_tree),
    "find": ToolHandler(model=Req_Find, execute=_exec_find, format=_fmt_default),
    "search": ToolHandler(model=Req_Search, execute=_exec_search, format=_fmt_search),
    "list": ToolHandler(model=Req_List, execute=_exec_list, format=_fmt_list),
    "read": ToolHandler(model=Req_Read, execute=_exec_read, format=_fmt_read),
    "write": ToolHandler(
        model=Req_Write, execute=_exec_write, format=_fmt_write, risk_level="medium"
    ),
    "delete": ToolHandler(
        model=Req_Delete, execute=_exec_delete, format=_fmt_delete, risk_level="high"
    ),
    "mkdir": ToolHandler(
        model=Req_MkDir, execute=_exec_mkdir, format=_fmt_default, risk_level="medium"
    ),
    "move": ToolHandler(
        model=Req_Move, execute=_exec_move, format=_fmt_default, risk_level="high"
    ),
    "report_completion": ToolHandler(
        model=ReportTaskCompletion, execute=_exec_answer, format=_fmt_default
    ),
}

# ── FilesystemDomain ──────────────────────────────────────────────────────

CLI_GREEN = "\x1b[32m"
CLI_CLR = "\x1b[0m"


class FilesystemDomain:
    name = "filesystem"
    nextstep_type = NextStep
    tool_registry = TOOL_REGISTRY
    threat_profile = None  # defend.py uses its own module-level patterns for now
    classification_rules = ()  # classify.py uses its own module-level rules for now
    strategy_entries = ()  # strategy.py uses its own module-level table for now
    loop_mode = LoopMode(kind="batch", max_steps=25)

    def create_client(self, harness_url: str) -> PcmRuntimeClientSync:
        return PcmRuntimeClientSync(harness_url)

    def boot_messages(self, client: PcmRuntimeClientSync) -> list[dict]:
        messages: list[dict] = []
        boot_cmds = [
            Req_Tree(level=2, tool="tree", root="/"),
            Req_Read(path="AGENTS.md", tool="read"),
            Req_Context(tool="context"),
        ]
        for cmd in boot_cmds:
            result = self.dispatch(client, cmd)
            formatted = self.format_result(cmd, result)
            print(f"{CLI_GREEN}AUTO{CLI_CLR}: {formatted}")
            boot_warnings = scan_content(formatted)
            if boot_warnings:
                warning_text = "SECURITY WARNING (boot): " + "; ".join(boot_warnings)
                print(f"\x1b[33mDEFEND\x1b[0m: {warning_text}")
                formatted += f"\n{warning_text}"
            messages.append({"role": "user", "content": wrap_tool_output(formatted)})
        return messages

    def dispatch(self, client: Any, cmd: BaseModel) -> Any:
        tool_name = getattr(cmd, "tool", "")
        handler = self.tool_registry.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        return handler.execute(client, cmd)

    def format_result(self, cmd: BaseModel, result: Any) -> str:
        if result is None:
            return "{}"
        tool_name = getattr(cmd, "tool", "")
        handler = self.tool_registry.get(tool_name)
        if handler is None:
            return "{}"
        return handler.format(cmd, result)

    def is_completion(self, cmd: BaseModel) -> bool:
        return isinstance(cmd, ReportTaskCompletion)

    def completion_outcome(self, cmd: BaseModel) -> str | None:
        return cmd.outcome if isinstance(cmd, ReportTaskCompletion) else None

    def wrap_output(self, content: str) -> str:
        return wrap_tool_output(content)

    def expand_search_result(self, client: Any, cmd: BaseModel, result: Any, txt: str) -> str:
        """If search returned 0 results and query has 2+ tokens, retry per token."""
        if getattr(cmd, "tool", "") != "search" or not hasattr(result, "matches"):
            return txt
        if result.matches:
            return txt
        tokens = cmd.pattern.split()
        if len(tokens) < 2:
            return txt
        extra = []
        for tok in tokens:
            sub_cmd = Req_Search(tool="search", pattern=tok, root=cmd.root, limit=cmd.limit)
            sub = _exec_search(client, sub_cmd)
            if sub.matches:
                body = "\n".join(f"{m.path}:{m.line}:{m.line_text}" for m in sub.matches)
                extra.append(f"rg -e '{tok}' {cmd.root or '/'} (auto-retry)\n{body}")
        if extra:
            return (
                txt
                + "\nAuto-retry (0 matches for full pattern; individual tokens):\n"
                + "\n".join(extra)
            )
        return txt

    def poll_events(self, client: Any) -> list[dict] | None:
        return None
