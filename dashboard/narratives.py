"""Template-based narrative generation for dashboard."""

from __future__ import annotations

from dataclasses import dataclass


# ── Outcome explanations ─────────────────────────────────────────────────────

OUTCOME_EXPLANATIONS = {
    "OUTCOME_OK": "выполнил задачу",
    "OUTCOME_DENIED_SECURITY": "обнаружил угрозу и отклонил задачу",
    "OUTCOME_NONE_UNSUPPORTED": "корректно определил, что операция не поддерживается",
    "OUTCOME_NONE_CLARIFICATION": "запросил уточнение (задача неоднозначна)",
    "OUTCOME_ERR_INTERNAL": "столкнулся с внутренней ошибкой",
}

OUTCOME_LABELS = {
    "OUTCOME_OK": "OK",
    "OUTCOME_DENIED_SECURITY": "DENIED_SECURITY",
    "OUTCOME_NONE_UNSUPPORTED": "UNSUPPORTED",
    "OUTCOME_NONE_CLARIFICATION": "CLARIFICATION",
    "OUTCOME_ERR_INTERNAL": "INTERNAL_ERROR",
}


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class TaskLifecycle:
    task_id: str
    instruction: str
    current_score: float
    stability: str  # "3/3", "2/5", etc.
    pass_rate: float
    category: str  # task type from classification
    threat: str
    # From latest run log
    answer_message: str
    answer_outcome: str
    answer_steps: list  # completed_steps_laconic
    score_detail: list
    # History
    score_history: list  # [(timestamp, score)]
    # Cycle involvement
    cycles_targeting: list  # [{timestamp, category, observation}]
    fixes_applied: list
    redteam_mentions: list
    # Generated
    narrative: str


@dataclass
class RunDigest:
    timestamp: str
    score_pct: float
    verdict: str
    model: str
    narrative: str
    improvements: list  # task IDs
    regressions: list  # task IDs
    still_failing: list  # task IDs
    key_events: list  # short descriptions


# ── Narrative generators ─────────────────────────────────────────────────────


def generate_run_narrative(
    eval_report,
    prev_eval,
    analysis_reports: list,
    git_commits: list,  # noqa: ARG001 — reserved for future commit attribution
) -> RunDigest:
    """Generate a plain-language RunDigest from structured eval data."""
    ts = eval_report.timestamp
    score = eval_report.score_pct
    verdict = eval_report.verdict
    model = eval_report.model
    delta = eval_report.delta_pct

    improvements = []
    regressions = []
    still_failing = []

    for t in eval_report.tasks:
        if t.delta > 0:
            improvements.append(t.task_id)
        elif t.delta < 0:
            regressions.append(t.task_id)
        elif t.curr < 1.0:
            still_failing.append(t.task_id)

    parts = []

    # Opening line
    if verdict == "REGRESSED":
        parts.append(f"Этот прогон потерял {len(regressions)} задач (дельта {delta:+.0f}%).")
    elif verdict == "IMPROVED":
        parts.append(f"Улучшение: +{len(improvements)} задач (дельта {delta:+.0f}%).")
    elif verdict == "IMPROVED_WITH_REGRESSION":
        parts.append(
            f"Смешанный результат: +{len(improvements)} улучшений, "
            f"но -{len(regressions)} регрессий "
            f"(дельта {delta:+.0f}%)."
        )
    elif verdict == "NEUTRAL":
        parts.append("Без изменений относительно предыдущего прогона.")
    else:
        parts.append(f"Результат: {score:.0f}%.")

    # Fix attribution
    if eval_report.fix_attribution:
        attr_lines = eval_report.fix_attribution.strip().split("\n")
        summary = attr_lines[0][:200] if attr_lines else ""
        if summary:
            parts.append(f"Изменения: {summary}")

    # Reverted?
    if verdict == "REGRESSED":
        parts.append("Изменения откатили из-за регрессии.")

    # Key events from analysis reports matching this timestamp
    key_events = []
    for a in analysis_reports:
        if a.timestamp == ts or a.timestamp[:10] == ts[:10]:
            key_events.append(f"{a.category}: {a.target_task} — {a.summary[:100]}")

    narrative = "\n\n".join(parts)

    return RunDigest(
        timestamp=ts,
        score_pct=score,
        verdict=verdict,
        model=model,
        narrative=narrative,
        improvements=improvements,
        regressions=regressions,
        still_failing=still_failing,
        key_events=key_events,
    )


def generate_task_narrative(lifecycle: TaskLifecycle) -> str:
    """Generate a plain-language summary for a single task."""
    parts = []

    # Instruction summary
    instr = lifecycle.instruction
    if instr:
        if len(instr) > 120:
            instr = instr[:117] + "..."
        parts.append(f'Задача {lifecycle.task_id}: "{instr}"')
    else:
        parts.append(f"Задача {lifecycle.task_id} (инструкция не найдена)")

    # Stability
    if lifecycle.pass_rate >= 1.0:
        parts.append(f"Проходит стабильно ({lifecycle.stability}).")
    elif lifecycle.pass_rate == 0:
        parts.append(f"Никогда не проходила ({lifecycle.stability}).")
    else:
        pct = lifecycle.pass_rate * 100
        parts.append(f"Нестабильна — проходит {pct:.0f}% прогонов ({lifecycle.stability}).")

    # Latest answer
    if lifecycle.answer_outcome:
        expl = OUTCOME_EXPLANATIONS.get(
            lifecycle.answer_outcome,
            lifecycle.answer_outcome,
        )
        parts.append(f"В последнем прогоне агент {expl}.")
        if lifecycle.answer_message:
            msg = lifecycle.answer_message
            if len(msg) > 200:
                msg = msg[:197] + "..."
            parts.append(f'Ответ: "{msg}"')

    # Score detail
    if lifecycle.score_detail:
        details = "; ".join(lifecycle.score_detail[:3])
        parts.append(f"Детали оценки: {details}")

    # Cycles targeting this task
    if lifecycle.cycles_targeting:
        count = len(lifecycle.cycles_targeting)
        latest = lifecycle.cycles_targeting[-1]
        parts.append(
            f"Analyst смотрел на эту задачу {count} раз(а). "
            f"Последний: {latest.get('timestamp', '?')} — "
            f"{latest.get('category', '?')}: "
            f"{latest.get('observation', '')[:100]}"
        )

    # Fixes
    if lifecycle.fixes_applied:
        parts.append(f"Применённые фиксы: {'; '.join(lifecycle.fixes_applied[:3])}")

    return "\n\n".join(parts)
