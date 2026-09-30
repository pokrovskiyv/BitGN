"""Ecommerce domain for the ECOM1 benchmark.

Implements DomainProtocol for the public `bitgn.vm.ecom` runtime. The runtime
is file-shaped like PAC/PCM, but adds `stat` and `exec`; catalogue-heavy tasks
are expected to use `/bin/sql` through `exec`.
"""

import json
import shlex
from typing import Annotated, Any, Literal

from annotated_types import Ge, Le, MaxLen, MinLen
from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import (
    AnswerRequest,
    DeleteRequest,
    ExecRequest,
    FindRequest,
    ListRequest,
    NodeKind,
    Outcome,
    ReadRequest,
    SearchRequest,
    StatRequest,
    TreeRequest,
    WriteRequest,
)
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field

from defend import scan_content, wrap_tool_output
from domain_protocol import LoopMode, ToolHandler


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
    limit: Annotated[int, Ge(1), Le(200)] = 20


class Req_Search(BaseModel):
    tool: Literal["search"]
    pattern: str = ""
    query: str = ""
    limit: Annotated[int, Ge(1), Le(200)] = 20
    root: str = "/"
    path: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.pattern and self.query:
            object.__setattr__(self, "pattern", self.query)
        if self.root == "/" and self.path:
            object.__setattr__(self, "root", self.path)


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


class Req_Write(BaseModel):
    tool: Literal["write"]
    path: str
    content: str


class Req_Delete(BaseModel):
    tool: Literal["delete"]
    path: str


class Req_Stat(BaseModel):
    tool: Literal["stat"]
    path: str


class Req_Exec(BaseModel):
    tool: Literal["exec"]
    path: str
    args: list[str] = Field(default_factory=list)
    stdin: str = ""


class NextStep(BaseModel):
    current_state: str
    plan_remaining_steps_brief: Annotated[list[str], MinLen(1), MaxLen(8)] = Field(
        ...,
        description="briefly explain the next useful steps",
    )
    task_completed: bool
    function: (
        ReportTaskCompletion
        | Req_Tree
        | Req_Find
        | Req_Search
        | Req_List
        | Req_Read
        | Req_Write
        | Req_Delete
        | Req_Stat
        | Req_Exec
    ) = Field(..., description="execute the first remaining step")


OUTCOME_BY_NAME = {
    "OUTCOME_OK": Outcome.OUTCOME_OK,
    "OUTCOME_DENIED_SECURITY": Outcome.OUTCOME_DENIED_SECURITY,
    "OUTCOME_NONE_CLARIFICATION": Outcome.OUTCOME_NONE_CLARIFICATION,
    "OUTCOME_NONE_UNSUPPORTED": Outcome.OUTCOME_NONE_UNSUPPORTED,
    "OUTCOME_ERR_INTERNAL": Outcome.OUTCOME_ERR_INTERNAL,
}


def _render(command: str, body: str) -> str:
    return f"{command}\n{body}"


def _is_truncated(result: Any) -> bool:
    return bool(getattr(result, "truncated", False))


def _mark_truncated(result: Any, body: str, hint: str) -> str:
    if not _is_truncated(result):
        return body
    marker = f"[TRUNCATED: {hint}]"
    return marker if not body else f"{body}\n{marker}"


def _fmt_tree_entry(entry: Any, prefix: str = "", is_last: bool = True) -> list[str]:
    branch = "`-- " if is_last else "|-- "
    lines = [f"{prefix}{branch}{entry.name}"]
    child_prefix = f"{prefix}{'    ' if is_last else '|   '}"
    children = list(entry.children)
    for idx, child in enumerate(children):
        lines.extend(_fmt_tree_entry(child, prefix=child_prefix, is_last=idx == len(children) - 1))
    return lines


def _fmt_tree(cmd: Req_Tree, result: Any) -> str:
    root = result.root
    if not root.name:
        body = "."
    else:
        lines = [root.name]
        children = list(root.children)
        for idx, child in enumerate(children):
            lines.extend(_fmt_tree_entry(child, is_last=idx == len(children) - 1))
        body = "\n".join(lines)
    body = _mark_truncated(
        result,
        body,
        "tree output hit a limit; use a narrower root or search for a specific term",
    )
    level_arg = f" -L {cmd.level}" if cmd.level > 0 else ""
    return _render(f"tree{level_arg} {cmd.root or '/'}", body)


def _fmt_list(cmd: Req_List, result: Any) -> str:
    if not result.entries:
        body = "."
    else:
        body = "\n".join(
            f"{entry.name}/" if entry.kind == NodeKind.NODE_KIND_DIR else entry.name
            for entry in result.entries
        )
    return _render(f"ls {cmd.path}", body)


def _fmt_read(cmd: Req_Read, result: Any) -> str:
    if cmd.start_line > 0 or cmd.end_line > 0:
        start = cmd.start_line if cmd.start_line > 0 else 1
        end = cmd.end_line if cmd.end_line > 0 else "$"
        command = f"sed -n '{start},{end}p' {cmd.path}"
    elif cmd.number:
        command = f"cat -n {cmd.path}"
    else:
        command = f"cat {cmd.path}"
    body = _mark_truncated(
        result,
        result.content,
        "file output hit a limit; use start_line/end_line to read a smaller range",
    )
    return _render(command, body)


def _fmt_search(cmd: Req_Search, result: Any) -> str:
    root = shlex.quote(cmd.root or "/")
    pattern = shlex.quote(cmd.pattern)
    body = "\n".join(f"{m.path}:{m.line}:{m.line_text}" for m in result.matches)
    body = _mark_truncated(
        result,
        body,
        "search hit limit reached; narrow the pattern/root or raise the limit",
    )
    return _render(f"rg -n --no-heading -e {pattern} {root}", body)


def _fmt_exec(cmd: Req_Exec, result: Any) -> str:
    path = shlex.quote(cmd.path)
    args = " ".join(shlex.quote(arg) for arg in cmd.args)
    command = f"{path} {args}".strip()
    if cmd.stdin:
        label = "SQL" if cmd.path == "/bin/sql" else "STDIN"
        command = f"{command} <<'{label}'\n{cmd.stdin.rstrip()}\n{label}"
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append(f"stderr:\n{result.stderr.rstrip()}")
    if getattr(result, "exit_code", 0):
        parts.append(f"[exit {result.exit_code}]")
    return _render(command, "\n".join(parts) if parts else ".")


def _fmt_default(cmd: BaseModel, result: Any) -> str:
    return "{}" if result is None else json.dumps(MessageToDict(result), indent=2)


def _fmt_write(cmd: Req_Write, result: Any) -> str:
    return _render(f"tee {cmd.path}", f"written: {cmd.path} (OK, now read to verify)")


def _fmt_delete(cmd: Req_Delete, result: Any) -> str:
    return _render(f"rm {cmd.path}", f"deleted: {cmd.path}")


def _exec_tree(vm: EcomRuntimeClientSync, cmd: Req_Tree):
    return vm.tree(TreeRequest(root=cmd.root, level=cmd.level))


def _exec_find(vm: EcomRuntimeClientSync, cmd: Req_Find):
    return vm.find(
        FindRequest(
            root=cmd.root,
            name=cmd.name,
            kind={
                "all": NodeKind.NODE_KIND_UNSPECIFIED,
                "files": NodeKind.NODE_KIND_FILE,
                "dirs": NodeKind.NODE_KIND_DIR,
            }[cmd.kind],
            limit=cmd.limit,
        )
    )


def _exec_search(vm: EcomRuntimeClientSync, cmd: Req_Search):
    return vm.search(SearchRequest(root=cmd.root, pattern=cmd.pattern, limit=cmd.limit))


def _exec_list(vm: EcomRuntimeClientSync, cmd: Req_List):
    return vm.list(ListRequest(path=cmd.path))


def _exec_read(vm: EcomRuntimeClientSync, cmd: Req_Read):
    return vm.read(
        ReadRequest(
            path=cmd.path,
            number=cmd.number,
            start_line=cmd.start_line,
            end_line=cmd.end_line,
        )
    )


def _exec_write(vm: EcomRuntimeClientSync, cmd: Req_Write):
    return vm.write(WriteRequest(path=cmd.path, content=cmd.content))


def _exec_delete(vm: EcomRuntimeClientSync, cmd: Req_Delete):
    return vm.delete(DeleteRequest(path=cmd.path))


def _exec_stat(vm: EcomRuntimeClientSync, cmd: Req_Stat):
    return vm.stat(StatRequest(path=cmd.path))


def _exec_exec(vm: EcomRuntimeClientSync, cmd: Req_Exec):
    return vm.exec(ExecRequest(path=cmd.path, args=cmd.args, stdin=cmd.stdin))


def _exec_answer(vm: EcomRuntimeClientSync, cmd: ReportTaskCompletion):
    return vm.answer(
        AnswerRequest(
            message=cmd.message,
            outcome=OUTCOME_BY_NAME[cmd.outcome],
            refs=cmd.grounding_refs,
        )
    )


TOOL_REGISTRY: dict[str, ToolHandler] = {
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
    "stat": ToolHandler(model=Req_Stat, execute=_exec_stat, format=_fmt_default),
    "exec": ToolHandler(model=Req_Exec, execute=_exec_exec, format=_fmt_exec, risk_level="medium"),
    "report_completion": ToolHandler(
        model=ReportTaskCompletion, execute=_exec_answer, format=_fmt_default
    ),
}


CLI_GREEN = "\x1b[32m"
CLI_CLR = "\x1b[0m"


class EcomDomain:
    name = "ecommerce"
    nextstep_type = NextStep
    tool_registry = TOOL_REGISTRY
    threat_profile = None
    classification_rules = ()
    strategy_entries = ()
    loop_mode = LoopMode(kind="batch", max_steps=30)

    def create_client(self, harness_url: str) -> EcomRuntimeClientSync:
        return EcomRuntimeClientSync(harness_url)

    def boot_messages(self, client: EcomRuntimeClientSync) -> list[dict]:
        messages: list[dict] = []
        boot_cmds = [
            Req_Tree(level=2, tool="tree", root="/"),
            Req_Read(path="/AGENTS.MD", tool="read"),
            Req_Exec(path="/bin/date", tool="exec"),
            Req_Exec(path="/bin/id", tool="exec"),
        ]
        for cmd in boot_cmds:
            result = self.dispatch(client, cmd)
            formatted = self.format_result(cmd, result)
            print(f"{CLI_GREEN}AUTO{CLI_CLR}: {formatted}")
            warnings = scan_content(formatted)
            if warnings:
                warning_text = "SECURITY WARNING (boot): " + "; ".join(warnings)
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
