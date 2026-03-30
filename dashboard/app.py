"""BitGN PAC — Command Center Dashboard (v2)."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from log_parser import load_all_run_logs
from narratives import OUTCOME_EXPLANATIONS, OUTCOME_LABELS
from parsers import (
    build_run_digests,
    build_task_lifecycle,
    load_analysis_reports,
    load_eval_reports,
    load_git_log,
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

# ── Load data ────────────────────────────────────────────────────────────────

evals = load_eval_reports()
analyses = load_analysis_reports()
redteams = load_redteam_reports()
opts = load_opt_reports()
task_cache = load_task_cache()
run_history = load_run_history()
run_logs = load_all_run_logs()
git_commits = load_git_log()

latest_eval = evals[-1] if evals else None
latest_analysis = analyses[-1] if analyses else None

# Build aggregated data
run_digests = build_run_digests(evals, analyses, git_commits)

# Latest traces for task lifecycle
latest_log_key = sorted(run_logs.keys())[-1] if run_logs else None
latest_traces = run_logs.get(latest_log_key, []) if latest_log_key else []
trace_map = {t.task_id: t for t in latest_traces}

# ── Helpers ──────────────────────────────────────────────────────────────────


def _format_redteam(report) -> str:
    if not report.attacks:
        return "Нет данных об атаках."
    badge_map = {"BLOCKED": "🟢", "PARTIAL": "🟡", "BYPASSES": "🔴"}
    counts: dict = {}
    for a in report.attacks:
        counts[a.rating] = counts.get(a.rating, 0) + 1
    summary_parts = [f"{badge_map.get(r, '⚪')} {r}: {c}" for r, c in counts.items()]
    lines = [" · ".join(summary_parts)]
    for a in report.attacks:
        badge = {"BLOCKED": "🟢", "PARTIAL": "🟡", "BYPASSES": "🔴"}.get(
            a.rating,
            "⚪",
        )
        lines.append(f"{badge} Атака {a.number}: **{a.rating}** — {a.target}")
    return "\n\n".join(lines)


# ── Layer 1: Command Bar ─────────────────────────────────────────────────────

st.title("BitGN PAC — Command Center")

bar1, bar2, bar3, bar4 = st.columns([1, 1, 1, 2])
with bar1:
    score = latest_eval.score_pct if latest_eval else 0.0
    delta = latest_eval.delta_pct if latest_eval else 0.0
    delta_str = f"{delta:+.0f}%" if latest_eval else None
    st.metric("Счёт", f"{score:.0f}%", delta_str)
with bar2:
    passed = latest_eval.tasks_passed if latest_eval else 0
    remaining = 25 - passed
    st.metric("Задачи", f"{passed}/25", f"{remaining} осталось")
with bar3:
    days_left = (COMPETITION_DATE - date.today()).days
    st.metric("До соревнования", f"{days_left} дн.")
with bar4:
    # Next action logic
    if latest_eval and latest_eval.verdict == "REGRESSED":
        action = "Откатить последние изменения (REGRESSED)"
        action_color = "#ef4444"
    elif latest_analysis and latest_eval:
        if latest_analysis.dt > latest_eval.dt:
            action = "Запустить evaluator — фикс уже в коде"
            action_color = "#f59e0b"
        elif latest_eval.next_priorities:
            action = f"Новый цикл: {latest_eval.next_priorities[0][:60]}"
            action_color = "#3b82f6"
        else:
            action = "Запустить make run для нового прогона"
            action_color = "#6366f1"
    else:
        action = "Запустить make run для первого прогона"
        action_color = "#6366f1"
    st.markdown(
        f"<div style='padding:8px 12px; border-radius:6px; "
        f"border:1px solid {action_color}66; background:{action_color}11'>"
        f"<span style='color:{action_color}; font-weight:600'>⚡ Следующий шаг:</span> "
        f"<span style='color:#e2e8f0'>{action}</span></div>",
        unsafe_allow_html=True,
    )

# Cycle status pills
if analyses:
    latest_ts = analyses[-1].timestamp
    has_analyst = any(a.timestamp == latest_ts for a in analyses)
    has_redteam = any(r.timestamp == latest_ts for r in redteams)
    has_optimizer = any(o.timestamp == latest_ts for o in opts)
    has_eval = any(e.timestamp == latest_ts or e.timestamp[:10] == latest_ts[:10] for e in evals)
    stages = [
        ("Analyst", has_analyst),
        ("Architect", has_analyst),  # architect runs if analyst ran
        ("Red Team", has_redteam),
        ("Optimizer", has_optimizer),
        ("Evaluator", has_eval),
    ]
    pills = " ".join(
        f"<span style='padding:2px 8px; border-radius:4px; font-size:12px; "
        f"background:{'#22c55e22' if done else '#33415522'}; "
        f"border:1px solid {'#22c55e66' if done else '#33415566'}; "
        f"color:{'#22c55e' if done else '#64748b'}'>"
        f"{'✓' if done else '⬜'} {name}</span>"
        for name, done in stages
    )
    st.markdown(
        f"<div style='margin-top:4px; font-size:12px; color:#94a3b8'>"
        f"Цикл {latest_ts}: {pills}</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ── Layer 2: Task Grid ───────────────────────────────────────────────────────

st.subheader("Задачи")

# Compute per-task stability from eval reports
task_scores_all = {}
for e in evals:
    for t in e.tasks:
        task_scores_all.setdefault(t.task_id, []).append(t.curr)

targeted_task = latest_analysis.target_task if latest_analysis else None

grid_cols = st.columns(5)
for i in range(25):
    tid = f"t{i + 1:02d}"
    col = grid_cols[i % 5]
    scores = task_scores_all.get(tid, [])
    passes = sum(1 for s in scores if s >= 1.0)
    total = len(scores)
    latest_score = scores[-1] if scores else -1

    if tid == targeted_task:
        color, icon = "#f59e0b", "🎯"
        border = f"border:2px solid #f59e0b"
    elif latest_score >= 1.0:
        color, icon = "#22c55e", "✓"
        border = "border:1px solid #22c55e66"
    elif latest_score >= 0:
        color, icon = "#ef4444", "✗"
        border = "border:1px solid #ef444466"
    else:
        color, icon = "#64748b", "❓"
        border = "border:1px solid #33415566"

    stability_text = f"{passes}/{total}" if total > 0 else "—"
    stability_color = "#eab308" if 0 < passes < total else color

    col.markdown(
        f"<div style='text-align:center; padding:6px 2px; border-radius:6px; "
        f"background:{color}15; {border}; margin:2px; cursor:pointer'>"
        f"<span style='font-size:15px'>{icon}</span><br>"
        f"<span style='font-size:11px; color:{color}; font-family:monospace'>"
        f"{tid}</span><br>"
        f"<span style='font-size:9px; color:{stability_color}'>"
        f"{stability_text}</span></div>",
        unsafe_allow_html=True,
    )

st.caption(
    "🟢 проходит · 🔴 проваливается · 🟡 нестабильно · 🎯 в работе · Число = прошла/всего прогонов"
)

# ── Task Deep-Dive Panel ─────────────────────────────────────────────────────

task_ids = [f"t{i:02d}" for i in range(1, 26)]
selected = st.selectbox(
    "Выбрать задачу для подробного разбора",
    options=task_ids,
    index=None,
    placeholder="Нажми чтобы выбрать задачу…",
)

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

    # Header
    outcome_label = OUTCOME_LABELS.get(lc.answer_outcome, lc.answer_outcome)
    cat_badge = f"{lc.category}" if lc.category != "unknown" else ""
    threat_badge = f" · threat={lc.threat}" if lc.threat and lc.threat != "none" else ""

    hdr1, hdr2, hdr3 = st.columns([1, 1, 1])
    with hdr1:
        status_icon = "✅" if lc.current_score >= 1.0 else "❌"
        st.metric(
            f"{selected} {status_icon}",
            f"{lc.current_score:.1f}",
            lc.stability,
        )
    with hdr2:
        st.markdown(f"**Тип:** {cat_badge}{threat_badge}")
        if outcome_label:
            st.markdown(f"**Результат:** {outcome_label}")
    with hdr3:
        st.markdown(f"**Стабильность:** {lc.stability}")
        st.markdown(f"**Win rate:** {lc.pass_rate * 100:.0f}%")

    # Section A: Instruction & Answer
    with st.expander("📋 Инструкция и ответ агента", expanded=True):
        if lc.instruction:
            st.markdown(f"**Задание:** {lc.instruction}")
        if lc.answer_outcome:
            expl = OUTCOME_EXPLANATIONS.get(
                lc.answer_outcome,
                lc.answer_outcome,
            )
            st.markdown(f"**Агент {expl}.**")
        if lc.answer_message:
            st.info(f"💬 {lc.answer_message}")
        if lc.answer_steps:
            st.markdown("**Шаги агента:**")
            for step in lc.answer_steps:
                st.markdown(f"- {step}")
        if lc.score_detail:
            st.markdown("**Почему такой балл:**")
            for detail in lc.score_detail:
                st.warning(f"⚠️ {detail}")

    # Section B: Execution Trace
    if trace and trace.steps:
        with st.expander(
            f"🔍 Трейс выполнения — {trace.step_count} шагов, {trace.total_time_ms / 1000:.1f}с",
            expanded=False,
        ):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Шаги", trace.step_count)
            m2.metric("Время", f"{trace.total_time_ms / 1000:.1f}с")
            m3.metric("Бюджет", f"{trace.step_count}/{trace.max_steps}")
            m4.metric(
                "LLM ошибки",
                trace.events_summary.get("LLM_ERROR", 0),
            )
            rows = [
                {
                    "#": s.step_num,
                    "Инструмент": s.tool,
                    "План": s.plan_brief[:60],
                    "Время": f"{s.timing_ms / 1000:.1f}с",
                    "События": " ".join("🛡️" if e == "GATE" else "🔴" for e in s.events) or "—",
                }
                for s in trace.steps
            ]
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

    # Section C: History
    if lc.score_history:
        with st.expander("📈 История по прогонам", expanded=False):
            fig_h = go.Figure()
            ts_list = [h[0] for h in lc.score_history]
            sc_list = [h[1] for h in lc.score_history]
            fig_h.add_trace(
                go.Scatter(
                    x=ts_list,
                    y=sc_list,
                    mode="lines+markers",
                    marker=dict(
                        size=10,
                        color=["#22c55e" if s >= 1.0 else "#ef4444" for s in sc_list],
                        line=dict(width=1.5, color="white"),
                    ),
                    line=dict(color="#6366f1", width=2),
                )
            )
            fig_h.update_layout(
                yaxis=dict(
                    range=[-0.1, 1.1],
                    tickvals=[0, 0.5, 1.0],
                    gridcolor="#2d2d2d",
                ),
                xaxis=dict(tickangle=-20),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
                height=200,
            )
            st.plotly_chart(fig_h, use_container_width=True)

            if lc.cycles_targeting:
                st.markdown("**Циклы, смотревшие на эту задачу:**")
                for c in lc.cycles_targeting:
                    st.caption(
                        f"📎 {c['timestamp']} — **{c['category']}**: {c['observation'][:120]}"
                    )

    # Section D: Narrative
    with st.expander("💡 Сводка на понятном языке", expanded=True):
        st.markdown(lc.narrative)

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_runs, tab_pipeline, tab_analytics = st.tabs(
    ["📋 Прогоны", "🔄 PCDRED Pipeline", "📊 Аналитика"]
)

# ── Tab 1: Run Digests ───────────────────────────────────────────────────────

with tab_runs:
    verdict_badges = {
        "IMPROVED": "🟢",
        "IMPROVED_WITH_REGRESSION": "🟡",
        "NEUTRAL": "⚪",
        "REGRESSED": "🔴",
        "UNKNOWN": "❓",
    }
    if run_digests:
        for idx, digest in enumerate(reversed(run_digests)):
            badge = verdict_badges.get(digest.verdict, "❓")
            with st.expander(
                f"{badge} {digest.timestamp} — {digest.score_pct:.0f}% "
                f"({digest.verdict}) · {digest.model}",
                expanded=(idx == 0),
            ):
                st.markdown(digest.narrative)
                if digest.improvements:
                    st.success(f"Улучшились: {', '.join(digest.improvements)}")
                if digest.regressions:
                    st.error(f"Регрессии: {', '.join(digest.regressions)}")
                if digest.still_failing:
                    st.warning(f"Не проходят: {', '.join(digest.still_failing)}")
                if digest.key_events:
                    st.caption("Ключевые события:")
                    for ev in digest.key_events:
                        st.caption(f"  · {ev}")
    else:
        st.info("Нет eval-отчётов. Запустите make run.")

# ── Tab 2: PCDRED Pipeline (live) ───────────────────────────────────────────

with tab_pipeline:
    latest_redteam = redteams[-1] if redteams else None
    latest_opt = opts[-1] if opts else None

    pipe_cols = st.columns(5)
    stages_data = [
        (
            "🔍 Analyst",
            latest_analysis,
            (
                f"**{latest_analysis.category}** → "
                f"`{latest_analysis.target_task}`\n\n"
                f"{latest_analysis.summary[:200]}"
            )
            if latest_analysis
            else None,
        ),
        (
            "🏗️ Architect",
            latest_analysis,
            (f"Фикс для {latest_analysis.target_task}\n\nСм. последний commit с `fix:` в git log")
            if latest_analysis
            else None,
        ),
        (
            "🎯 Red Team",
            latest_redteam,
            _format_redteam(latest_redteam) if latest_redteam else None,
        ),
        (
            "⚡ Optimizer",
            latest_opt,
            "\n".join(f"- {r}" for r in (latest_opt.recommendations or []))
            if latest_opt
            else None,
        ),
        (
            "📊 Evaluator",
            latest_eval,
            (
                f"**{latest_eval.verdict}** — "
                f"{latest_eval.score_pct:.0f}% "
                f"({latest_eval.delta_pct:+.0f}%)"
            )
            if latest_eval
            else None,
        ),
    ]

    for col, (name, report, content) in zip(pipe_cols, stages_data):
        ts = report.timestamp if report else "—"
        has_data = report is not None
        border_color = "#22c55e" if has_data else "#334155"
        bg = "#22c55e08" if has_data else "#0f172a"
        col.markdown(
            f"<div style='text-align:center; padding:10px; "
            f"border-radius:8px; border:1px solid {border_color}; "
            f"background:{bg}; min-height:80px'>"
            f"<div style='font-size:16px'>{name}</div>"
            f"<div style='font-size:10px; color:#64748b'>{ts}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Expandable details per stage
    for name, report, content in stages_data:
        if content:
            with st.expander(f"{name} — подробности"):
                st.markdown(content)

    # Cycle selector
    if analyses:
        cycle_options = [a.timestamp for a in reversed(analyses)]
        selected_cycle = st.selectbox(
            "Посмотреть другой цикл",
            cycle_options,
            index=0,
        )
        cycle_analysis = next(
            (a for a in analyses if a.timestamp == selected_cycle),
            None,
        )
        if cycle_analysis:
            st.markdown(
                f"**Цикл {selected_cycle}**: "
                f"{cycle_analysis.category} → "
                f"`{cycle_analysis.target_task}` — "
                f"{cycle_analysis.summary[:200]}"
            )

# ── Tab 3: Analytics ─────────────────────────────────────────────────────────

with tab_analytics:
    sub_timeline, sub_heatmap, sub_cats, sub_prio = st.tabs(
        ["Тренд", "Стабильность", "Категории ошибок", "Приоритеты"]
    )

    with sub_timeline:
        dated_evals = [r for r in evals if len(r.timestamp) == 13]
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
                        size=12,
                        color=[color_map.get(r.verdict, "#94a3b8") for r in dated_evals],
                        line=dict(width=1.5, color="white"),
                    ),
                    line=dict(color="#6366f1", width=2.5),
                )
            )
            fig.update_layout(
                yaxis=dict(
                    range=[0, 100],
                    title="Счёт (%)",
                    gridcolor="#2d2d2d",
                ),
                xaxis=dict(title="", tickangle=-20),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
            )
            st.plotly_chart(fig, use_container_width=True)
            cols = st.columns(4)
            cols[0].caption("🟢 IMPROVED")
            cols[1].caption("🟡 +REGRESSION")
            cols[2].caption("⚪ NEUTRAL")
            cols[3].caption("🔴 REGRESSED")
        else:
            st.info("Нет прогонов с датами.")

    with sub_heatmap:
        dated = [e for e in evals if e.tasks and len(e.timestamp) == 13]
        if dated:
            hm_data = []
            for e in dated:
                for t in e.tasks:
                    hm_data.append({"Run": e.timestamp, "Task": t.task_id, "Score": t.curr})
            hm_df = pd.DataFrame(hm_data)
            pivot = hm_df.pivot(index="Task", columns="Run", values="Score").fillna(-1)
            pivot = pivot.reindex(sorted(pivot.index, key=lambda x: int(x[1:])))
            fig_hm = go.Figure(
                data=go.Heatmap(
                    z=pivot.values,
                    x=pivot.columns.tolist(),
                    y=pivot.index.tolist(),
                    colorscale=[
                        [0.0, "#1e1e1e"],
                        [0.45, "#ef4444"],
                        [0.55, "#ef4444"],
                        [1.0, "#22c55e"],
                    ],
                    zmin=-1,
                    zmax=1,
                )
            )
            fig_hm.update_layout(
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
                height=600,
            )
            st.plotly_chart(fig_hm, use_container_width=True)
        else:
            st.info("Нет данных для heatmap.")

    with sub_cats:
        if analyses:
            cat_counts = {}
            for a in analyses:
                cat_counts[a.category] = cat_counts.get(a.category, 0) + 1
            cat_colors = {
                "STAGNATION": "#eab308",
                "PROTOCOL": "#3b82f6",
                "SECURITY": "#ef4444",
                "TOOL_ERROR": "#f97316",
                "SIDE_EFFECT": "#a855f7",
                "EDGE_CASE": "#22d3ee",
            }
            fig_cat = go.Figure(
                data=go.Bar(
                    x=list(cat_counts.keys()),
                    y=list(cat_counts.values()),
                    marker_color=[cat_colors.get(c, "#94a3b8") for c in cat_counts],
                )
            )
            fig_cat.update_layout(
                yaxis=dict(title="Отчётов", gridcolor="#2d2d2d"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
            )
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("Нет analysis-отчётов.")

    with sub_prio:
        if latest_eval and latest_eval.next_priorities:
            st.caption(f"Из eval {latest_eval.timestamp}")
            for i, prio in enumerate(latest_eval.next_priorities, 1):
                st.markdown(f"**{i}.** {prio}")
        else:
            st.info("Нет приоритетов.")

# ── Footer ───────────────────────────────────────────────────────────────────

st.caption(
    f"Данные: docs/eval/ ({len(evals)}) · "
    f"docs/run_history.json ({len(run_history)}) · "
    f"docs/analysis/ ({len(analyses)}) · "
    f"docs/redteam/ ({len(redteams)}) · "
    f"docs/run_logs/ ({len(run_logs)}) · "
    f"Перезагрузи страницу для обновления"
)
