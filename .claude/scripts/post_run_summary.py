from __future__ import annotations

import json
import re
from pathlib import Path

from hook_utils import REPO_ROOT, emit_context, extract_command, is_benchmark_command, read_event


def _latest_eval_report() -> Path | None:
    reports = sorted((REPO_ROOT / "docs" / "eval").glob("run-*.md"))
    return reports[-1] if reports else None


def _parse_bullets(text: str, heading: str) -> list[str]:
    pattern = re.compile(rf"## {re.escape(heading)}(?:: none)?\n(.*?)(?:\n## |\Z)", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return []
    block = match.group(1)
    return [line[2:].strip() for line in block.splitlines() if line.startswith("- ")]


def _summary_from_eval(path: Path) -> list[str]:
    text = path.read_text()
    score = re.search(r"\*\*Score:\*\* ([^\n]+)", text)
    previous = re.search(r"\*\*Previous:\*\* ([^\n]+)", text)
    delta = re.search(r"\*\*Delta:\*\* ([^\n]+)", text)
    lines = [f"Latest eval report: {path.name}."]
    if score:
        lines.append(f"Score: {score.group(1).strip()}")
    if previous and delta:
        lines.append(f"Previous: {previous.group(1).strip()} | Delta: {delta.group(1).strip()}")

    regressions = _parse_bullets(text, "Regressions")
    still_failing = _parse_bullets(text, "Still Failing")
    if regressions:
        lines.append(
            "Regressions: " + ", ".join(item.split(":")[0].strip("* ") for item in regressions[:6])
        )
    if still_failing:
        lines.append(
            "Still failing: " + ", ".join(item.split(":")[0].strip() for item in still_failing[:6])
        )
    return lines


def _history_note() -> str:
    history_path = REPO_ROOT / "docs" / "run_history.json"
    if not history_path.exists():
        return ""
    try:
        history = json.loads(history_path.read_text())
    except Exception:
        return ""
    full_runs = [
        run
        for run in history
        if not run.get("is_partial_run")
        and run.get("tasks_total", 0) >= run.get("benchmark_task_count", run.get("tasks_total", 0))
    ]
    if len(full_runs) < 2:
        return ""
    latest, prev = full_runs[-1], full_runs[-2]
    if latest.get("tasks_total") != prev.get("tasks_total"):
        return f"Benchmark drift detected: tasks_total changed {prev.get('tasks_total')} -> {latest.get('tasks_total')}."
    return ""


def main() -> None:
    event = read_event()
    command = extract_command(event)
    if not is_benchmark_command(command):
        return

    report = _latest_eval_report()
    if report is None:
        return

    lines = _summary_from_eval(report)
    drift = _history_note()
    if drift:
        lines.append(drift)
        lines.append("Next step: use `triage-benchmark-update` before running a broad fix cycle.")
    else:
        lines.append("Next step: use `analyze-run` or `pcdred-cycle` depending on failure concentration.")

    emit_context("\n".join(f"- {line}" for line in lines), event_name="PostToolUse")


if __name__ == "__main__":
    main()
