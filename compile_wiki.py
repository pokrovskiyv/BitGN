"""Compile the BitGN Knowledge Wiki from raw data sources.

Reads run_history.json, task_cache.json, and PCDRED reports from docs/,
then writes synthesized wiki pages to docs/wiki/.

Usage:
    python3 compile_wiki.py              # Full rebuild
    python3 compile_wiki.py --check      # Lint only, no writes
    python3 compile_wiki.py --tasks t01 t05  # Specific task cards
"""

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent
DOCS = REPO_ROOT / "docs"
WIKI_DIR = DOCS / "wiki"
TASKS_DIR = WIKI_DIR / "tasks"

RUN_HISTORY_PATH = DOCS / "run_history.json"
TASK_CACHE_PATH = DOCS / "task_cache.json"
SOTA_PATH = DOCS / "sota-analysis.md"

MIN_COMPLETE_RUN_TASKS = 25


# ── Data Models ────────────────────────────────────────────────────────────


@dataclass
class RunRecord:
    timestamp: str
    dt: datetime
    model: str
    backend: str
    score_pct: float
    tasks_passed: int
    tasks_total: int
    tasks: dict
    cost_usd: float


@dataclass
class CycleReport:
    timestamp: str
    dt: datetime
    target: str
    classification: str
    zone: str
    file_changed: str
    do_not_repeat: list  # [(cycle_ts, description, verdict)]


@dataclass
class EvalReportW:
    timestamp: str
    dt: datetime
    model: str
    backend: str
    score: int
    total: int
    score_pct: float
    delta: str
    improvements: list
    regressions: list
    still_failing: list
    per_task: dict


@dataclass
class AttackEntry:
    number: int
    title: str
    rating: str


@dataclass
class RedTeamReportW:
    timestamp: str
    dt: datetime
    change: str
    attacks: list


@dataclass
class OptReportW:
    timestamp: str
    dt: datetime
    change: str
    recommendations: list
    pending: list


@dataclass
class FixEntry:
    cycle_ts: str
    description: str
    verdict: str


@dataclass
class TaskCard:
    task_id: str
    instruction: str
    task_type: str
    win_rate: float
    wins: int
    total_runs: int
    stability: str
    last_5: list
    failure_modes: list
    per_backend: dict
    fix_history: list
    do_not_repeat: list
    redteam_notes: list
    opt_notes: list


@dataclass
class VulnEntry:
    title: str
    rating: str
    cycle_ts: str
    change_tested: str


@dataclass
class ScoreboardData:
    complete_runs: list
    per_model: dict
    best_ever: tuple
    current: tuple
    rolling_5: list


@dataclass
class HealthAlert:
    level: str
    message: str


# ── Timestamp Parsing ──────────────────────────────────────────────────────


def _parse_ts(stem: str) -> tuple[str, datetime]:
    """Extract YYYY-MM-DD-HH from filename stem."""
    m = re.search(r"(\d{4}-\d{2}-\d{2}-\d{2})", stem)
    if m:
        ts = m.group(1)
        y, mo, d, h = ts.split("-")
        return ts, datetime(int(y), int(mo), int(d), int(h))
    return stem, datetime(2026, 1, 1)


# ── Parsers ────────────────────────────────────────────────────────────────


def load_run_history() -> list[RunRecord]:
    """Load docs/run_history.json → list[RunRecord] sorted oldest-first."""
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
            api = entry.get("api_usage", {})
            records.append(
                RunRecord(
                    timestamp=ts,
                    dt=dt,
                    model=entry.get("model", "unknown"),
                    backend=entry.get("backend", "cli"),
                    score_pct=float(entry.get("score_pct", 0.0)),
                    tasks_passed=int(entry.get("tasks_passed", 0)),
                    tasks_total=int(entry.get("tasks_total", 25)),
                    tasks=entry.get("tasks", {}),
                    cost_usd=float(api.get("cost_usd", 0.0)),
                )
            )
        except Exception:
            continue
    return sorted(records, key=lambda r: r.dt)


def load_task_cache() -> dict:
    """Load docs/task_cache.json → {task_id: {instruction, score, ...}}."""
    if not TASK_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(TASK_CACHE_PATH.read_text())
    except Exception:
        return {}


def parse_cycle_report(path: Path) -> CycleReport | None:
    """Parse docs/analysis/cycle-*.md into CycleReport."""
    try:
        text = path.read_text()
    except Exception:
        return None
    ts, dt = _parse_ts(path.stem)

    # Target: handles both "## Target:" and "## Target Failure"
    target_m = re.search(r"## Target[:\s]+(.+)", text)
    if not target_m:
        target_m = re.search(r"## Target Failure\s*\n+\*\*Tasks?\*\*:\s*(.+)", text)
    target = target_m.group(1).strip() if target_m else ""

    class_m = re.search(r"\*\*Classification\*\*:\s*(\w+)", text)
    classification = class_m.group(1) if class_m else "UNKNOWN"

    zone_m = re.search(r"## Zone:\s*(\w+)", text)
    zone = zone_m.group(1) if zone_m else "UNKNOWN"

    file_m = re.search(r"\*\*File\*\*:\s*`?([^`\n]+)`?", text)
    file_changed = file_m.group(1).strip() if file_m else ""

    # DO_NOT_REPEAT — look for the section with either header variant
    do_not_repeat = []
    dnr_section = re.search(
        r"(?:DO_NOT_REPEAT|Previous Cycles)\)?\s*\n(.*?)(?=\n## |\Z)",
        text,
        re.DOTALL,
    )
    if dnr_section:
        for line in dnr_section.group(1).strip().split("\n"):
            # Match: - Cycle 2026-04-02-20: desc → VERDICT
            m = re.match(
                r"-\s*Cycle\s+([\d-]+):\s*(.+?)\s*(?:→|->)\s*(\S+.*)",
                line.strip(),
            )
            if m:
                do_not_repeat.append(
                    (
                        m.group(1).strip(),
                        m.group(2).strip(),
                        m.group(3).strip(),
                    )
                )

    return CycleReport(ts, dt, target, classification, zone, file_changed, do_not_repeat)


def parse_eval_report_w(path: Path) -> EvalReportW | None:
    """Parse docs/eval/run-*.md into EvalReportW."""
    try:
        text = path.read_text()
    except Exception:
        return None
    ts, dt = _parse_ts(path.stem)

    model_m = re.search(r"\*\*Model:\*\*\s*`?([^`\n]+)`?", text)
    model = model_m.group(1).strip() if model_m else "unknown"

    backend_m = re.search(r"\*\*Backend:\*\*\s*`?([^`\n]+)`?", text)
    backend = backend_m.group(1).strip() if backend_m else "unknown"

    score_m = re.search(r"\*\*Score:\*\*\s*(\d+)/(\d+)\s*\(([\d.]+)%\)", text)
    if score_m:
        score, total = int(score_m.group(1)), int(score_m.group(2))
        score_pct = float(score_m.group(3))
    else:
        score, total, score_pct = 0, 31, 0.0

    delta_m = re.search(r"\*\*Delta:\*\*\s*([^\n]+)", text)
    delta = delta_m.group(1).strip() if delta_m else "N/A"

    def _parse_task_list(header: str) -> list[tuple[str, str]]:
        sec = re.search(rf"## {header}\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
        if not sec:
            return []
        items = []
        for line in sec.group(1).strip().split("\n"):
            m = re.match(r"-\s*\*?\*?(t\d+)\*?\*?:\s*(.*)", line.strip())
            if m:
                items.append((m.group(1), m.group(2).strip()))
        return items

    improvements = _parse_task_list("Improvements")
    regressions = _parse_task_list("Regressions")
    still_failing = _parse_task_list("Still Failing")

    per_task = {}
    for m in re.finditer(r"\|\s*(t\d+)\s*\|\s*([\d.]+)\s*\|\s*(\w+)\s*\|", text):
        per_task[m.group(1)] = (float(m.group(2)), m.group(3))

    return EvalReportW(
        ts,
        dt,
        model,
        backend,
        score,
        total,
        score_pct,
        delta,
        improvements,
        regressions,
        still_failing,
        per_task,
    )


def parse_redteam_report_w(path: Path) -> RedTeamReportW | None:
    """Parse docs/redteam/cycle-*.md into RedTeamReportW."""
    try:
        text = path.read_text()
    except Exception:
        return None
    ts, dt = _parse_ts(path.stem)

    change_m = re.search(r"\*\*(?:Change|Fix analyzed)\*\*:\s*(.+)", text)
    change = change_m.group(1).strip()[:120] if change_m else ""

    attacks = []

    # Format A: ### Attack N: Title (RATING)
    for m in re.finditer(r"###?\s*Attack\s+(\d+)[:\s]+(.+?)\s*\((\w+)\)", text):
        attacks.append(AttackEntry(int(m.group(1)), m.group(2).strip(), m.group(3)))

    # Format B: ## Attack N — Title ... **Rating**: WORD  (or summary table)
    if not attacks:
        for m in re.finditer(r"##\s*Attack\s+(\d+)\s*[—–-]\s*(.+?)(?:\n|$)", text):
            num = int(m.group(1))
            title = m.group(2).strip()
            # Find rating in the block after this header
            rest = text[m.end() :]
            next_header = re.search(r"\n## ", rest)
            block = rest[: next_header.start()] if next_header else rest
            rating_m = re.search(r"\*\*Rating\*\*:\s*\*?\*?(\w+)", block)
            rating = rating_m.group(1) if rating_m else "UNKNOWN"
            attacks.append(AttackEntry(num, title, rating))

    # Format C: summary table | N | Name | Rating | ...
    if not attacks:
        for m in re.finditer(r"\|\s*(\d+)\s*\|([^|]+)\|[^|]*\|\s*(\w+)\s*\|", text):
            attacks.append(
                AttackEntry(
                    int(m.group(1)),
                    m.group(2).strip(),
                    m.group(3).strip(),
                )
            )

    return RedTeamReportW(ts, dt, change, attacks)


def parse_opt_report_w(path: Path) -> OptReportW | None:
    """Parse docs/optimization/cycle-*.md into OptReportW."""
    try:
        text = path.read_text()
    except Exception:
        return None
    ts, dt = _parse_ts(path.stem)

    change_m = re.search(r"\*\*Change\*\*:\s*(.+)", text)
    change = change_m.group(1).strip() if change_m else ""

    recommendations = []
    rec_m = re.search(r"## Recommendation\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if rec_m:
        recommendations = [
            ln.strip()
            for ln in rec_m.group(1).strip().split("\n")
            if ln.strip() and not ln.strip().startswith("#")
        ]

    pending = []
    pend_m = re.search(r"## Pending.*?\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if pend_m:
        pending = [
            ln.strip().lstrip("- ")
            for ln in pend_m.group(1).strip().split("\n")
            if ln.strip().startswith("-")
        ]

    return OptReportW(ts, dt, change, recommendations, pending)


# ── Loader Helpers ─────────────────────────────────────────────────────────


def _load_reports(subdir: str, pattern: str, parser):
    """Generic loader: glob → parse → sort by dt."""
    d = DOCS / subdir
    if not d.exists():
        return []
    reports = []
    for p in sorted(d.glob(pattern)):
        r = parser(p)
        if r:
            reports.append(r)
    return sorted(reports, key=lambda r: r.dt)


def load_all_data():
    """Load every data source. Returns a dict of all loaded data."""
    return {
        "runs": load_run_history(),
        "cache": load_task_cache(),
        "cycles": _load_reports("analysis", "cycle-*.md", parse_cycle_report),
        "evals": _load_reports("eval", "run-*.md", parse_eval_report_w),
        "redteams": _load_reports("redteam", "cycle-*.md", parse_redteam_report_w),
        "opts": _load_reports("optimization", "cycle-*.md", parse_opt_report_w),
    }


# ── Synthesis ──────────────────────────────────────────────────────────────


def _classify_task_type(instruction: str) -> str:
    """Regex classification matching pac1-py/classify.py categories."""
    lo = instruction.lower()
    if any(w in lo for w in ("security", "suspicious", "phishing", "malicious")):
        return "security_test"
    if any(w in lo for w in ("draft", "send", "reply", "forward", "compose")):
        return "communication"
    if any(w in lo for w in ("inbox", "unread", "new messages", "capture", "distill")):
        return "inbox_processing"
    if any(w in lo for w in ("search", "find", "look for", "locate")):
        return "search"
    if any(w in lo for w in ("analyze", "compare", "summarize", "report")):
        return "analysis"
    if any(
        w in lo
        for w in ("create", "add", "write", "update", "delete", "rename", "move", "discard")
    ):
        return "crud"
    return "multi_step"


def build_task_card(task_id, runs, cache, cycles, redteams, opts) -> TaskCard:
    """Synthesize all data sources into a single TaskCard."""
    cached = cache.get(task_id, {})
    instruction = cached.get("instruction", "")
    task_type = _classify_task_type(instruction)

    complete_runs = [r for r in runs if r.tasks_total >= MIN_COMPLETE_RUN_TASKS]
    scores = []
    per_backend: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    failure_counter: Counter = Counter()

    for r in complete_runs:
        td = r.tasks.get(task_id)
        if td is None:
            continue
        s = td.get("score", 0.0)
        win = s >= 1.0
        scores.append(("W" if win else "L", r.backend))

        be = r.backend or "unknown"
        per_backend[be][1] += 1
        if win:
            per_backend[be][0] += 1
        else:
            for d in td.get("score_detail", []):
                failure_counter[d] += 1

    wins = sum(1 for s, _ in scores if s == "W")
    total = len(scores)
    win_rate = (wins / total * 100) if total > 0 else 0.0

    if total == 0:
        stability = "NO_DATA"
    elif win_rate == 100.0:
        stability = "STABLE"
    elif win_rate == 0.0:
        stability = "DEAD"
    else:
        stability = "FLAKY"

    last_5 = [s for s, _ in scores[-5:]]

    total_fails = sum(failure_counter.values())
    failure_modes = [
        (err, cnt, round(cnt / total_fails * 100) if total_fails > 0 else 0)
        for err, cnt in failure_counter.most_common(5)
    ]

    per_backend_dict = {be: (vals[0], vals[1]) for be, vals in sorted(per_backend.items())}

    # Collect all DO_NOT_REPEAT entries across cycles (global registry)
    all_fixes = []
    seen_fixes = set()
    for c in cycles:
        for c_ts, desc, verdict in c.do_not_repeat:
            key = (c_ts, desc)
            if key not in seen_fixes:
                seen_fixes.add(key)
                all_fixes.append(FixEntry(c_ts, desc, verdict))

    # Filter to task-relevant entries
    tid_lo = task_id.lower()
    dnr_for_task = [
        f"{fe.description} (cycle {fe.cycle_ts}, {fe.verdict})"
        for fe in all_fixes
        if tid_lo in fe.description.lower()
    ]

    # Redteam notes mentioning this task
    redteam_notes = [
        f"Cycle {rt.timestamp}: {a.title} ({a.rating})"
        for rt in redteams
        for a in rt.attacks
        if tid_lo in a.title.lower()
    ]

    # Optimization pending items mentioning this task
    opt_notes = [
        f"Cycle {o.timestamp}: {p}" for o in opts for p in o.pending if tid_lo in p.lower()
    ]

    return TaskCard(
        task_id=task_id,
        instruction=instruction,
        task_type=task_type,
        win_rate=win_rate,
        wins=wins,
        total_runs=total,
        stability=stability,
        last_5=last_5,
        failure_modes=failure_modes,
        per_backend=per_backend_dict,
        fix_history=all_fixes,
        do_not_repeat=dnr_for_task,
        redteam_notes=redteam_notes,
        opt_notes=opt_notes,
    )


def build_fix_registry(cycles: list[CycleReport]) -> list[FixEntry]:
    """Consolidate all DO_NOT_REPEAT entries across all cycle reports."""
    seen = set()
    registry = []
    for c in cycles:
        for c_ts, desc, verdict in c.do_not_repeat:
            key = (c_ts, desc)
            if key not in seen:
                seen.add(key)
                registry.append(FixEntry(c_ts, desc, verdict))
    return sorted(registry, key=lambda f: f.cycle_ts)


def build_vuln_catalog(redteams: list[RedTeamReportW]) -> list[VulnEntry]:
    """Collect all attack entries across all redteam reports."""
    return [
        VulnEntry(a.title, a.rating, rt.timestamp, rt.change)
        for rt in redteams
        for a in rt.attacks
    ]


def build_scoreboard(runs: list[RunRecord]) -> ScoreboardData:
    """Build score progression from complete runs."""
    complete = [r for r in runs if r.tasks_total >= MIN_COMPLETE_RUN_TASKS]

    run_tuples = [
        (r.timestamp[:19], r.model, r.backend, r.score_pct, r.tasks_passed, r.tasks_total)
        for r in complete
    ]

    model_scores: dict[str, list[float]] = defaultdict(list)
    for r in complete:
        short = r.model.split("/")[-1] if "/" in r.model else r.model
        model_scores[short].append(r.score_pct)

    per_model = {
        m: (round(sum(s) / len(s), 1), round(min(s), 1), round(max(s), 1), len(s))
        for m, s in model_scores.items()
    }

    if complete:
        best_r = max(complete, key=lambda r: r.score_pct)
        best_ever = (best_r.score_pct, best_r.timestamp[:19], best_r.model)
        cur = complete[-1]
        current = (cur.score_pct, cur.timestamp[:19], cur.model)
    else:
        best_ever = (0.0, "", "")
        current = (0.0, "", "")

    rolling_5 = [r.score_pct for r in complete[-5:]]

    return ScoreboardData(run_tuples, per_model, best_ever, current, rolling_5)


def compute_health_checks(runs, cycles, evals, redteams, task_cards):
    """Run data quality and consistency checks."""
    alerts = []

    # 1. Data volume
    if runs:
        alerts.append(
            HealthAlert("PASS", f"run_history: {len(runs)} runs, latest {runs[-1].timestamp[:10]}")
        )
    else:
        alerts.append(HealthAlert("FAIL", "run_history.json empty or missing"))

    # 2. Dead tasks with no recent cycle
    recent_targets = " ".join(c.target.lower() for c in cycles[-5:])
    for tid, card in sorted(task_cards.items()):
        if card.stability == "DEAD" and card.total_runs >= 3:
            if tid not in recent_targets:
                alerts.append(HealthAlert("WARN", f"{tid} (0% win rate) — no recent cycle"))

    # 3. Unresolved BYPASSES
    bypasses = sum(1 for rt in redteams for a in rt.attacks if a.rating == "BYPASSES")
    if bypasses > 0:
        alerts.append(HealthAlert("INFO", f"{bypasses} BYPASSES findings across redteam reports"))
    else:
        alerts.append(HealthAlert("PASS", "No BYPASSES in redteam reports"))

    # 4. SoTA analysis freshness
    if SOTA_PATH.exists():
        days_old = (datetime.now() - datetime.fromtimestamp(SOTA_PATH.stat().st_mtime)).days
        if days_old > 3:
            alerts.append(HealthAlert("WARN", f"sota-analysis.md not updated in {days_old} days"))

    # 5. Task stability summary
    stable = [t for t, c in task_cards.items() if c.stability == "STABLE"]
    flaky = [t for t, c in task_cards.items() if c.stability == "FLAKY"]
    dead = [t for t, c in task_cards.items() if c.stability == "DEAD"]
    alerts.append(
        HealthAlert("PASS", f"Tasks: {len(stable)} STABLE, {len(flaky)} FLAKY, {len(dead)} DEAD")
    )
    if flaky:
        alerts.append(HealthAlert("INFO", f"FLAKY: {', '.join(sorted(flaky))}"))
    if dead:
        alerts.append(HealthAlert("WARN", f"DEAD: {', '.join(sorted(dead))}"))

    # 6. Report coverage
    alerts.append(
        HealthAlert(
            "PASS", f"Reports: {len(evals)} eval, {len(cycles)} cycle, {len(redteams)} redteam"
        )
    )

    return alerts


# ── Rendering ──────────────────────────────────────────────────────────────


def render_index(scoreboard, task_cards, alerts, fix_registry) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    stable = sum(1 for c in task_cards.values() if c.stability == "STABLE")
    flaky = sum(1 for c in task_cards.values() if c.stability == "FLAKY")
    dead = sum(1 for c in task_cards.values() if c.stability == "DEAD")

    if len(scoreboard.rolling_5) >= 2:
        diff = scoreboard.rolling_5[-1] - scoreboard.rolling_5[-2]
        arrow = "+" if diff > 0 else "" if diff < 0 else "="
        trend = f"{arrow}{diff:.0f}pp"
    else:
        trend = "—"

    lines = [
        "# BitGN Knowledge Wiki",
        "",
        f"*Compiled: {now}*",
        "",
        "## Current State",
        "",
        f"- **Score**: {scoreboard.current[0]:.1f}% ({scoreboard.current[2].split('/')[-1]})",
        f"- **Best Ever**: {scoreboard.best_ever[0]:.1f}%",
        f"- **Trend**: {trend} ({' > '.join(f'{s:.0f}' for s in scoreboard.rolling_5)})",
        f"- **Tasks**: {stable} STABLE / {flaky} FLAKY / {dead} DEAD",
        f"- **Fixes Attempted**: {len(fix_registry)}",
        "",
        "## Health",
        "",
    ]
    for a in alerts:
        lines.append(f"- [{a.level}] {a.message}")

    lines += [
        "",
        "## Task Summary",
        "",
        "| Task | Win% | Stability | Last 5 |",
        "|------|------|-----------|--------|",
    ]
    for tid in sorted(task_cards):
        c = task_cards[tid]
        l5 = " ".join(c.last_5) if c.last_5 else "—"
        lines.append(
            f"| [{tid}](tasks/{tid}.md) "
            f"| {c.win_rate:.0f}% ({c.wins}/{c.total_runs}) "
            f"| {c.stability} | {l5} |"
        )

    lines += [
        "",
        "## Pages",
        "",
        "- [Scoreboard](scoreboard.md)",
        "- [Fix Registry](fix-registry.md)",
        "- [Vulnerability Catalog](vulnerability-catalog.md)",
        "- [Health Report](health.md)",
    ]
    return "\n".join(lines) + "\n"


def render_scoreboard(sb: ScoreboardData) -> str:
    lines = [
        "# Scoreboard",
        "",
        f"**Best Ever**: {sb.best_ever[0]:.1f}% ({sb.best_ever[2]}, {sb.best_ever[1]})",
        f"**Current**: {sb.current[0]:.1f}% ({sb.current[2]}, {sb.current[1]})",
        "",
        "## Complete Runs",
        "",
        "| # | Timestamp | Model | Backend | Score |",
        "|---|-----------|-------|---------|-------|",
    ]
    for i, (ts, model, be, pct, passed, total) in enumerate(sb.complete_runs, 1):
        short = model.split("/")[-1][:30] if "/" in model else model[:30]
        lines.append(f"| R{i} | {ts[:16]} | {short} | {be} | {pct:.1f}% ({passed}/{total}) |")

    lines += [
        "",
        "## Per-Model",
        "",
        "| Model | Mean | Min | Max | Runs |",
        "|-------|------|-----|-----|------|",
    ]
    for model, (mean, mn, mx, cnt) in sorted(sb.per_model.items()):
        lines.append(f"| {model[:35]} | {mean:.1f}% | {mn:.1f}% | {mx:.1f}% | {cnt} |")
    return "\n".join(lines) + "\n"


def render_task_card(card: TaskCard) -> str:
    lines = [f"# {card.task_id} — {card.task_type}", ""]
    if card.instruction:
        lines += [f"> {card.instruction}", ""]

    l5 = " ".join(card.last_5) if card.last_5 else "—"
    lines += [
        "## Status",
        f"- **Win Rate**: {card.win_rate:.0f}% ({card.wins}/{card.total_runs} complete runs)",
        f"- **Stability**: {card.stability}",
        f"- **Last 5**: {l5}",
        "",
    ]

    if card.failure_modes:
        lines += [
            "## Failure Modes",
            "",
            "| Error | Count | % |",
            "|-------|-------|---|",
        ]
        for err, cnt, pct in card.failure_modes:
            e = err[:80] + "..." if len(err) > 80 else err
            lines.append(f"| {e} | {cnt} | {pct}% |")
        lines.append("")

    if card.per_backend:
        lines += [
            "## Per-Backend",
            "",
            "| Backend | Win Rate | Runs |",
            "|---------|----------|------|",
        ]
        for be, (w, t) in card.per_backend.items():
            wr = round(w / t * 100) if t > 0 else 0
            lines.append(f"| {be} | {wr}% ({w}/{t}) | {t} |")
        lines.append("")

    if card.do_not_repeat:
        lines += ["## DO_NOT_REPEAT", ""]
        for item in card.do_not_repeat:
            lines.append(f"- {item}")
        lines.append("")

    if card.redteam_notes:
        lines += ["## Redteam Notes", ""]
        for note in card.redteam_notes:
            lines.append(f"- {note}")
        lines.append("")

    if card.opt_notes:
        lines += ["## Optimization Notes", ""]
        for note in card.opt_notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_fix_registry(registry: list[FixEntry]) -> str:
    lines = [
        "# Fix Registry",
        "",
        "Consolidated DO_NOT_REPEAT from all PCDRED cycles.",
        "",
        "| Cycle | Fix | Verdict |",
        "|-------|-----|---------|",
    ]
    for fe in registry:
        d = fe.description[:70] + "..." if len(fe.description) > 70 else fe.description
        lines.append(f"| {fe.cycle_ts} | {d} | {fe.verdict} |")

    verdicts = Counter(fe.verdict for fe in registry)
    lines += ["", "## Summary", ""]
    for v, cnt in verdicts.most_common():
        lines.append(f"- **{v}**: {cnt}")
    return "\n".join(lines) + "\n"


def render_vuln_catalog(vulns: list[VulnEntry]) -> str:
    lines = [
        "# Vulnerability Catalog",
        "",
        "Attack patterns tested across PCDRED Red Team cycles.",
        "",
        "| Cycle | Attack | Rating | Change Tested |",
        "|-------|--------|--------|---------------|",
    ]
    for v in vulns:
        t = v.title[:50] + "..." if len(v.title) > 50 else v.title
        ch = v.change_tested[:50] + "..." if len(v.change_tested) > 50 else v.change_tested
        lines.append(f"| {v.cycle_ts} | {t} | {v.rating} | {ch} |")

    ratings = Counter(v.rating for v in vulns)
    lines += ["", "## Summary", ""]
    for r, cnt in ratings.most_common():
        lines.append(f"- **{r}**: {cnt}")
    return "\n".join(lines) + "\n"


def render_health(alerts: list[HealthAlert]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = ["# Health Report", "", f"*Generated: {now}*", ""]
    for a in alerts:
        lines.append(f"- [{a.level}] {a.message}")
    return "\n".join(lines) + "\n"


# ── Output ─────────────────────────────────────────────────────────────────


def write_wiki(
    pages: dict[str, str],
    task_cards_md: dict[str, str],
    meta: dict,
    task_filter: list[str] | None = None,
) -> None:
    """Write all wiki pages to docs/wiki/."""
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    if task_filter:
        for tid in task_filter:
            if tid in task_cards_md:
                (TASKS_DIR / f"{tid}.md").write_text(task_cards_md[tid])
        return

    for name, content in pages.items():
        (WIKI_DIR / name).write_text(content)
    (WIKI_DIR / "_meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    for tid, content in task_cards_md.items():
        (TASKS_DIR / f"{tid}.md").write_text(content)


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile BitGN Knowledge Wiki")
    parser.add_argument("--check", action="store_true", help="Lint only, no writes")
    parser.add_argument("--tasks", nargs="*", help="Rebuild specific task cards only")
    args = parser.parse_args()

    # 1. Load
    data = load_all_data()
    runs, cache = data["runs"], data["cache"]
    cycles, evals = data["cycles"], data["evals"]
    redteams, opts = data["redteams"], data["opts"]

    # 2. Discover all task IDs
    all_ids = set()
    for r in runs:
        all_ids.update(r.tasks.keys())
    all_ids.update(cache.keys())
    all_ids = sorted(all_ids)

    # 3. Synthesize
    task_cards = {
        tid: build_task_card(tid, runs, cache, cycles, redteams, opts) for tid in all_ids
    }
    fix_registry = build_fix_registry(cycles)
    vuln_catalog = build_vuln_catalog(redteams)
    scoreboard = build_scoreboard(runs)
    alerts = compute_health_checks(runs, cycles, evals, redteams, task_cards)

    # 4. Check mode — print and exit
    if args.check:
        for a in alerts:
            print(f"[{a.level}] {a.message}")
        return

    # 5. Render
    pages = {
        "index.md": render_index(scoreboard, task_cards, alerts, fix_registry),
        "scoreboard.md": render_scoreboard(scoreboard),
        "fix-registry.md": render_fix_registry(fix_registry),
        "vulnerability-catalog.md": render_vuln_catalog(vuln_catalog),
        "health.md": render_health(alerts),
    }
    task_cards_md = {tid: render_task_card(card) for tid, card in task_cards.items()}

    # 6. Meta
    rh_hash = ""
    if RUN_HISTORY_PATH.exists():
        rh_hash = hashlib.sha256(RUN_HISTORY_PATH.read_bytes()).hexdigest()[:16]

    meta = {
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "run_count": len(runs),
        "complete_run_count": len([r for r in runs if r.tasks_total >= MIN_COMPLETE_RUN_TASKS]),
        "task_count": len(all_ids),
        "report_counts": {
            "cycles": len(cycles),
            "eval": len(evals),
            "redteam": len(redteams),
            "optimization": len(opts),
        },
        "source_hashes": {"run_history.json": rh_hash},
    }

    # 7. Write
    task_filter = args.tasks if args.tasks else None
    write_wiki(pages, task_cards_md, meta, task_filter)

    complete = meta["complete_run_count"]
    print(f"Wiki compiled: {len(task_cards_md)} task cards + {len(pages)} pages -> docs/wiki/")
    print(
        f"Data: {len(runs)} runs ({complete} complete), "
        f"{len(cycles)} cycles, {len(evals)} evals, "
        f"{len(redteams)} redteam, {len(opts)} optimization"
    )


if __name__ == "__main__":
    main()
