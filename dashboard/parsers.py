"""Parse PCDRED markdown reports into structured data."""

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class TaskScore:
    task_id: str
    prev: float
    curr: float
    delta: float
    status: str  # "—", "IMPROVED", "REGRESSED", etc.


@dataclass
class EvalReport:
    timestamp: str  # "2026-03-30-07"
    dt: datetime
    verdict: str  # IMPROVED | NEUTRAL | REGRESSED | IMPROVED_WITH_REGRESSION
    score_pct: float  # 68.0
    tasks_passed: int  # 17
    tasks_total: int  # 25, 32, ...
    delta_pct: float  # +8.0
    tasks: list
    model: str
    log_path: str
    fix_attribution: str  # full Fix Attribution section text
    consistently_failing: list  # [{"task": "t21", "cause": "PROTOCOL", "notes": "..."}]
    next_priorities: list  # ["t21 (PROTOCOL): ...", "t03 (SIDE_EFFECT): ..."]


@dataclass
class AnalysisReport:
    timestamp: str
    dt: datetime
    target_task: str
    category: str  # STAGNATION | PROTOCOL | SECURITY | etc.
    summary: str  # first line of Observation section


@dataclass
class AttackResult:
    number: int
    rating: str  # BLOCKED | PARTIAL | BYPASSES
    target: str


@dataclass
class RedTeamReport:
    timestamp: str
    dt: datetime
    attacks: list


@dataclass
class OptReport:
    timestamp: str
    dt: datetime
    recommendations: list


@dataclass
class RunRecord:
    timestamp: str  # ISO 8601: "2026-03-30T09:00:00+00:00"
    dt: datetime
    model: str
    backend: str  # "nebius", "api", or "cli" (legacy)
    score_pct: float
    tasks_passed: int
    tasks_total: int
    tasks: dict  # {task_id: {"score": float, "score_detail": list[str]}}
    cost_usd: float  # API cost in USD (0.0 for CLI runs)
    benchmark_task_count: int | None = None
    is_partial_run: bool = False


RUN_HISTORY_PATH = REPO_ROOT / "docs" / "run_history.json"


# ── Timestamp parsing ─────────────────────────────────────────────────────────


def _parse_ts(stem: str) -> tuple:
    """Extract YYYY-MM-DD-HH from filename stem."""
    m = re.search(r"(\d{4}-\d{2}-\d{2}-\d{2})", stem)
    if m:
        ts = m.group(1)
        y, mo, d, h = ts.split("-")
        return ts, datetime(int(y), int(mo), int(d), int(h))
    return stem, datetime(2026, 1, 1)  # fallback for legacy names


def _task_sort_key(task_id: str) -> tuple[int, str]:
    m = re.search(r"(\d+)$", task_id)
    return (int(m.group(1)), task_id) if m else (10**9, task_id)


def is_complete_run(record: RunRecord) -> bool:
    if record.benchmark_task_count:
        return not record.is_partial_run and record.tasks_total >= record.benchmark_task_count
    return record.tasks_total >= 25


def collect_task_ids(
    task_scores_all: dict,
    latest_eval,
    task_cache: dict,
    trace_map: dict,
    task_deltas: dict | None = None,
    targeted_task: str | None = None,
) -> list[str]:
    task_ids = set(task_scores_all)
    task_ids.update(task_cache)
    task_ids.update(trace_map)
    if latest_eval:
        task_ids.update(t.task_id for t in latest_eval.tasks)
        task_ids.update(item["task"] for item in latest_eval.consistently_failing)
    if task_deltas:
        task_ids.update(task_deltas)
    if targeted_task:
        task_ids.add(targeted_task)
    return sorted(task_ids, key=_task_sort_key)


# ── Eval report parser ────────────────────────────────────────────────────────


def parse_eval_report(path: Path) -> EvalReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)

    # Verdict — multiple formats: "## Verdict: X", "## Cycle Verdict: X", "**Verdict:** X"
    verdict = "UNKNOWN"
    for pat in [r"##\s*(?:Cycle\s+)?Verdict:\s*(\S+)", r"\*\*Verdict:\*\*\s*(\S+)"]:
        m = re.search(pat, text)
        if m:
            verdict = m.group(1)
            break
    # Infer verdict from content when not explicitly stated
    if verdict == "UNKNOWN":
        has_improve = bool(re.search(r"\*\*(t\d+)\*\*:\s*0→1", text))
        has_regress = bool(re.search(r"\*\*(t\d+)\*\*:\s*1→0", text))
        if has_improve and has_regress:
            verdict = "IMPROVED_WITH_REGRESSION"
        elif has_improve:
            verdict = "IMPROVED"
        elif has_regress:
            verdict = "REGRESSED"
        else:
            verdict = "NEUTRAL"

    # Score + tasks passed — "Current total: X% (N/M", "**Score:** N/M (X%)", "**Run N:** M/T (X%)"
    score_pct = 0.0
    tasks_passed = 0
    tasks_total = 0
    total_m = re.search(r"Current total:\s*([\d.]+)%\s*\((\d+)/(\d+)", text)
    if total_m:
        score_pct = float(total_m.group(1))
        tasks_passed = int(total_m.group(2))
        tasks_total = int(total_m.group(3))
    else:
        score_m = re.search(r"\*\*(?:Score|Run\s+\d+):\*\*\s*(\d+)/(\d+)\s*\(([\d.]+)%\)", text)
        if score_m:
            tasks_passed = int(score_m.group(1))
            tasks_total = int(score_m.group(2))
            score_pct = float(score_m.group(3))

    # Delta — "Delta: +8.00%", "**Delta:** +3.2pp", "**Delta:** -2 tasks (-6.45pp)"
    delta_pct = 0.0
    delta_m = re.search(r"Delta:\s*([+-]?[\d.]+)%", text)
    if delta_m:
        delta_pct = float(delta_m.group(1))
    else:
        # Try "(-6.45pp)" in parentheses first, then bare "+3.2pp"
        delta_m = re.search(r"\(([+-]?[\d.]+)pp\)", text) or re.search(
            r"\*\*Delta:\*\*\s*([+-]?[\d.]+)pp", text
        )
        if delta_m:
            delta_pct = float(delta_m.group(1))

    # Task rows — 5-col (prev|curr|delta|status) or 2-col (score|status) tables
    rows = re.findall(
        r"\|\s*(t\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([+-]?[\d.]+)\s*\|\s*([^|\n]+)",
        text,
    )
    tasks = [TaskScore(r[0], float(r[1]), float(r[2]), float(r[3]), r[4].strip()) for r in rows]
    if not tasks:
        # 2-col: "| t01 | 1.00 | PASS |" from auto-generated reports
        rows2 = re.findall(r"\|\s*(t\d+)\s*\|\s*([\d.]+)\s*\|\s*(\w+)\s*\|", text)
        tasks = [TaskScore(r[0], 0.0, float(r[1]), float(r[1]), r[2]) for r in rows2]
    if tasks_total == 0 and tasks:
        tasks_total = len(tasks)

    # Model — "Model: X" or "**Model:** `X`"
    model_m = re.search(r"\*\*Model:\*\*\s*`?([^`\n]+)`?", text) or re.search(
        r"Model:\s*(.+)", text
    )
    model = model_m.group(1).strip() if model_m else "unknown"

    log_m = re.search(r"Log:\s*(.+)", text)
    log_path = log_m.group(1).strip() if log_m else ""

    # Fix Attribution section
    fix_attr_m = re.search(r"## Fix Attribution\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    fix_attribution = fix_attr_m.group(1).strip() if fix_attr_m else ""

    # Consistently Failing table
    consistently_failing = []
    cf_start = text.find("Consistently")
    if cf_start != -1:
        cf_rows = re.findall(
            r"\|\s*(t\d+)\s*\|\s*[\d.]+\s*\|\s*([^|]+)\|\s*([^|\n]+)",
            text[cf_start:],
        )
        for r in cf_rows:
            consistently_failing.append(
                {
                    "task": r[0].strip(),
                    "cause": r[1].strip(),
                    "notes": r[2].strip(),
                }
            )

    # Next Cycle Priorities
    next_priorities = []
    prio_m = re.search(r"## Next Cycle Priorities\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if prio_m:
        for line in prio_m.group(1).strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                next_priorities.append(re.sub(r"^\d+\.\s*", "", line))

    return EvalReport(
        ts,
        dt,
        verdict,
        score_pct,
        tasks_passed,
        tasks_total,
        delta_pct,
        tasks,
        model,
        log_path,
        fix_attribution,
        consistently_failing,
        next_priorities,
    )


# ── Analysis report parser ────────────────────────────────────────────────────


def parse_analysis_report(path: Path) -> AnalysisReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)

    task_m = re.search(r"\*\*Task\*\*:\s*(\S+)", text)
    target_task = task_m.group(1) if task_m else "unknown"

    cat_m = re.search(r"\*\*Category\*\*:\s*(\S+)", text)
    category = cat_m.group(1) if cat_m else "UNKNOWN"

    obs_m = re.search(r"## Observation\s*\n+(.+?)(?:\n\n|\Z)", text, re.DOTALL)
    summary = obs_m.group(1).strip() if obs_m else ""

    return AnalysisReport(ts, dt, target_task, category, summary)


# ── Red team report parser ────────────────────────────────────────────────────


def parse_redteam_report(path: Path) -> RedTeamReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)

    attacks = []
    for i, block in enumerate(re.split(r"## Attack \d+", text)[1:], start=1):
        rating_m = re.search(r"\*\*Rating\*\*:\s*(\w+)", block)
        target_m = re.search(r"\*\*Target\*\*:\s*(.+)", block)
        attacks.append(
            AttackResult(
                number=i,
                rating=rating_m.group(1) if rating_m else "UNKNOWN",
                target=target_m.group(1).strip()[:80] if target_m else "",
            )
        )

    return RedTeamReport(ts, dt, attacks)


# ── Optimization report parser ────────────────────────────────────────────────


def parse_opt_report(path: Path) -> OptReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)

    recs = re.findall(r"\*\*Recommendation\*\*:\s*(.+)", text)
    short_recs = [r.strip() for r in recs[:6]]

    return OptReport(ts, dt, short_recs)


# ── Task cache ───────────────────────────────────────────────────────────────

TASK_CACHE_PATH = REPO_ROOT / "docs" / "task_cache.json"


def load_task_cache() -> dict:
    """Load task instructions and score details saved by main.py during runs.

    Returns dict keyed by task_id:
      {instruction, score, score_detail: list[str], model, timestamp}
    """
    if not TASK_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(TASK_CACHE_PATH.read_text())
    except Exception:
        return {}


def load_run_history() -> list:
    """Load docs/run_history.json — append-only list of complete run records.

    Returns list[RunRecord] sorted oldest-first.
    """
    if not RUN_HISTORY_PATH.exists():
        return []
    try:
        raw = json.loads(RUN_HISTORY_PATH.read_text())
    except Exception:
        return []
    if not isinstance(raw, list):
        return []

    records = []
    for entry in raw:
        try:
            ts = entry.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                dt = datetime(2026, 1, 1)
            api_usage = entry.get("api_usage", {})
            records.append(
                RunRecord(
                    timestamp=ts,
                    dt=dt,
                    benchmark_task_count=entry.get("benchmark_task_count"),
                    is_partial_run=bool(entry.get("is_partial_run", False)),
                    model=entry.get("model", "unknown"),
                    backend=entry.get("backend", "cli"),
                    score_pct=float(entry.get("score_pct", 0.0)),
                    tasks_passed=int(entry.get("tasks_passed", 0)),
                    tasks_total=int(entry.get("tasks_total", len(entry.get("tasks", {})))),
                    tasks=entry.get("tasks", {}),
                    cost_usd=float(api_usage.get("cost_usd", 0.0)),
                )
            )
        except Exception:
            continue
    return sorted(records, key=lambda r: r.dt)


# ── Git log ───────────────────────────────────────────────────────────────────


@dataclass
class GitCommit:
    hash: str
    message: str
    commit_type: str  # "feat", "fix", "perf", "docs", etc.


def load_git_log(limit: int = 30) -> list:
    """Load recent git commits. Returns list[GitCommit] newest-first."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{limit}"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=5,
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        hash_str = parts[0]
        msg = parts[1]
        type_m = re.match(r"(feat|fix|perf|docs|chore|refactor|test|ci):", msg)
        commit_type = type_m.group(1) if type_m else "other"
        commits.append(GitCommit(hash=hash_str, message=msg, commit_type=commit_type))
    return commits


# ── Aggregators ──────────────────────────────────────────────────────────────


def build_task_lifecycle(
    task_id: str,
    evals: list,
    analyses: list,
    redteams: list,
    task_cache: dict,
    latest_trace,
) -> "TaskLifecycle":
    """Join all data sources into a single TaskLifecycle for one task."""
    from narratives import TaskLifecycle, generate_task_narrative

    # Score history from eval reports (primary multi-run source)
    score_history = []
    for e in evals:
        for t in e.tasks:
            if t.task_id == task_id:
                score_history.append((e.timestamp, t.curr))
                break

    passes = sum(1 for _, s in score_history if s >= 1.0)
    total = len(score_history)
    pass_rate = passes / total if total > 0 else 0.0
    stability = f"{passes}/{total}" if total > 0 else "—"
    current_score = score_history[-1][1] if score_history else 0.0

    # Task cache data
    cached = task_cache.get(task_id, {})
    instruction = cached.get("instruction", "")
    score_detail = cached.get("score_detail", [])

    # Classification from latest trace
    category = latest_trace.task_type if latest_trace else "unknown"
    threat = latest_trace.threat if latest_trace else "none"

    # Agent answer from latest trace
    answer_message = latest_trace.answer_message if latest_trace else ""
    answer_outcome = latest_trace.answer_outcome if latest_trace else ""
    answer_steps = latest_trace.answer_steps if latest_trace else []

    # Cycles that targeted this task
    cycles_targeting = [
        {
            "timestamp": a.timestamp,
            "category": a.category,
            "observation": a.summary,
        }
        for a in analyses
        if a.target_task == task_id
    ]

    # Fix attribution from evals mentioning this task
    fixes_applied = []
    for e in evals:
        if e.fix_attribution and task_id in e.fix_attribution:
            fixes_applied.append(f"{e.timestamp}: {e.fix_attribution[:100]}")

    # Red team mentions
    redteam_mentions = []
    for rt in redteams:
        for a in rt.attacks:
            if task_id in (a.target or ""):
                redteam_mentions.append(f"{rt.timestamp}: {a.rating} — {a.target[:60]}")

    lifecycle = TaskLifecycle(
        task_id=task_id,
        instruction=instruction,
        current_score=current_score,
        stability=stability,
        pass_rate=pass_rate,
        category=category,
        threat=threat,
        answer_message=answer_message,
        answer_outcome=answer_outcome,
        answer_steps=answer_steps,
        score_detail=score_detail,
        score_history=score_history,
        cycles_targeting=cycles_targeting,
        fixes_applied=fixes_applied,
        redteam_mentions=redteam_mentions,
        narrative="",
    )
    lifecycle.narrative = generate_task_narrative(lifecycle)
    return lifecycle


def build_run_digests(
    evals: list,
    analyses: list,
    git_commits: list,
) -> list:
    """Build RunDigest for each eval report."""
    from narratives import generate_run_narrative

    digests = []
    for i, e in enumerate(evals):
        prev = evals[i - 1] if i > 0 else None
        digests.append(generate_run_narrative(e, prev, analyses, git_commits))
    return digests


def build_task_table_df(
    task_scores_all: dict,
    latest_eval,
    task_cache: dict,
    trace_map: dict,
    targeted_task: str | None,
    task_deltas: dict | None = None,
) -> pd.DataFrame:
    """Build a sorted DataFrame for the task table view.

    Columns: Задача, ✓/✗, Δ, Задание, Стаб., Причина.
    Sorted: failing first, then by task number.
    """
    task_deltas = task_deltas or {}
    cf_map: dict = {}
    if latest_eval:
        for item in latest_eval.consistently_failing:
            cf_map[item["task"]] = f"{item['cause']}: {item['notes'][:40]}"

    rows = []
    task_ids = collect_task_ids(
        task_scores_all,
        latest_eval,
        task_cache,
        trace_map,
        task_deltas,
        targeted_task,
    )
    for tid in task_ids:
        scores = task_scores_all.get(tid, [])
        latest_score = scores[-1] if scores else -1
        passes = sum(1 for s in scores if s >= 1.0)
        total = len(scores)

        if tid == targeted_task:
            status = "🎯"
        elif latest_score >= 1.0:
            status = "✓"
        elif latest_score >= 0:
            status = "✗"
        else:
            status = "?"

        stability = f"{passes}/{total}" if total > 0 else "—"

        cached = task_cache.get(tid, {})
        instruction = cached.get("instruction", "")
        instr_short = instruction[:50] + "…" if len(instruction) > 50 else instruction

        issue = cf_map.get(tid, "")
        if not issue:
            details = cached.get("score_detail", [])
            issue = details[0][:50] if details else "—"

        delta_val = task_deltas.get(tid, 0.0)
        if delta_val > 0:
            delta_mark = "▲"
        elif delta_val < 0:
            delta_mark = "▼"
        else:
            delta_mark = "—"

        rows.append(
            {
                "Задача": tid,
                "Статус": status,
                "Δ": delta_mark,
                "Задание": instr_short,
                "Стаб.": stability,
                "Причина": issue,
            }
        )

    df = pd.DataFrame(rows)
    sort_order = {"✗": 0, "🎯": 1, "?": 2, "✓": 3}
    df["_sort"] = df["Статус"].map(sort_order)
    df["_task_num"] = df["Задача"].map(lambda tid: _task_sort_key(tid)[0])
    df = df.sort_values(["_sort", "_task_num", "Задача"]).drop(columns=["_sort", "_task_num"])
    return df


# ── Dashboard Summary ────────────────────────────────────────────────────────


@dataclass
class DashboardSummary:
    best_score_pct: float
    best_score_timestamp: str
    is_current_best: bool
    delta_from_best: float
    regressions: list
    improvements: list
    improvement_count: int
    failure_clusters: dict  # cause -> [task_ids]
    bottleneck_desc: str
    bottleneck_tasks: list
    bottleneck_points: int
    projected_score_pct: float
    task_deltas: dict  # task_id -> delta float


def extract_task_metrics_df(record: RunRecord) -> pd.DataFrame:
    """Build per-task metrics DataFrame from a RunRecord. Includes TOTAL row."""
    rows = []
    tot_time = 0.0
    tot_steps = tot_tools = tot_prompt = tot_compl = 0
    for tid in sorted(record.tasks.keys(), key=_task_sort_key):
        td = record.tasks[tid]
        score = td.get("score", 0.0)
        m = td.get("metrics", {})
        time_s = m.get("total_time_ms", 0) / 1000.0
        steps = m.get("step_count", 0)
        tools = m.get("tool_call_count", 0)
        prompt = m.get("prompt_tokens", 0)
        compl = m.get("completion_tokens", 0)
        rows.append(
            {
                "Task": tid,
                "Score": "PASS" if score >= 1.0 else "FAIL",
                "Time": f"{time_s:.1f}s" if time_s > 0 else "—",
                "Steps": steps or "—",
                "Tool Calls": tools or "—",
                "Prompt Tok": f"{prompt:,}" if prompt else "—",
                "Compl Tok": f"{compl:,}" if compl else "—",
            }
        )
        tot_time += time_s
        tot_steps += steps
        tot_tools += tools
        tot_prompt += prompt
        tot_compl += compl
    passed = sum(1 for r in rows if r["Score"] == "PASS")
    rows.append(
        {
            "Task": "TOTAL",
            "Score": f"{passed}/{len(rows)} ({record.score_pct:.1f}%)",
            "Time": f"{tot_time:.0f}s ({tot_time / 60:.0f}m)",
            "Steps": tot_steps,
            "Tool Calls": tot_tools,
            "Prompt Tok": f"{tot_prompt:,}",
            "Compl Tok": f"{tot_compl:,}",
        }
    )
    return pd.DataFrame(rows)


def compute_dashboard_summary(evals: list, task_scores_all: dict) -> DashboardSummary:  # noqa: ARG001
    """Pre-compute derived insights for the dashboard hero section."""
    latest = evals[-1] if evals else None

    # Best-ever from eval reports (not run_history which has spot runs)
    all_scores = [(e.score_pct, e.timestamp) for e in evals if e.tasks]
    best_score, best_ts = max(all_scores, key=lambda x: x[0]) if all_scores else (0.0, "")
    current = latest.score_pct if latest else 0.0
    is_best = abs(current - best_score) < 0.01 and latest is not None

    # Regressions / improvements from latest eval task deltas
    regressions = [t.task_id for t in (latest.tasks if latest else []) if t.delta < 0]
    improvements = [t.task_id for t in (latest.tasks if latest else []) if t.delta > 0]
    improvement_count = sum(int(t.delta) for t in (latest.tasks if latest else []) if t.delta > 0)

    # Failure clusters from consistently_failing
    clusters: dict = {}
    if latest:
        for item in latest.consistently_failing:
            clusters.setdefault(item["cause"], []).append(item["task"])

    # Bottleneck from next_priorities[0]
    bottleneck_desc = ""
    bottleneck_tasks: list = []
    bottleneck_points = 0
    projected = current
    total_tasks = latest.tasks_total if latest and latest.tasks_total > 0 else max(len(task_scores_all), 1)
    if latest and latest.next_priorities:
        prio = latest.next_priorities[0]
        m = re.match(r"(t\d+(?:\+t\d+)*)\s*\((\w+),\s*(\d+)\s*pts?\):\s*(.+)", prio)
        if m:
            bottleneck_tasks = m.group(1).split("+")
            bottleneck_points = int(m.group(3))
            bottleneck_desc = m.group(4).strip()[:80]
            projected = current + (bottleneck_points / total_tasks * 100)
        else:
            bottleneck_desc = prio[:80]

    # Task deltas
    task_deltas: dict = {}
    if latest:
        for t in latest.tasks:
            task_deltas[t.task_id] = t.delta

    return DashboardSummary(
        best_score_pct=best_score,
        best_score_timestamp=best_ts,
        is_current_best=is_best,
        delta_from_best=current - best_score,
        regressions=regressions,
        improvements=improvements,
        improvement_count=improvement_count,
        failure_clusters=clusters,
        bottleneck_desc=bottleneck_desc,
        bottleneck_tasks=bottleneck_tasks,
        bottleneck_points=bottleneck_points,
        projected_score_pct=projected,
        task_deltas=task_deltas,
    )


# ── Narrative reports ─────────────────────────────────────────────────────────


@dataclass
class NarrativeReport:
    timestamp: str
    dt: datetime
    title: str  # first heading
    content: str  # full markdown


def parse_narrative_report(path: Path) -> NarrativeReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)
    title_m = re.search(r"^#\s+(.+)", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else path.stem
    return NarrativeReport(ts, dt, title, text)


# ── Loaders ───────────────────────────────────────────────────────────────────


def load_narrative_reports() -> list:
    narr_dir = DOCS / "narratives"
    if not narr_dir.exists():
        return []
    reports = []
    for p in sorted(narr_dir.glob("run-*.md")):
        try:
            reports.append(parse_narrative_report(p))
        except Exception:
            pass
    return sorted(reports, key=lambda r: r.dt)


def load_eval_reports() -> list:
    reports = []
    for p in sorted((DOCS / "eval").glob("run-*.md")):
        try:
            reports.append(parse_eval_report(p))
        except Exception:
            pass
    return sorted(reports, key=lambda r: r.dt)


def load_analysis_reports() -> list:
    reports = []
    for p in sorted((DOCS / "analysis").glob("cycle-*.md")):
        try:
            reports.append(parse_analysis_report(p))
        except Exception:
            pass
    return sorted(reports, key=lambda r: r.dt)


def load_redteam_reports() -> list:
    reports = []
    for p in sorted((DOCS / "redteam").glob("cycle-*.md")):
        try:
            reports.append(parse_redteam_report(p))
        except Exception:
            pass
    return sorted(reports, key=lambda r: r.dt)


def load_opt_reports() -> list:
    reports = []
    for p in sorted((DOCS / "optimization").glob("cycle-*.md")):
        try:
            reports.append(parse_opt_report(p))
        except Exception:
            pass
    return sorted(reports, key=lambda r: r.dt)
