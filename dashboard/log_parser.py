"""Parse raw benchmark execution logs into structured task traces."""

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_LOGS_DIR = REPO_ROOT / "docs" / "run_logs"

_ANSI_RE = re.compile(r"\x1B\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


@dataclass
class StepTrace:
    step_num: int
    plan_brief: str
    tool: str
    args_summary: str
    timing_ms: int
    events: list


@dataclass
class TaskTrace:
    task_id: str
    instruction: str
    classification: str
    task_type: str
    max_steps: int
    threat: str
    steps: list
    score: float
    total_time_ms: int
    step_count: int
    events_summary: dict
    # Agent answer fields (from report_completion)
    answer_outcome: str
    answer_message: str
    answer_steps: list  # completed_steps_laconic
    answer_grounding_refs: list


def _extract_answer(block: str) -> tuple:
    """Extract agent answer from report_completion in a task block.

    Returns (outcome, message, completed_steps, grounding_refs).
    """
    # Try structured report_completion line first
    rc_m = re.search(r"tool='report_completion'(.+?)(?:\n|$)", block)
    if rc_m:
        line = rc_m.group(1)
        outcome_m = re.search(r"outcome='([^']+)'", line)
        msg_m = re.search(r"message='([^']*(?:''[^']*)*)'", line)
        # For message with internal quotes, try a broader match
        if not msg_m:
            msg_m = re.search(r'message="([^"]*)"', line)
        if not msg_m:
            msg_m = re.search(r"message='(.+?)'\s+grounding_refs=", line)
        steps_m = re.search(r"completed_steps_laconic=\[([^\]]*)\]", line)
        refs_m = re.search(r"grounding_refs=\[([^\]]*)\]", line)

        outcome = outcome_m.group(1) if outcome_m else ""
        message = msg_m.group(1) if msg_m else ""
        steps_raw = steps_m.group(1) if steps_m else ""
        refs_raw = refs_m.group(1) if refs_m else ""

        completed_steps = [s.strip().strip("'\"") for s in steps_raw.split("',") if s.strip()]
        grounding_refs = [r.strip().strip("'\"") for r in refs_raw.split("',") if r.strip()]

        return outcome, message, completed_steps, grounding_refs

    # Fallback: parse "agent OUTCOME_..." line + Summary block
    agent_m = re.search(r"agent (OUTCOME_\w+)\.\s*Summary:\s*\n((?:- .+\n)*)", block)
    if agent_m:
        outcome = agent_m.group(1)
        summary_lines = [
            line.strip().lstrip("- ")
            for line in agent_m.group(2).strip().split("\n")
            if line.strip()
        ]
        message = "; ".join(summary_lines)
        return outcome, message, summary_lines, []

    return "", "", [], []


def parse_benchmark_log(path: Path) -> list:
    """Parse a raw benchmark log file into a list of TaskTrace objects."""
    text = _strip_ansi(path.read_text())
    task_blocks = re.split(r"={20,} Starting task: (t\d+) ={20,}", text)

    traces = []
    for i in range(1, len(task_blocks), 2):
        task_id = task_blocks[i]
        block = task_blocks[i + 1] if i + 1 < len(task_blocks) else ""

        instr_m = re.search(r"\n(.+?)\n-{10,}", block, re.DOTALL)
        instruction = instr_m.group(1).strip() if instr_m else ""

        cls_m = re.search(r"CLASSIFY:\s*(.+)", block)
        classification = cls_m.group(1).strip() if cls_m else ""

        type_m = re.match(r"(\w+)", classification)
        task_type = type_m.group(1) if type_m else "unknown"

        max_m = re.search(r"max_steps=(\d+)", classification)
        max_steps = int(max_m.group(1)) if max_m else 0

        threat_m = re.search(r"threat=(\w+)", classification)
        threat = threat_m.group(1) if threat_m else "none"

        steps = []
        events_count = {"GATE": 0, "DEFEND": 0, "STAGNATION": 0, "LLM_ERROR": 0}

        step_matches = list(re.finditer(r"Next step_(\d+)\.\.\.\s*(.+?)\s*\((\d+)\s*ms\)", block))

        for idx, step_m in enumerate(step_matches):
            step_num = int(step_m.group(1))
            plan_brief = step_m.group(2).strip()
            timing_ms = int(step_m.group(3))

            if "LLM parse error" in plan_brief:
                events_count["LLM_ERROR"] += 1
                continue

            pos = step_m.end()
            tool_m = re.search(r"tool='(\w+)'(.+)?", block[pos : pos + 200])
            tool = tool_m.group(1) if tool_m else ""
            args_summary = tool_m.group(0).strip()[:80] if tool_m else ""

            next_pos = step_matches[idx + 1].start() if idx + 1 < len(step_matches) else len(block)
            region = block[pos:next_pos]

            step_events = []
            if "GATE" in region:
                events_count["GATE"] += 1
                step_events.append("GATE")
            if "DEFEND" in region:
                events_count["DEFEND"] += 1
                step_events.append("DEFEND")
            if "STAGNATION" in region:
                events_count["STAGNATION"] += 1
                step_events.append("STAGNATION")

            steps.append(
                StepTrace(
                    step_num=step_num,
                    plan_brief=plan_brief,
                    tool=tool,
                    args_summary=args_summary,
                    timing_ms=timing_ms,
                    events=step_events,
                )
            )

        llm_errors_in_block = len(re.findall(r"LLM parse error \(attempt", block))
        events_count["LLM_ERROR"] = max(events_count["LLM_ERROR"], llm_errors_in_block)

        score_m = re.search(r"Score:\s*([\d.]+)", block)
        score = float(score_m.group(1)) if score_m else -1.0

        total_time = sum(s.timing_ms for s in steps)

        # Extract agent answer from report_completion
        answer_outcome, answer_message, answer_steps, answer_refs = _extract_answer(block)

        traces.append(
            TaskTrace(
                task_id=task_id,
                instruction=instruction,
                classification=classification,
                task_type=task_type,
                max_steps=max_steps,
                threat=threat,
                steps=steps,
                score=score,
                total_time_ms=total_time,
                step_count=len(steps),
                events_summary=events_count,
                answer_outcome=answer_outcome,
                answer_message=answer_message,
                answer_steps=answer_steps,
                answer_grounding_refs=answer_refs,
            )
        )

    return traces


def load_run_log(timestamp: str) -> list:
    """Load parsed task traces for a run by timestamp."""
    candidates = [
        RUN_LOGS_DIR / f"run-{timestamp}.log",
        RUN_LOGS_DIR / f"{timestamp}.log",
    ]
    for path in candidates:
        if path.exists():
            try:
                return parse_benchmark_log(path)
            except Exception:
                return []
    return []


def load_all_run_logs() -> dict:
    """Load all available run logs. Returns dict: filename stem → list[TaskTrace]."""
    if not RUN_LOGS_DIR.exists():
        return {}
    logs = {}
    for path in sorted(RUN_LOGS_DIR.glob("run-*.log")):
        try:
            logs[path.stem] = parse_benchmark_log(path)
        except Exception:
            continue
    return logs
