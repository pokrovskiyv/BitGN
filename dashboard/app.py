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
    load_run_history,
    load_task_cache,
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
task_cache = load_task_cache()
run_history = load_run_history()

latest_eval = evals[-1] if evals else None
latest_analysis = analyses[-1] if analyses else None
latest_redteam = redteams[-1] if redteams else None
latest_opt = opts[-1] if opts else None

# ── Header ────────────────────────────────────────────────────────────────────

st.title("BitGN PAC — Command Center")

h1, h2, h3, h4, h5, h6 = st.columns([3, 1, 1, 1, 1, 1])
with h1:
    st.caption(
        "PCDRED · docs/eval/ + docs/run_history.json · Reload page to refresh"
    )
with h2:
    score = latest_eval.score_pct if latest_eval else 0.0
    delta = latest_eval.delta_pct if latest_eval else 0.0
    delta_str = f"{delta:+.0f}%" if delta != 0 else None
    st.metric("Score", f"{score:.0f}%", delta_str)
with h3:
    passed = latest_eval.tasks_passed if latest_eval else 0
    st.metric("Passed", f"{passed}/25")
with h4:
    days_left = (COMPETITION_DATE - date.today()).days
    st.metric("Days Left", days_left)
with h5:
    st.metric("Runs Logged", len(run_history))
with h6:
    if len(run_history) >= 2:
        trend = run_history[-1].score_pct - run_history[-2].score_pct
        trend_str = f"{trend:+.1f}%" if trend != 0 else "—"
        st.metric("Trend", f"{run_history[-1].score_pct:.0f}%", trend_str)
    else:
        st.metric("Trend", "—")

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

# ── Row 2: Weak Spots + Latest Analyst ───────────────────────────────────────

col_weak, col_analyst = st.columns([1, 1])

with col_weak:
    st.subheader("Weak Spots")
    complete_runs = [r for r in run_history if r.tasks_total >= 25]
    if len(complete_runs) >= 2:
        task_scores: dict = {}
        for run in complete_runs:
            for tid, tdata in run.tasks.items():
                task_scores.setdefault(tid, []).append(float(tdata.get("score", 0.0)))

        weak = {tid: sc for tid, sc in task_scores.items() if min(sc) < 1.0}
        weak_sorted = sorted(
            weak.items(),
            key=lambda kv: (sum(kv[1]) / len(kv[1]), -len(kv[1])),
        )

        if weak_sorted:
            ws_df = pd.DataFrame([
                {
                    "Task": tid,
                    "Win Rate": f"{sum(sc)/len(sc)*100:.0f}%",
                    "Runs": len(sc),
                    "Last": "✓" if sc[-1] >= 1.0 else "✗",
                }
                for tid, sc in weak_sorted[:12]
            ])
            st.dataframe(ws_df, use_container_width=True, hide_index=True)
        else:
            st.success("All logged tasks passing consistently.")
    elif len(complete_runs) == 1:
        st.info("Need 2+ complete runs to compute weak spots.")
    else:
        st.info("No run_history.json data yet. Run `make run` once.")

with col_analyst:
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
            f"**{icon} {latest_analysis.category}** — Task `{latest_analysis.target_task}`  "
            f"  \n_Cycle: {latest_analysis.timestamp}_"
        )
        if latest_analysis.summary:
            with st.expander("Full Observation", expanded=True):
                st.markdown(latest_analysis.summary)
    elif latest_analysis:
        st.caption(f"Cycle: {latest_analysis.timestamp}")
        st.write(f"Category: {latest_analysis.category}")
    else:
        st.info("No analysis reports found.")

st.divider()

# ── Row 3: Run Comparison ─────────────────────────────────────────────────────

st.subheader("Run Comparison")
if len(run_history) >= 2:
    run_labels = [
        f"{r.timestamp[:19]}  {r.score_pct:.0f}%  ({r.tasks_passed}/{r.tasks_total})"
        for r in run_history
    ]
    rc1, rc2, _ = st.columns([2, 2, 3])
    with rc1:
        run_a_label = st.selectbox(
            "Run A (baseline)", run_labels, index=len(run_labels) - 2, key="run_a"
        )
    with rc2:
        run_b_label = st.selectbox(
            "Run B (compare)", run_labels, index=len(run_labels) - 1, key="run_b"
        )

    run_a = run_history[run_labels.index(run_a_label)]
    run_b = run_history[run_labels.index(run_b_label)]

    all_tids = sorted(set(list(run_a.tasks) + list(run_b.tasks)))
    comp_rows = []
    for tid in all_tids:
        sa = float(run_a.tasks.get(tid, {}).get("score", 0.0))
        sb = float(run_b.tasks.get(tid, {}).get("score", 0.0))
        d = sb - sa
        comp_rows.append({
            "Task": tid,
            "Run A": f"{sa:.2f}",
            "Run B": f"{sb:.2f}",
            "Delta": f"+{d:.2f}" if d > 0 else (f"{d:.2f}" if d < 0 else "—"),
        })

    comp_df = pd.DataFrame(comp_rows)

    def _color_delta(val):
        if isinstance(val, str) and val.startswith("+"):
            return "color: #22c55e; font-weight: bold"
        if isinstance(val, str) and val.startswith("-"):
            return "color: #ef4444; font-weight: bold"
        return "color: #94a3b8"

    styled = comp_df.style.map(_color_delta, subset=["Delta"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    improved = sum(1 for r in comp_rows if r["Delta"].startswith("+"))
    regressed = sum(1 for r in comp_rows if r["Delta"].startswith("-"))
    st.caption(
        f"A: {run_a.score_pct:.0f}% ({run_a.tasks_passed}/{run_a.tasks_total})  |  "
        f"B: {run_b.score_pct:.0f}% ({run_b.tasks_passed}/{run_b.tasks_total})  |  "
        f"Improved: {improved}  Regressed: {regressed}"
    )
else:
    st.info("Need 2+ runs in run_history.json to compare. Run `make run` at least twice.")

st.divider()

# ── Task Inspector ────────────────────────────────────────────────────────────

if latest_eval and latest_eval.tasks:
    task_ids = [t.task_id for t in sorted(latest_eval.tasks, key=lambda t: t.task_id)]
    selected = st.selectbox(
        "Inspect task",
        options=task_ids,
        index=None,
        placeholder="Select a task to see instruction, score detail, and history…",
    )
    if selected:
        task_score_obj = next((t for t in latest_eval.tasks if t.task_id == selected), None)
        cached = task_cache.get(selected)

        col_info, col_detail, col_hist = st.columns([1, 2, 2])

        with col_info:
            if task_score_obj:
                status_icon = "✅" if task_score_obj.curr >= 1.0 else "❌"
                st.metric("Score", f"{task_score_obj.curr:.2f}", task_score_obj.status)
                st.markdown(f"**Status:** {status_icon} {task_score_obj.status}")
            if cached:
                st.caption(
                    f"Model: {cached.get('model', '—')}  "
                    f"  \n{cached.get('timestamp', '')[:10]}"
                )

        with col_detail:
            if cached:
                with st.expander("📋 Task Instruction", expanded=True):
                    st.text(cached["instruction"])
                if cached.get("score_detail"):
                    with st.expander("📊 Score Detail (why this score)", expanded=True):
                        for line in cached["score_detail"]:
                            st.markdown(f"- {line}")
            else:
                st.info(
                    "Task details not available yet. "
                    "They will appear after the next benchmark run (`make run`)."
                )

        with col_hist:
            hist_scores = []
            hist_ts = []
            for run in run_history:
                if selected in run.tasks:
                    hist_scores.append(float(run.tasks[selected].get("score", 0.0)))
                    hist_ts.append(run.timestamp[:16])

            if hist_scores:
                st.markdown(f"**History — {selected}**")
                fig_h = go.Figure()
                fig_h.add_trace(go.Scatter(
                    x=hist_ts,
                    y=hist_scores,
                    mode="lines+markers",
                    marker=dict(
                        size=10,
                        color=["#22c55e" if s >= 1.0 else "#ef4444" for s in hist_scores],
                        line=dict(width=1.5, color="white"),
                    ),
                    line=dict(color="#6366f1", width=2),
                    hovertemplate="<b>%{x}</b><br>Score: %{y:.2f}<extra></extra>",
                ))
                fig_h.update_layout(
                    yaxis=dict(range=[-0.1, 1.1], tickvals=[0, 0.5, 1.0], gridcolor="#2d2d2d"),
                    xaxis=dict(tickangle=-20),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=220,
                )
                st.plotly_chart(fig_h, use_container_width=True)
                pass_count = sum(1 for s in hist_scores if s >= 1.0)
                st.caption(
                    f"Win rate: {pass_count}/{len(hist_scores)} "
                    f"({pass_count/len(hist_scores)*100:.0f}%)"
                )
            else:
                st.info("No history yet — appears after first `make run`.")

st.divider()

# ── PCDRED Pipeline ────────────────────────────────────────────────────────────

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

# ── Agent Reports + Cycle History ────────────────────────────────────────────

tab_rt, tab_opt, tab_hist = st.tabs(["Red Team", "Optimization", "Cycle History"])

with tab_rt:
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
            target_txt = a.target[:80] if a.target else "—"
            st.caption(f"{badge} Attack {a.number}: **{a.rating}** — {target_txt}")
    elif latest_redteam:
        st.caption(f"Cycle: {latest_redteam.timestamp}")
        st.info("No attack data parsed (legacy format).")
    else:
        st.info("No red team reports found.")

with tab_opt:
    if latest_opt and latest_opt.recommendations:
        st.caption(f"Cycle: {latest_opt.timestamp}")
        for rec in latest_opt.recommendations:
            st.markdown(f"- {rec}")
    elif latest_opt:
        st.caption(f"Cycle: {latest_opt.timestamp}")
        st.info("No structured recommendations extracted.")
    else:
        st.info("No optimization reports found.")

with tab_hist:
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
    f"docs/run_history.json ({len(run_history)} runs) · "
    f"docs/analysis/ ({len(analyses)}) · "
    f"docs/redteam/ ({len(redteams)}) · "
    f"docs/optimization/ ({len(opts)}) · "
    f"Reload page to refresh"
)
