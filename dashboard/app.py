"""BitGN PAC — Command Center Dashboard."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from parsers import (
    load_analysis_reports,
    load_eval_reports,
    load_opt_reports,
    load_redteam_reports,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BitGN PAC — Command Center",
    layout="wide",
    initial_sidebar_state="collapsed",
)

COMPETITION_DATE = date(2026, 4, 11)

# ── Load data ─────────────────────────────────────────────────────────────────

evals = load_eval_reports()
analyses = load_analysis_reports()
redteams = load_redteam_reports()
opts = load_opt_reports()

latest_eval = evals[-1] if evals else None
latest_analysis = analyses[-1] if analyses else None
latest_redteam = redteams[-1] if redteams else None
latest_opt = opts[-1] if opts else None

# ── Header ────────────────────────────────────────────────────────────────────

st.title("BitGN PAC — Command Center")

col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
with col1:
    st.caption(
        "PCDRED optimization dashboard · "
        "auto-reads docs/eval/, docs/analysis/, docs/redteam/, docs/optimization/"
    )
with col2:
    score = latest_eval.score_pct if latest_eval else 0.0
    delta = latest_eval.delta_pct if latest_eval else 0.0
    delta_str = f"{delta:+.0f}%" if delta != 0 else None
    st.metric("Current Score", f"{score:.0f}%", delta_str)
with col3:
    passed = latest_eval.tasks_passed if latest_eval else 0
    st.metric("Tasks Passed", f"{passed}/25")
with col4:
    days_left = (COMPETITION_DATE - date.today()).days
    st.metric("Days to Competition", days_left)

st.divider()

# ── Row 1: Score Timeline + Task Heatmap ──────────────────────────────────────

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Score Timeline")
    dated_evals = [r for r in evals if len(r.timestamp) == 13]  # YYYY-MM-DD-HH only
    if len(dated_evals) >= 1:
        color_map = {
            "IMPROVED": "#22c55e",
            "IMPROVED_WITH_REGRESSION": "#84cc16",
            "NEUTRAL": "#94a3b8",
            "REGRESSED": "#ef4444",
            "UNKNOWN": "#94a3b8",
        }
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[r.timestamp for r in dated_evals],
            y=[r.score_pct for r in dated_evals],
            mode="lines+markers",
            marker=dict(
                size=12,
                color=[color_map.get(r.verdict, "#94a3b8") for r in dated_evals],
                line=dict(width=1.5, color="white"),
            ),
            line=dict(color="#6366f1", width=2.5),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Score: %{y:.0f}%<br>"
                "<extra></extra>"
            ),
        ))
        fig.update_layout(
            yaxis=dict(range=[0, 100], title="Score (%)", gridcolor="#2d2d2d"),
            xaxis=dict(title="", tickangle=-20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Legend
        leg_cols = st.columns(4)
        leg_cols[0].caption("🟢 IMPROVED")
        leg_cols[1].caption("🟡 +REGRESSION")
        leg_cols[2].caption("⚪ NEUTRAL")
        leg_cols[3].caption("🔴 REGRESSED")
    else:
        st.info("No dated eval runs to plot. Run a PCDRED cycle first.")

with col_right:
    st.subheader("Task Status — Latest Run")
    if latest_eval and latest_eval.tasks:
        task_map = {t.task_id: t.curr for t in latest_eval.tasks}
        cells = []
        for i in range(1, 26):
            tid = f"t{i:02d}"
            score_val = task_map.get(tid)
            if score_val is None:
                cells.append(("❓", "#64748b", tid))
            elif score_val >= 1.0:
                cells.append(("✓", "#22c55e", tid))
            else:
                cells.append(("✗", "#ef4444", tid))

        for row in range(5):
            cols = st.columns(5)
            for col_i in range(5):
                idx = row * 5 + col_i
                icon, color, tid = cells[idx]
                cols[col_i].markdown(
                    f"<div style='text-align:center; padding:8px 4px; border-radius:6px; "
                    f"background:{color}22; border:1px solid {color}66; margin:2px'>"
                    f"<span style='font-size:16px'>{icon}</span><br>"
                    f"<span style='font-size:11px; color:{color}; font-family:monospace'>{tid}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        st.caption(f"Run: {latest_eval.timestamp} · Model: {latest_eval.model}")
    else:
        st.info("No eval report available.")

st.divider()

# ── Row 2: Latest Analysis + Red Team + Optimization ─────────────────────────

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.subheader("Latest Analysis")
    if latest_analysis and latest_analysis.target_task != "unknown":
        cat_icons = {
            "STAGNATION": "🔄",
            "PROTOCOL": "📋",
            "SECURITY": "🔒",
            "TOOL_ERROR": "🔧",
            "SIDE_EFFECT": "⚠️",
            "EDGE_CASE": "🎯",
        }
        icon = cat_icons.get(latest_analysis.category, "❓")
        st.markdown(
            f"**{icon} {latest_analysis.category}** — Task `{latest_analysis.target_task}`"
        )
        st.caption(f"Cycle: {latest_analysis.timestamp}")
        if latest_analysis.summary:
            st.write(latest_analysis.summary)
    elif latest_analysis:
        st.caption(f"Cycle: {latest_analysis.timestamp}")
        st.write(f"Category: {latest_analysis.category}")
    else:
        st.info("No analysis reports found.")

with col_b:
    st.subheader("Red Team Status")
    if latest_redteam and latest_redteam.attacks:
        rating_counts = {"BLOCKED": 0, "PARTIAL": 0, "BYPASSES": 0}
        for a in latest_redteam.attacks:
            rating_counts[a.rating] = rating_counts.get(a.rating, 0) + 1

        c1, c2, c3 = st.columns(3)
        c1.metric("Blocked", rating_counts["BLOCKED"])
        c2.metric("Partial", rating_counts["PARTIAL"])
        c3.metric("Bypasses", rating_counts["BYPASSES"])

        st.caption(
            f"Cycle: {latest_redteam.timestamp} · "
            f"{len(latest_redteam.attacks)} attacks analyzed"
        )
        for a in latest_redteam.attacks:
            badge = {"BLOCKED": "🟢", "PARTIAL": "🟡", "BYPASSES": "🔴"}.get(a.rating, "⚪")
            target_txt = a.target[:60] if a.target else "—"
            st.caption(f"{badge} Attack {a.number}: **{a.rating}** — {target_txt}")
    elif latest_redteam:
        st.caption(f"Cycle: {latest_redteam.timestamp}")
        st.info("No attack data parsed (legacy format).")
    else:
        st.info("No red team reports found.")

with col_c:
    st.subheader("Optimization Queue")
    if latest_opt and latest_opt.recommendations:
        st.caption(f"Cycle: {latest_opt.timestamp}")
        for rec in latest_opt.recommendations:
            st.markdown(f"- {rec}")
    elif latest_opt:
        st.caption(f"Cycle: {latest_opt.timestamp}")
        st.info("No structured recommendations extracted.")
    else:
        st.info("No optimization reports found.")

st.divider()

# ── Row 3: PCDRED Pipeline ────────────────────────────────────────────────────

st.subheader("PCDRED Pipeline")
pipe_cols = st.columns(5)
stages = ["Analyst", "Architect", "Red Team", "Optimizer", "Evaluator"]
stage_icons = ["🔍", "🏗️", "🎯", "⚡", "📊"]
for col, stage, icon in zip(pipe_cols, stages, stage_icons):
    col.markdown(
        f"<div style='text-align:center; padding:12px; border-radius:8px; "
        f"border:1px solid #334155; background:#0f172a'>"
        f"<div style='font-size:24px'>{icon}</div>"
        f"<div style='font-size:13px; font-weight:600; margin-top:4px'>{stage}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ── Row 4: Cycle History ──────────────────────────────────────────────────────

st.subheader("Cycle History")
if evals:
    verdict_badge = {
        "IMPROVED": "🟢 IMPROVED",
        "IMPROVED_WITH_REGRESSION": "🟡 IMPROVED+REG",
        "NEUTRAL": "⚪ NEUTRAL",
        "REGRESSED": "🔴 REGRESSED",
        "UNKNOWN": "❓ UNKNOWN",
    }
    df_history = pd.DataFrame([
        {
            "Run": r.timestamp,
            "Verdict": verdict_badge.get(r.verdict, r.verdict),
            "Score": f"{r.score_pct:.0f}%",
            "Delta": f"{r.delta_pct:+.0f}%" if r.delta_pct != 0 else "—",
            "Passed": f"{r.tasks_passed}/25",
            "Model": r.model,
        }
        for r in reversed(evals)
    ])
    st.dataframe(df_history, use_container_width=True, hide_index=True)
else:
    st.info("No eval reports found.")

# ── Footer ────────────────────────────────────────────────────────────────────

st.caption(
    f"Data: docs/eval/ ({len(evals)} runs) · "
    f"docs/analysis/ ({len(analyses)}) · "
    f"docs/redteam/ ({len(redteams)}) · "
    f"docs/optimization/ ({len(opts)}) · "
    f"Reload page to refresh"
)
