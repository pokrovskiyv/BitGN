"""BitGN PAC — Command Center Dashboard (v3.1: Dense Table + Insights)."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from log_parser import load_all_run_logs
from narratives import OUTCOME_EXPLANATIONS, OUTCOME_LABELS
from parsers import (
    build_task_lifecycle,
    build_task_table_df,
    collect_task_ids,
    compute_dashboard_summary,
    extract_task_metrics_df,
    is_complete_run,
    load_analysis_reports,
    load_eval_reports,
    load_narrative_reports,
    load_opt_reports,
    load_redteam_reports,
    load_run_history,
    load_task_cache,
)

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BitGN PAC — Command Center",
    layout="wide",
    initial_sidebar_state="collapsed",
)

COMPETITION_DATE = date(2026, 4, 11)
REFRESH_INTERVAL_MS = 30_000  # auto-refresh every 30s

st_autorefresh(interval=REFRESH_INTERVAL_MS, key="data_refresh")

# ── Load data ────────────────────────────────────────────────────────────────

evals = load_eval_reports()
analyses = load_analysis_reports()
redteams = load_redteam_reports()
opts = load_opt_reports()
task_cache = load_task_cache()
run_history = load_run_history()
run_logs = load_all_run_logs()
narratives = load_narrative_reports()

latest_eval = evals[-1] if evals else None
latest_analysis = analyses[-1] if analyses else None

latest_log_key = sorted(run_logs.keys())[-1] if run_logs else None
latest_traces = run_logs.get(latest_log_key, []) if latest_log_key else []
trace_map = {t.task_id: t for t in latest_traces}

# Per-task stability from eval reports
task_scores_all: dict = {}
for e in evals:
    for t in e.tasks:
        task_scores_all.setdefault(t.task_id, []).append(t.curr)

targeted_task = latest_analysis.target_task if latest_analysis else None

# Pre-computed summary for insights
summary = compute_dashboard_summary(evals, task_scores_all)

# ── Section A: Header ────────────────────────────────────────────────────────

st.title("BitGN PAC — Command Center")

bar1, bar2, bar3, bar4 = st.columns([1, 1, 1, 1])
with bar1:
    score = latest_eval.score_pct if latest_eval else 0.0
    if summary.is_current_best:
        delta_str = "рекорд ★"
    elif summary.best_score_pct > 0:
        delta_str = f"{summary.delta_from_best:+.0f}% от рекорда {summary.best_score_pct:.0f}%"
    else:
        delta_str = None
    st.metric("Счёт", f"{score:.0f}%", delta_str, delta_color="off")
with bar2:
    passed = latest_eval.tasks_passed if latest_eval else 0
    total_tasks = latest_eval.tasks_total if latest_eval and latest_eval.tasks_total > 0 else passed
    remaining = max(total_tasks - passed, 0)
    st.metric("Задачи", f"{passed}/{total_tasks}", f"{remaining} осталось" if total_tasks else None)
with bar3:
    days_left = (COMPETITION_DATE - date.today()).days
    st.metric("До соревнования", f"{days_left} дн.")
with bar4:
    api_runs = [r for r in run_history if r.cost_usd > 0]
    total_spent = sum(r.cost_usd for r in api_runs)
    last_cost = api_runs[-1].cost_usd if api_runs else 0.0
    st.metric(
        "Потрачено", f"${total_spent:.2f}", f"${last_cost:.2f} последний" if last_cost else None
    )

# Next action
if latest_eval and latest_eval.verdict == "REGRESSED":
    action = "Откатить последние изменения (REGRESSED)"
    st.error(f"⚡ Следующий шаг: {action}")
elif latest_analysis and latest_eval:
    if latest_analysis.dt > latest_eval.dt:
        st.warning("⚡ Следующий шаг: Запустить evaluator — фикс уже в коде")
    elif latest_eval.next_priorities:
        action = f"Новый цикл: {latest_eval.next_priorities[0][:60]}"
        st.info(f"⚡ Следующий шаг: {action}")
    else:
        st.info("⚡ Следующий шаг: Запустить make run для нового прогона")
else:
    st.info("⚡ Следующий шаг: Запустить make run для первого прогона")

# PCDRED cycle status
if analyses:
    latest_ts = analyses[-1].timestamp
    has_analyst = any(a.timestamp == latest_ts for a in analyses)
    has_redteam = any(r.timestamp == latest_ts for r in redteams)
    has_optimizer = any(o.timestamp == latest_ts for o in opts)
    has_eval = any(e.timestamp == latest_ts or e.timestamp[:10] == latest_ts[:10] for e in evals)
    stages = [
        ("Analyst", has_analyst),
        ("Architect", has_analyst),
        ("Red Team", has_redteam),
        ("Optimizer", has_optimizer),
        ("Evaluator", has_eval),
    ]
    pills_text = "  ".join(f"{'✓' if done else '☐'} {name}" for name, done in stages)
    st.caption(f"PCDRED: {pills_text}  ·  Цикл {latest_ts}")

# ── Insights ─────────────────────────────────────────────────────────────────

_insights: list = []
if summary.is_current_best and summary.best_score_pct > 0:
    _insights.append(f"★ Рекорд {summary.best_score_pct:.0f}%")
if summary.improvements:
    _insights.append(f"▲ {', '.join(summary.improvements)} (+{summary.improvement_count})")
if summary.regressions:
    _insights.append(f"▼ {', '.join(summary.regressions)} упали")
clusters_text = " · ".join(
    f"{cause}: {', '.join(tasks)}" for cause, tasks in summary.failure_clusters.items()
)
if clusters_text:
    _insights.append(f"Провалы — {clusters_text}")
if summary.bottleneck_desc:
    _insights.append(
        f"Bottleneck: {summary.bottleneck_desc} → "
        f"+{summary.bottleneck_points * 4}pp (→{summary.projected_score_pct:.0f}%)"
    )
if _insights:
    st.caption(" │ ".join(_insights))

st.divider()

# ── Score Trend Chart ────────────────────────────────────────────────────────

# Only show full benchmark runs on the trend chart — partial runs distort the trend.
current_benchmark_total = max(
    (
        r.benchmark_task_count or r.tasks_total
        for r in run_history
        if is_complete_run(r)
    ),
    default=0,
)
dated_evals = [
    r
    for r in evals
    if len(r.timestamp) == 13 and current_benchmark_total > 0 and r.tasks_total == current_benchmark_total
]
if dated_evals:
    color_map = {
        "IMPROVED": "#22c55e",
        "IMPROVED_WITH_REGRESSION": "#84cc16",
        "NEUTRAL": "#94a3b8",
        "REGRESSED": "#ef4444",
        "UNKNOWN": "#94a3b8",
    }
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[r.timestamp for r in dated_evals],
            y=[r.score_pct for r in dated_evals],
            mode="lines+markers",
            marker=dict(
                size=10,
                color=[color_map.get(r.verdict, "#94a3b8") for r in dated_evals],
                line=dict(width=1.5, color="white"),
            ),
            line=dict(color="#6366f1", width=2),
        )
    )
    fig.update_layout(
        yaxis=dict(range=[0, 100], title="Счёт (%)", gridcolor="#2d2d2d"),
        xaxis=dict(tickangle=-20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        height=150,
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Section: Run Detail (per-task metrics) ───────────────────────────────────

selected_run = None
if run_history:
    st.subheader("Детали прогона")
    run_options = [
        f"{r.timestamp[:19]}  —  {r.score_pct:.0f}% ({r.tasks_passed}/{r.tasks_total})  [{r.model.split('/')[-1][:30]}]"
        for r in reversed(run_history)
    ]
    selected_run_label = st.selectbox("Прогон", options=run_options, index=0)
    selected_run_idx = run_options.index(selected_run_label)
    selected_run = list(reversed(run_history))[selected_run_idx]

    has_metrics = any(td.get("metrics") for td in selected_run.tasks.values())
    if has_metrics:
        metrics_df = extract_task_metrics_df(selected_run)

        def _color_score_col(val: str) -> str:
            if val == "PASS":
                return "color: #22c55e"
            if val == "FAIL":
                return "color: #ef4444"
            return "font-weight: bold"

        st.dataframe(
            metrics_df.style.map(_color_score_col, subset=["Score"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Метрики для этого прогона недоступны (старый формат данных)")

st.divider()

# ── Section B: Task Table ────────────────────────────────────────────────────

st.subheader("Задачи")

df = build_task_table_df(
    task_scores_all,
    latest_eval,
    task_cache,
    trace_map,
    targeted_task,
    summary.task_deltas,
)


def _color_delta(val: str) -> str:
    if val == "▲":
        return "color: #22c55e"
    if val == "▼":
        return "color: #ef4444"
    return ""


styled_df = df.style.map(_color_delta, subset=["Δ"])
st.dataframe(styled_df, use_container_width=True, hide_index=True)

# Task selection — default to first failing task
task_ids = collect_task_ids(
    task_scores_all,
    latest_eval,
    task_cache,
    trace_map,
    summary.task_deltas,
    targeted_task,
)
selected = None
if task_ids:
    failing_ids = [
        tid for tid in task_ids if (scores := task_scores_all.get(tid)) and scores[-1] < 1.0
    ]
    default_idx = task_ids.index(failing_ids[0]) if failing_ids else 0
    selected = st.selectbox(
        "Подробности задачи",
        options=task_ids,
        index=default_idx,
        placeholder="Выбрать задачу...",
    )
else:
    st.caption("Список задач пока пуст.")

# ── Section C: Task Detail Panel ─────────────────────────────────────────────

if selected:
    trace = trace_map.get(selected)
    lc = build_task_lifecycle(
        selected,
        evals,
        analyses,
        redteams,
        task_cache,
        trace,
    )

    st.divider()

    instr_short = lc.instruction[:80] if lc.instruction else "—"
    st.subheader(f'{selected} — "{instr_short}"')

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Балл", f"{lc.current_score:.1f}", lc.stability)
    c2.metric("Тип", lc.category)
    c3.metric("Win rate", f"{lc.pass_rate * 100:.0f}%")
    outcome_label = OUTCOME_LABELS.get(lc.answer_outcome, lc.answer_outcome)
    c4.metric("Результат", outcome_label or "—")

    if lc.answer_outcome:
        expl = OUTCOME_EXPLANATIONS.get(lc.answer_outcome, lc.answer_outcome)
        st.markdown(f"**Агент:** {expl}")
    if lc.answer_message:
        st.markdown(f"> {lc.answer_message[:200]}")

    if lc.score_detail:
        st.warning(" · ".join(lc.score_detail[:3]))

    if lc.score_history:
        marks = "".join("✓" if s >= 1.0 else "✗" for _, s in lc.score_history)
        st.caption(f"История: {marks} ({lc.stability})")

    # Per-step detail — prefer stored metrics, fallback to log traces
    stored_steps = []
    if selected_run and selected in selected_run.tasks:
        stored_steps = selected_run.tasks[selected].get("metrics", {}).get("steps", [])

    if stored_steps:
        with st.expander(
            f"Итерации: {len(stored_steps)} шагов",
            expanded=False,
        ):
            step_rows = [
                {
                    "#": s["step"],
                    "Инструмент": s.get("tool", ""),
                    "Аргументы": s.get("args", "")[:50],
                    "План": s.get("plan", "")[:50],
                    "Planning": f"{s.get('planning_ms', 0) / 1000:.1f}s",
                    "Dispatch": f"{s.get('dispatch_ms', 0)}ms",
                    "Всего": f"{(s.get('planning_ms', 0) + s.get('dispatch_ms', 0)) / 1000:.1f}s",
                }
                for s in stored_steps
            ]
            st.dataframe(pd.DataFrame(step_rows), use_container_width=True, hide_index=True)
    elif trace and trace.steps:
        with st.expander(
            f"Трейс: {trace.step_count} шагов, "
            f"{trace.total_time_ms / 1000:.1f}с, "
            f"бюджет {trace.step_count}/{trace.max_steps}",
            expanded=False,
        ):
            rows = [
                {
                    "#": s.step_num,
                    "Инструмент": s.tool,
                    "План": s.plan_brief[:60],
                    "Время": f"{s.timing_ms / 1000:.1f}с",
                    "События": " ".join("🛡️" if ev == "GATE" else "🔴" for ev in s.events) or "—",
                }
                for s in trace.steps
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Raw trace JSON
    if selected_run and selected in selected_run.tasks:
        import json

        raw_data = selected_run.tasks[selected]
        with st.expander("Raw trace", expanded=False):
            st.code(json.dumps(raw_data, indent=2, ensure_ascii=False), language="json")

    # Comparison with previous run
    if selected_run and run_history and len(run_history) >= 2:
        rev = list(reversed(run_history))
        run_idx = rev.index(selected_run) if selected_run in rev else -1
        prev_run = rev[run_idx + 1] if 0 <= run_idx < len(rev) - 1 else None
        if prev_run and selected in prev_run.tasks:
            prev_td = prev_run.tasks[selected]
            prev_m = prev_td.get("metrics", {})
            cur_m = selected_run.tasks.get(selected, {}).get("metrics", {})
            if prev_m and cur_m:
                step_delta = cur_m.get("step_count", 0) - prev_m.get("step_count", 0)
                time_delta = (
                    cur_m.get("total_time_ms", 0) - prev_m.get("total_time_ms", 0)
                ) / 1000
                prev_score = prev_td.get("score", 0)
                cur_score = selected_run.tasks[selected].get("score", 0)
                status_change = "нет"
                if cur_score >= 1 and prev_score < 1:
                    status_change = "PASS ▲"
                elif cur_score < 1 and prev_score >= 1:
                    status_change = "FAIL ▼"
                st.caption(
                    f"Δ vs пред. прогон: статус {status_change} · "
                    f"шаги Δ {step_delta:+d} · время Δ {time_delta:+.1f}s"
                )

    if lc.cycles_targeting:
        latest_cycle = lc.cycles_targeting[-1]
        st.caption(
            f"Analyst: {latest_cycle['timestamp']} — "
            f"{latest_cycle['category']}: "
            f"{latest_cycle['observation'][:120]}"
        )

    if lc.redteam_mentions:
        st.caption(f"Red Team: {lc.redteam_mentions[-1]}")

st.divider()

# ── Narrative ────────────────────────────────────────────────────────────────

if narratives:
    latest_narr = narratives[-1]
    with st.expander(f"Разбор прогона — {latest_narr.timestamp}", expanded=False):
        st.markdown(latest_narr.content)

# ── Footer ───────────────────────────────────────────────────────────────────

st.caption(
    f"Данные: docs/eval/ ({len(evals)}) · "
    f"docs/analysis/ ({len(analyses)}) · "
    f"docs/redteam/ ({len(redteams)}) · "
    f"docs/optimization/ ({len(opts)}) · "
    f"docs/run_logs/ ({len(run_logs)}) · "
    f"Перезагрузи страницу для обновления"
)
