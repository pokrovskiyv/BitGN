"""Parse PCDRED markdown reports into structured data."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
    timestamp: str          # "2026-03-30-07"
    dt: datetime
    verdict: str            # IMPROVED | NEUTRAL | REGRESSED | IMPROVED_WITH_REGRESSION
    score_pct: float        # 68.0
    tasks_passed: int       # 17
    delta_pct: float        # +8.0
    tasks: list
    model: str
    log_path: str


@dataclass
class AnalysisReport:
    timestamp: str
    dt: datetime
    target_task: str
    category: str           # STAGNATION | PROTOCOL | SECURITY | etc.
    summary: str            # first line of Observation section


@dataclass
class AttackResult:
    number: int
    rating: str             # BLOCKED | PARTIAL | BYPASSES
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


# ── Timestamp parsing ─────────────────────────────────────────────────────────

def _parse_ts(stem: str) -> tuple:
    """Extract YYYY-MM-DD-HH from filename stem."""
    m = re.search(r"(\d{4}-\d{2}-\d{2}-\d{2})", stem)
    if m:
        ts = m.group(1)
        y, mo, d, h = ts.split("-")
        return ts, datetime(int(y), int(mo), int(d), int(h))
    return stem, datetime(2026, 1, 1)  # fallback for legacy names


# ── Eval report parser ────────────────────────────────────────────────────────

def parse_eval_report(path: Path) -> EvalReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)

    verdict_m = re.search(r"## Verdict:\s*(\S+)", text)
    verdict = verdict_m.group(1) if verdict_m else "UNKNOWN"

    total_m = re.search(r"Current total:\s*([\d.]+)%\s*\((\d+)/25", text)
    score_pct = float(total_m.group(1)) if total_m else 0.0
    tasks_passed = int(total_m.group(2)) if total_m else 0

    delta_m = re.search(r"Delta:\s*([+-]?[\d.]+)%", text)
    delta_pct = float(delta_m.group(1)) if delta_m else 0.0

    rows = re.findall(
        r"\|\s*(t\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([+-]?[\d.]+)\s*\|\s*([^|\n]+)",
        text,
    )
    tasks = [
        TaskScore(r[0], float(r[1]), float(r[2]), float(r[3]), r[4].strip())
        for r in rows
    ]

    model_m = re.search(r"Model:\s*(.+)", text)
    model = model_m.group(1).strip() if model_m else "unknown"

    log_m = re.search(r"Log:\s*(.+)", text)
    log_path = log_m.group(1).strip() if log_m else ""

    return EvalReport(ts, dt, verdict, score_pct, tasks_passed, delta_pct, tasks, model, log_path)


# ── Analysis report parser ────────────────────────────────────────────────────

def parse_analysis_report(path: Path) -> AnalysisReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)

    task_m = re.search(r"\*\*Task\*\*:\s*(\S+)", text)
    target_task = task_m.group(1) if task_m else "unknown"

    cat_m = re.search(r"\*\*Category\*\*:\s*(\S+)", text)
    category = cat_m.group(1) if cat_m else "UNKNOWN"

    obs_m = re.search(r"## Observation\s*\n+(.+?)(?:\n\n|\Z)", text, re.DOTALL)
    summary = obs_m.group(1).strip().split("\n")[0][:120] if obs_m else ""

    return AnalysisReport(ts, dt, target_task, category, summary)


# ── Red team report parser ────────────────────────────────────────────────────

def parse_redteam_report(path: Path) -> RedTeamReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)

    attacks = []
    for i, block in enumerate(re.split(r"## Attack \d+", text)[1:], start=1):
        rating_m = re.search(r"\*\*Rating\*\*:\s*(\w+)", block)
        target_m = re.search(r"\*\*Target\*\*:\s*(.+)", block)
        attacks.append(AttackResult(
            number=i,
            rating=rating_m.group(1) if rating_m else "UNKNOWN",
            target=target_m.group(1).strip()[:80] if target_m else "",
        ))

    return RedTeamReport(ts, dt, attacks)


# ── Optimization report parser ────────────────────────────────────────────────

def parse_opt_report(path: Path) -> OptReport:
    text = path.read_text()
    ts, dt = _parse_ts(path.stem)

    recs = re.findall(r"\*\*Recommendation\*\*:\s*(.+)", text)
    short_recs = [r.strip()[:100] for r in recs[:6]]

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


# ── Loaders ───────────────────────────────────────────────────────────────────

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
