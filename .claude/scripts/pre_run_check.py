from __future__ import annotations

import json
from pathlib import Path

from hook_utils import REPO_ROOT, emit_context, extract_command, is_benchmark_command, read_event


def _latest_full_run_summary() -> str:
    history_path = REPO_ROOT / "docs" / "run_history.json"
    if not history_path.exists():
        return "No run_history.json yet."
    try:
        history = json.loads(history_path.read_text())
    except Exception:
        return "run_history.json exists but could not be parsed."

    full_runs = [
        run
        for run in history
        if not run.get("is_partial_run")
        and run.get("tasks_total", 0) >= run.get("benchmark_task_count", run.get("tasks_total", 0))
    ]
    if not full_runs:
        return "No complete runs recorded yet."

    latest = full_runs[-1]
    line = (
        f"Latest full run: {latest.get('score_pct', 0)}% "
        f"({latest.get('tasks_passed', 0)}/{latest.get('tasks_total', 0)}) "
        f"at {latest.get('timestamp', 'unknown time')}."
    )
    if len(full_runs) >= 2:
        prev = full_runs[-2]
        if latest.get("tasks_total") != prev.get("tasks_total"):
            line += f" Benchmark size changed {prev.get('tasks_total')} -> {latest.get('tasks_total')}."
    return line


def main() -> None:
    event = read_event()
    command = extract_command(event)
    if not is_benchmark_command(command):
        return

    progress_path = REPO_ROOT / "pac1-py" / ".run_progress.json"
    warnings: list[str] = [_latest_full_run_summary()]

    if progress_path.exists() and "--resume" not in command:
        warnings.append(
            "Found pac1-py/.run_progress.json. If the previous run was interrupted, prefer "
            "`uv run python main.py --resume` or remove stale progress intentionally."
        )

    lower_cmd = command.lower()
    if "make run" in lower_cmd and "--parallel" not in lower_cmd:
        warnings.append(
            "Full runs should prefer `uv run python main.py --parallel=4` to keep wall-clock low."
        )
    elif "uv run python main.py" in lower_cmd and "--parallel" not in lower_cmd and "task" not in lower_cmd:
        warnings.append("This looks like a full run without explicit parallelism; prefer `--parallel=4`.")

    emit_context("\n".join(f"- {line}" for line in warnings), event_name="PreToolUse")


if __name__ == "__main__":
    main()
