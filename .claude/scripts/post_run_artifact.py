from __future__ import annotations

import json
import re
from pathlib import Path

from hook_utils import REPO_ROOT, emit_context, extract_command, is_benchmark_command, read_event


def _latest_eval_report() -> Path | None:
    reports = sorted((REPO_ROOT / "docs" / "eval").glob("run-*.md"))
    return reports[-1] if reports else None


def _parse_list(text: str, heading: str) -> list[str]:
    pattern = re.compile(rf"## {re.escape(heading)}(?:: none)?\n(.*?)(?:\n## |\Z)", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return []
    block = match.group(1)
    return [line[2:].strip() for line in block.splitlines() if line.startswith("- ")]


def _parse_eval(path: Path) -> dict:
    text = path.read_text()
    m_ts = re.search(r"run-(\d{4}-\d{2}-\d{2}-\d{2})\.md$", path.name)
    m_score = re.search(r"\*\*Score:\*\*\s*(\d+)/(\d+)\s*\(([\d.]+)%\)", text)
    m_prev = re.search(r"\*\*Previous:\*\*\s*(\d+)/(\d+)\s*\(([\d.]+)%\)", text)
    m_delta = re.search(r"\*\*Delta:\*\*\s*([^\n]+)", text)
    m_model = re.search(r"\*\*Model:\*\*\s*`?([^`\n]+)`?", text)
    m_backend = re.search(r"\*\*Backend:\*\*\s*`?([^`\n]+)`?", text)

    per_task = {}
    for task_id, score, status in re.findall(r"\|\s*(t\d+)\s*\|\s*([\d.]+)\s*\|\s*(\w+)\s*\|", text):
        per_task[task_id] = {"score": float(score), "status": status}

    return {
        "report_path": str(path.relative_to(REPO_ROOT)),
        "timestamp": m_ts.group(1) if m_ts else path.stem,
        "model": m_model.group(1).strip() if m_model else "unknown",
        "backend": m_backend.group(1).strip() if m_backend else "unknown",
        "score": {
            "tasks_passed": int(m_score.group(1)) if m_score else 0,
            "tasks_total": int(m_score.group(2)) if m_score else len(per_task),
            "score_pct": float(m_score.group(3)) if m_score else 0.0,
        },
        "previous": {
            "tasks_passed": int(m_prev.group(1)) if m_prev else 0,
            "tasks_total": int(m_prev.group(2)) if m_prev else 0,
            "score_pct": float(m_prev.group(3)) if m_prev else 0.0,
        },
        "delta": m_delta.group(1).strip() if m_delta else "",
        "improvements": _parse_list(text, "Improvements"),
        "regressions": _parse_list(text, "Regressions"),
        "still_failing": _parse_list(text, "Still Failing"),
        "passing_count": sum(1 for task in per_task.values() if task["score"] >= 1.0),
        "failing_task_ids": [task_id for task_id, task in sorted(per_task.items()) if task["score"] < 1.0],
        "per_task": per_task,
    }


def _latest_run_history_note() -> dict:
    history_path = REPO_ROOT / "docs" / "run_history.json"
    if not history_path.exists():
        return {}
    try:
        history = json.loads(history_path.read_text())
    except Exception:
        return {}
    if not history:
        return {}
    latest = history[-1]
    previous_full = None
    for run in reversed(history[:-1]):
        if not run.get("is_partial_run") and run.get("tasks_total", 0) >= run.get(
            "benchmark_task_count", run.get("tasks_total", 0)
        ):
            previous_full = run
            break
    note = {
        "benchmark_id": latest.get("benchmark_id"),
        "benchmark_task_count": latest.get("benchmark_task_count"),
        "is_partial_run": bool(latest.get("is_partial_run")),
    }
    if previous_full and latest.get("tasks_total") != previous_full.get("tasks_total"):
        note["benchmark_drift"] = {
            "previous_tasks_total": previous_full.get("tasks_total"),
            "current_tasks_total": latest.get("tasks_total"),
        }
    return note


def main() -> None:
    event = read_event()
    command = extract_command(event)
    if not is_benchmark_command(command):
        return

    report = _latest_eval_report()
    if report is None:
        return

    data = _parse_eval(report)
    data["run_history"] = _latest_run_history_note()

    out_dir = REPO_ROOT / "docs" / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"auto-run-{data['timestamp']}.json"
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    emit_context(
        f"Auto artifact written: {out_path.relative_to(REPO_ROOT)}.",
        event_name="PostToolUse",
    )


if __name__ == "__main__":
    main()
