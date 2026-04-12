from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "docs" / "analysis" / "live-run-2026-04-11-1135.md"
LOG_PATH = ROOT / "docs" / "run_logs" / "run-final-pac1-prod-2026-04-11-1135.log"
TASK_CACHE_PATH = ROOT / "docs" / "task_cache.json"
RUN_HISTORY_PATH = ROOT / "docs" / "run_history.json"
BASELINE_PATH = ROOT / "docs" / "analysis" / "run-first-cycle.md"

RUN_ID = "run-22Hn6wN3Bg6WjbosPkW2gApDp"
RUN_NAME = "pac1-py-final-20260411-113521"
BENCHMARK_ID = "bitgn/pac1-prod"
TOTAL_TASKS = 104
STARTED_AT = datetime.fromisoformat("2026-04-11T11:35:21+00:00")
DEV_BASELINE_PCT = 74.42
BUDGETS = {
    "crud": 16,
    "search": 15,
    "multi_step": 25,
    "inbox_processing": 28,
    "communication": 22,
    "analysis": 20,
    "security_test": 8,
}

sys.path.insert(0, str(ROOT / "pac1-py"))
from classify import classify_task  # noqa: E402


def read_json_retry(path: Path, attempts: int = 5, delay: float = 0.15):
    last_error = None
    for _ in range(attempts):
        try:
            return json.loads(path.read_text())
        except Exception as exc:  # pragma: no cover - best-effort observer
            last_error = exc
            time.sleep(delay)
    raise last_error


def task_sort_key(task_id: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", task_id)
    return (int(match.group(1)) if match else 10**9, task_id)


def ms_to_s(ms: int | float | None) -> str:
    if ms is None:
        return "n/a"
    return f"{ms / 1000:.1f}s"


def human_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = round((len(ordered) - 1) * p)
    return ordered[int(idx)]


def language_of(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "cjk"
    if re.search(r"[\u0400-\u04ff]", text):
        return "cyrillic"
    if re.search(r"[¿¡]", text):
        return "spanish"
    return "en"


def verdict_of(proposed_outcome: str | None) -> str:
    outcome = proposed_outcome or ""
    if outcome.startswith("OUTCOME_OK"):
        return "ok"
    if outcome.startswith("OUTCOME_DENIED_"):
        return "denied_" + outcome.removeprefix("OUTCOME_DENIED_").lower()
    if outcome.startswith("OUTCOME_ERR_"):
        return "err_" + outcome.removeprefix("OUTCOME_ERR_").lower()
    return "unknown"


def load_run_tasks() -> list[dict]:
    data = read_json_retry(TASK_CACHE_PATH)
    tasks = []
    for task_id, payload in data.items():
        timestamp = payload.get("timestamp", "")
        if not timestamp:
            continue
        try:
            dt = datetime.fromisoformat(timestamp)
        except ValueError:
            continue
        if dt < STARTED_AT:
            continue
        metrics = payload.get("metrics", {}) or {}
        instruction = payload.get("instruction", "")
        kind = classify_task(instruction, []).task_type
        step_count = metrics.get("step_count") or 0
        tool_count = metrics.get("tool_call_count") or 0
        total_time_ms = metrics.get("total_time_ms")
        ratio = tool_count / step_count if step_count else 0.0
        proposed_outcome = (metrics.get("verifier_verdict") or {}).get("proposed_outcome")
        tasks.append(
            {
                "task_id": task_id,
                "timestamp": timestamp,
                "instruction": instruction,
                "kind": kind,
                "budget": BUDGETS[kind],
                "step_count": step_count,
                "tool_count": tool_count,
                "total_time_ms": total_time_ms,
                "tool_step_ratio": ratio,
                "verdict": verdict_of(proposed_outcome),
                "language": language_of(instruction),
                "verifier": metrics.get("verifier_verdict") or {},
            }
        )
    tasks.sort(key=lambda item: task_sort_key(item["task_id"]))
    return tasks


def load_log_stats() -> dict:
    text = LOG_PATH.read_text(errors="replace")
    return {
        "line_count": text.count("\n"),
        "starts": text.count("Starting task:"),
        "next_steps": text.count("Next step_"),
        "worker_errors": text.count("Task worker failed"),
        "stagnation": len(re.findall(r"stagnation|oscillation", text)),
        "invalid_search": text.count("Code.INVALID_ARGUMENT: invalid search request"),
        "not_found": text.count("Code.NOT_FOUND: file not found"),
        "denied_security_lines": text.count("OUTCOME_DENIED_SECURITY"),
        "action_gate": len(re.findall(r"action_gate|HIGH-RISK", text)),
        "submitted": "Submitted: run_id=" in text,
        "final_line": next((line for line in reversed(text.splitlines()) if line.startswith("FINAL: ")), ""),
        "api_line": next((line for line in reversed(text.splitlines()) if line.startswith("API: ")), ""),
        "verifier_api_line": next(
            (line for line in reversed(text.splitlines()) if line.startswith("Verifier API: ")), ""
        ),
    }


def load_history_summary() -> dict | None:
    if not RUN_HISTORY_PATH.exists():
        return None
    data = read_json_retry(RUN_HISTORY_PATH)
    if not isinstance(data, list):
        return None
    candidates = [
        item
        for item in data
        if isinstance(item, dict)
        and item.get("benchmark_id") == BENCHMARK_ID
        and item.get("timestamp", "") >= STARTED_AT.isoformat()
    ]
    if not candidates:
        return None
    return candidates[-1]


def summarize_tasks(tasks: list[dict]) -> dict:
    times = [task["total_time_ms"] for task in tasks if task["total_time_ms"] is not None]
    verdicts = Counter(task["verdict"] for task in tasks)
    langs = Counter(task["language"] for task in tasks)
    by_type = Counter(task["kind"] for task in tasks)

    en_times = [task["total_time_ms"] for task in tasks if task["language"] == "en" and task["total_time_ms"] is not None]
    non_en_times = [
        task["total_time_ms"] for task in tasks if task["language"] != "en" and task["total_time_ms"] is not None
    ]

    low_action = [task for task in tasks if task["tool_step_ratio"] < 0.3]
    slow = sorted(
        [task for task in tasks if task["total_time_ms"] is not None],
        key=lambda item: (item["total_time_ms"], task_sort_key(item["task_id"])),
        reverse=True,
    )
    exhausted = [task for task in tasks if task["step_count"] >= task["budget"]]

    per_type = defaultdict(list)
    for task in tasks:
        if task["total_time_ms"] is not None:
            per_type[task["kind"]].append(task["total_time_ms"])
    type_medians = sorted(
        (
            {
                "kind": kind,
                "count": len(items),
                "median_ms": int(statistics.median(items)),
                "max_steps": max(task["step_count"] for task in tasks if task["kind"] == kind),
                "budget": BUDGETS[kind],
            }
            for kind, items in per_type.items()
        ),
        key=lambda item: item["median_ms"],
        reverse=True,
    )

    return {
        "count": len(tasks),
        "times": times,
        "p50_ms": int(statistics.median(times)) if times else None,
        "p90_ms": percentile(times, 0.9),
        "verdicts": verdicts,
        "langs": langs,
        "by_type": by_type,
        "non_en_ratio": (
            round(statistics.mean(non_en_times) / statistics.mean(en_times), 2)
            if en_times and non_en_times
            else None
        ),
        "avg_tool_step_ratio": round(
            sum(task["tool_step_ratio"] for task in tasks) / len(tasks), 2
        )
        if tasks
        else 0.0,
        "low_action": low_action,
        "slow_top10": slow[:10],
        "budget_exhausted": exhausted,
        "type_medians": type_medians,
    }


def build_issues(summary: dict, log_stats: dict) -> list[dict]:
    issues = []

    exhausted = summary["budget_exhausted"]
    if exhausted:
        multi = [task for task in exhausted if task["kind"] == "multi_step"]
        if multi:
            impact = len(multi)
            issues.append(
                {
                    "title": "Recurring birthday lookups hit the multi-step ceiling",
                    "evidence": ", ".join(
                        f"{task['task_id']} ({task['step_count']}/{task['budget']}, {ms_to_s(task['total_time_ms'])})"
                        for task in multi[:5]
                    ),
                    "impact": f"{impact} tasks affected (~{impact / TOTAL_TASKS * 100:.1f}% of benchmark)",
                    "hypothesis": "The next-birthday tasks are doing broad entity scans and date disambiguation, exhausting the 25-step budget before a shorter route is learned.",
                    "fix_class": "code",
                    "complexity": "low (<30 lines)",
                    "delta": f"ceiling +{impact / TOTAL_TASKS * 100:.1f}pp",
                    "priority": "P0 (must-fix for next run)",
                }
            )

    inbox_type = next((item for item in summary["type_medians"] if item["kind"] == "inbox_processing"), None)
    if inbox_type and inbox_type["median_ms"] >= 150000:
        impact = summary["by_type"]["inbox_processing"]
        issues.append(
            {
                "title": "Inbox-processing path is materially slower than the rest of the mix",
                "evidence": f"median {ms_to_s(inbox_type['median_ms'])}; max_steps {inbox_type['max_steps']}/{inbox_type['budget']}; slow tasks include t015, t046, t047",
                "impact": f"{impact} tasks affected (~{impact / TOTAL_TASKS * 100:.1f}% of benchmark)",
                "hypothesis": "The agent is paying a heavy read/workflow setup tax before acting on inbox items, especially on ambiguous 'next item/message' prompts.",
                "fix_class": "prompt",
                "complexity": "medium",
                "delta": f"unclear; broad ceiling +{impact / TOTAL_TASKS * 100:.1f}pp",
                "priority": "P1",
            }
        )

    denied = sum(count for verdict, count in summary["verdicts"].items() if verdict.startswith("denied_"))
    total = summary["count"] or 1
    denied_ratio = denied / total
    if denied_ratio > 0.20:
        issues.append(
            {
                "title": "Verifier looks over-blocking in blind mode",
                "evidence": f"{denied}/{total} denied_* verdicts ({denied_ratio * 100:.1f}%)",
                "impact": f"{denied} tasks affected (~{denied / TOTAL_TASKS * 100:.1f}% of benchmark)",
                "hypothesis": "Legitimate ambiguity or workflow conflicts are probably being escalated into denial decisions too aggressively.",
                "fix_class": "prompt",
                "complexity": "medium",
                "delta": f"unclear; ceiling +{denied / TOTAL_TASKS * 100:.1f}pp",
                "priority": "P1",
            }
        )

    err_total = sum(count for verdict, count in summary["verdicts"].items() if verdict.startswith("err_"))
    if err_total / total > 0.10:
        issues.append(
            {
                "title": "Internal error outcomes are too frequent",
                "evidence": ", ".join(f"{k}={v}" for k, v in summary["verdicts"].items() if k.startswith("err_")),
                "impact": f"{err_total} tasks affected (~{err_total / TOTAL_TASKS * 100:.1f}% of benchmark)",
                "hypothesis": "There is a verifier or agent internal failure mode that is escaping retry/recovery logic.",
                "fix_class": "code",
                "complexity": "medium",
                "delta": f"ceiling +{err_total / TOTAL_TASKS * 100:.1f}pp",
                "priority": "P0 (must-fix for next run)",
            }
        )

    invalid_total = log_stats["invalid_search"] + log_stats["not_found"]
    if invalid_total >= 10:
        issues.append(
            {
                "title": "Tool targeting is leaking avoidable invalid-search / not-found calls",
                "evidence": f"invalid_search={log_stats['invalid_search']}, not_found={log_stats['not_found']}",
                "impact": "Spread across multiple workers; each miss burns budget and latency",
                "hypothesis": "The planner is still issuing untargeted search calls or optimistic reads before narrowing the path.",
                "fix_class": "prompt",
                "complexity": "low (<30 lines)",
                "delta": "unclear; likely latency win before direct score win",
                "priority": "P1",
            }
        )

    non_en_ratio = summary["non_en_ratio"]
    non_en_count = summary["langs"]["cjk"] + summary["langs"]["cyrillic"] + summary["langs"]["spanish"]
    if non_en_ratio is not None and non_en_count >= 4 and non_en_ratio > 2.0:
        issues.append(
            {
                "title": "Multilingual handling is a bottleneck",
                "evidence": f"non-EN={non_en_count}, non-EN/EN mean time ratio={non_en_ratio}x",
                "impact": f"{non_en_count} tasks affected (~{non_en_count / TOTAL_TASKS * 100:.1f}% of benchmark)",
                "hypothesis": "Language parsing or instruction normalization is slowing planning enough to matter on the multilingual slice.",
                "fix_class": "prompt",
                "complexity": "medium",
                "delta": f"unclear; ceiling +{non_en_count / TOTAL_TASKS * 100:.1f}pp",
                "priority": "P1",
            }
        )

    return issues


def build_questions(summary: dict, log_stats: dict, issues: list[dict], stalled_cycles: int) -> list[str]:
    questions = []
    if summary["budget_exhausted"]:
        questions.append(
            "Q1: Confirm whether step-budget tuning for the recurring next-birthday tasks should outrank verifier tuning in the post-run fix window."
        )
    else:
        questions.append(
            "Q1: Confirm whether to keep prioritizing process-signal analysis over manual per-task log inspection until the run finishes."
        )

    invalid_total = log_stats["invalid_search"] + log_stats["not_found"]
    questions.append(
        f"Q2: There are {invalid_total} avoidable tool misses in the log so far; after the run, should we treat that as a prompt-only pass first or open code-level planner fixes immediately?"
    )

    if stalled_cycles >= 2:
        questions.append(
            "URGENT Q3: Progress has not advanced for two observer cycles while the log still lacks a submit marker; please sanity-check the main window for a stalled worker pool."
        )
    elif not issues:
        questions.append(
            "Q3: No strong failure cluster yet from process signals alone; after real scores land, should we compare directly against the 74.42% dev baseline before proposing any fix batch?"
        )

    return questions


def key_observation(summary: dict, issues: list[dict]) -> str:
    if issues:
        return issues[0]["title"]
    if summary["slow_top10"]:
        slowest = summary["slow_top10"][0]
        return f"Slowest completed task so far is {slowest['task_id']} at {ms_to_s(slowest['total_time_ms'])}."
    return "No issues yet."


def format_snapshot(now: datetime, elapsed_seconds: float, progress: int, rate: float, log_stats: dict, issues: list[dict], finished: bool, number: int) -> str:
    remaining = max(0, TOTAL_TASKS - progress)
    eta = "n/a" if rate <= 0 else human_duration(remaining / rate * 60)
    return "\n".join(
        [
            f"### Snapshot {number} — {now.strftime('%H:%M')} UTC (elapsed {human_duration(elapsed_seconds)})",
            f"- Progress: {progress}/{TOTAL_TASKS} ({progress / TOTAL_TASKS * 100:.1f}%)",
            f"- Rate: {rate:.2f} tasks/min — ETA: {eta}",
            f"- Process: {'FINISHED' if finished else 'ALIVE'}",
            f"- Worker errors: {log_stats['worker_errors']}",
            f"- Key observation: {key_observation({'slow_top10': []}, issues) if issues else 'No issues yet.'}",
        ]
    )


def load_existing_snapshots() -> tuple[str, int]:
    if not OUTPUT_PATH.exists():
        return "", 0
    text = OUTPUT_PATH.read_text(errors="replace")
    match = re.search(r"## Snapshots \(append-only\)\n\n(.*?)\n## Pattern findings", text, re.S)
    if not match:
        return "", 0
    block = match.group(1).strip()
    count = len(re.findall(r"^### Snapshot \d+", block, re.M))
    return block, count


def render_report(snapshot_block: str, summary: dict, log_stats: dict, issues: list[dict], questions: list[str], finished: bool, history_summary: dict | None) -> str:
    progress = summary["count"]
    now = datetime.now(UTC)
    elapsed_seconds = (now - STARTED_AT).total_seconds()
    rate = progress / (elapsed_seconds / 60.0) if elapsed_seconds > 0 else 0.0
    slow_types = ", ".join(
        f"{item['kind']} ({ms_to_s(item['median_ms'])}, n={item['count']})"
        for item in summary["type_medians"][:3]
    ) or "none yet"

    exhausted = (
        ", ".join(
            f"{task['task_id']} ({task['step_count']}/{task['budget']})"
            for task in summary["budget_exhausted"][:10]
        )
        if summary["budget_exhausted"]
        else "none yet"
    )

    low_action = (
        ", ".join(
            f"{task['task_id']} ({task['tool_step_ratio']:.2f})"
            for task in summary["low_action"][:10]
        )
        if summary["low_action"]
        else "none yet"
    )

    denied = sum(count for verdict, count in summary["verdicts"].items() if verdict.startswith("denied_"))
    err_total = sum(count for verdict, count in summary["verdicts"].items() if verdict.startswith("err_"))
    total = summary["count"] or 1
    denied_signal = (
        f"yes ({denied}/{total}, {denied / total * 100:.1f}%)"
        if denied / total > 0.20
        else f"no ({denied}/{total}, {denied / total * 100:.1f}%)"
    )

    en = summary["langs"]["en"]
    non_en = summary["langs"]["cjk"] + summary["langs"]["cyrillic"] + summary["langs"]["spanish"]
    ratio = f"{summary['non_en_ratio']}x" if summary["non_en_ratio"] is not None else "n/a"

    lines = [
        f"# Live run analysis — {RUN_ID}",
        "",
        f"**Benchmark:** {BENCHMARK_ID} ({TOTAL_TASKS} tasks, EVAL_POLICY_BLIND)",
        f"**Run name:** {RUN_NAME}",
        f"**Started:** {STARTED_AT.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "**Config:** RUN_PROFILE=final, PARALLEL=8, Sonnet-4.6 + Haiku-4.5",
        "",
        "## Snapshots (append-only)",
        "",
        snapshot_block,
        "",
        "## Pattern findings",
        "",
        "### Timing distribution (updated as data grows)",
        f"- median: {ms_to_s(summary['p50_ms'])}, p90: {ms_to_s(summary['p90_ms'])}",
        f"- Budget-exhausted tasks: {exhausted}",
        f"- Slow task types: {slow_types}",
        "",
        "### Tool intensity",
        f"- avg tool/step: {summary['avg_tool_step_ratio']:.2f}",
        f"- Low-action tasks (ratio <0.3): {low_action}",
        "",
        "### Verifier verdicts",
        f"- ok: {summary['verdicts']['ok']}, denied_security: {summary['verdicts']['denied_security']}, err_*: {err_total}, unknown: {summary['verdicts']['unknown']}",
        f"- Over-denial signal: {denied_signal}",
        "",
        "### Language mix",
        f"- EN: {en}, non-EN: {non_en}",
        f"- non-EN time ratio vs EN: {ratio}",
        "",
        "## Observed issues (prioritized)",
        "",
    ]

    if issues:
        for idx, issue in enumerate(issues, start=1):
            lines.extend(
                [
                    f"### ISSUE-{idx} — {issue['title']}",
                    f"- **Evidence:** {issue['evidence']}",
                    f"- **Impact:** {issue['impact']}",
                    f"- **Hypothesis:** {issue['hypothesis']}",
                    f"- **Fix class:** {issue['fix_class']}",
                    f"- **Fix complexity:** {issue['complexity']}",
                    f"- **Estimated score delta:** {issue['delta']}",
                    f"- **Priority:** {issue['priority']}",
                    "",
                ]
            )
    else:
        lines.extend(["No issues yet from process signals alone.", ""])

    lines.extend(["## Questions for main window", ""])
    for q in questions:
        lines.append(f"- [ ] {q}")

    lines.extend(["", "## Post-run action plan", ""])

    if finished:
        history_line = "Run history not yet updated."
        if history_summary:
            history_line = (
                f"Run history score: {history_summary.get('tasks_passed', '?')}/{history_summary.get('tasks_total', '?')} "
                f"({history_summary.get('score_pct', '?')}%)."
            )
        blind_note = (
            "Real scores still appear suppressed in blind mode; verify on bitgn.com after the blind window closes."
            if history_summary and history_summary.get("tasks_total") and all(
                (task.get("score", 0.0) == 0.0) for task in history_summary.get("tasks", {}).values()
            )
            else "Use run_history and bitgn.com together for the real-score check."
        )
        lines.extend(
            [
                "## Post-run action plan — second blind run",
                "",
                f"- Gap vs dev baseline: dev baseline is {DEV_BASELINE_PCT}% on pac1-dev; compare final prod score against that after blind scores unlock.",
                f"- {history_line}",
                f"- {blind_note}",
                "",
                "### Top fixes (sorted by expected impact)",
                "",
            ]
        )
        if issues:
            for idx, issue in enumerate(issues, start=1):
                if "birthday" in issue["title"].lower():
                    target_files = "pac1-py/classify.py, pac1-py/strategy.py"
                    validation = "Re-run the recurring birthday prompts locally and confirm step_count drops below 25."
                elif "inbox-processing" in issue["title"].lower():
                    target_files = "pac1-py/workspace/prompts/fragments/inbox_processing.md, pac1-py/strategy.py"
                    validation = "Replay representative 'next inbox/message' tasks and check median time / step_count."
                elif "tool targeting" in issue["title"].lower():
                    target_files = "pac1-py/workspace/prompts/system.md, pac1-py/workspace/prompts/fragments/reasoning.md"
                    validation = "Confirm invalid search / not-found counts disappear on a smoke slice."
                else:
                    target_files = "pac1-py/verify.py, pac1-py/second_opinion.py"
                    validation = "Replay affected tasks and inspect verifier verdict distribution."
                lines.extend(
                    [
                        f"#### FIX-{idx} — {issue['title']}",
                        f"- **Target files:** {target_files}",
                        f"- **Diff size:** ~{'20-40' if issue['complexity'] != 'high' else '60+'} lines",
                        f"- **Rationale:** {issue['hypothesis']}",
                        f"- **Expected impact:** {issue['delta']}",
                        "- **Risk:** Reclassification or prompt tightening may move behavior on nearby task families; verify on a smoke slice first.",
                        f"- **Validation:** {validation}",
                        "",
                    ]
                )
        else:
            lines.extend(["No fix batch proposed yet because process signals stayed inconclusive.", ""])

        lines.extend(
            [
                "### Launch checklist для второго прогона",
                "- [ ] Все FIX-* применены и syntax-verified",
                '- [ ] `uv run python -c "import main"` — imports clean',
                "- [ ] `.env.final` не менялся",
                "- [ ] `BITGN_API_KEY` в `.env`",
                '- [ ] Предыдущий run.run_id сохранён где-то',
                "- [ ] Свободный log path подготовлен",
                "- [ ] Готовность к ~30-50 min wall clock",
                "",
                "### Вопросы к главному пилоту",
                "- Одобрение на применение FIX-* из списка выше",
                "- Решение о моменте запуска второго blind run",
                "- Подтверждение по PARALLEL=8 vs PARALLEL=4",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Pending run completion. Real scores will be checked from `docs/run_history.json` and bitgn.com after `SubmitRun(force=True)` lands.",
                "",
            ]
        )

    lines.extend(
        [
            "## Reference notes",
            "",
            f"- Log lines: {log_stats['line_count']}",
            f"- Starting task hits: {log_stats['starts']}",
            f"- Next step hits: {log_stats['next_steps']}",
            f"- Invalid search hits: {log_stats['invalid_search']}",
            f"- Not-found hits: {log_stats['not_found']}",
            f"- Stagnation/oscillation hits: {log_stats['stagnation']}",
            f"- action_gate/HIGH-RISK hits: {log_stats['action_gate']}",
            f"- denied_security lines in log: {log_stats['denied_security_lines']}",
        ]
    )
    if log_stats["final_line"]:
        lines.append(f"- Final aggregate: {log_stats['final_line']}")
    if log_stats["api_line"]:
        lines.append(f"- API summary: {log_stats['api_line']}")
    if log_stats["verifier_api_line"]:
        lines.append(f"- Verifier API summary: {log_stats['verifier_api_line']}")
    if BASELINE_PATH.exists():
        lines.append(f"- Dev baseline reference: {BASELINE_PATH.relative_to(ROOT)}")
    lines.append("")
    return "\n".join(lines)


def observe_once(stalled_cycles: int = 0) -> tuple[int, bool]:
    tasks = load_run_tasks()
    summary = summarize_tasks(tasks)
    log_stats = load_log_stats()
    finished = bool(log_stats["submitted"] or log_stats["final_line"] or summary["count"] >= TOTAL_TASKS)
    existing_snapshots, previous_count = load_existing_snapshots()
    snapshot_number = previous_count + 1
    now = datetime.now(UTC)
    elapsed_seconds = (now - STARTED_AT).total_seconds()
    rate = summary["count"] / (elapsed_seconds / 60.0) if elapsed_seconds > 0 else 0.0
    issues = build_issues(summary, log_stats)
    questions = build_questions(summary, log_stats, issues, stalled_cycles)
    snapshot = format_snapshot(
        now=now,
        elapsed_seconds=elapsed_seconds,
        progress=summary["count"],
        rate=rate,
        log_stats=log_stats,
        issues=issues,
        finished=finished,
        number=snapshot_number,
    )
    snapshot_block = f"{existing_snapshots}\n\n{snapshot}".strip() if existing_snapshots else snapshot
    history_summary = load_history_summary() if finished else None
    report = render_report(snapshot_block, summary, log_stats, issues, questions, finished, history_summary)
    OUTPUT_PATH.write_text(report)
    return summary["count"], finished


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=270)
    args = parser.parse_args()

    last_progress = None
    stalled_cycles = 0

    while True:
        progress, finished = observe_once(stalled_cycles=stalled_cycles)
        if progress == last_progress and not finished:
            stalled_cycles += 1
        else:
            stalled_cycles = 0
        last_progress = progress

        if finished or not args.loop:
            return 0
        time.sleep(max(60, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
