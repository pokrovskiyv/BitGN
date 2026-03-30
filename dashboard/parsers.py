"""Parse PCDRED markdown reports into structured data."""

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
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
    fix_attribution: str        # full Fix Attribution section text
    consistently_failing: list  # [{"task": "t21", "cause": "PROTOCOL", "notes": "..."}]
    next_priorities: list       # ["t21 (PROTOCOL): ...", "t03 (SIDE_EFFECT): ..."]


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


@dataclass
class RunRecord:
    timestamp: str          # ISO 8601: "2026-03-30T09:00:00+00:00"
    dt: datetime
    model: str
    score_pct: float
    tasks_passed: int
    tasks_total: int
    tasks: dict             # {task_id: {"score": float, "score_detail": list[str]}}


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

    # Fix Attribution section
    fix_attr_m = re.search(
        r"## Fix Attribution\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
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
            consistently_failing.append({
                "task": r[0].strip(),
                "cause": r[1].strip(),
                "notes": r[2].strip(),
            })

    # Next Cycle Priorities
    next_priorities = []
    prio_m = re.search(
        r"## Next Cycle Priorities\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if prio_m:
        for line in prio_m.group(1).strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                next_priorities.append(re.sub(r"^\d+\.\s*", "", line))

    return EvalReport(
        ts, dt, verdict, score_pct, tasks_passed, delta_pct,
        tasks, model, log_path, fix_attribution, consistently_failing, next_priorities,
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
            records.append(RunRecord(
                timestamp=ts,
                dt=dt,
                model=entry.get("model", "unknown"),
                score_pct=float(entry.get("score_pct", 0.0)),
                tasks_passed=int(entry.get("tasks_passed", 0)),
                tasks_total=int(entry.get("tasks_total", 25)),
                tasks=entry.get("tasks", {}),
            ))
        except Exception:
            continue
    return sorted(records, key=lambda r: r.dt)


# ── Git log ───────────────────────────────────────────────────────────────────

@dataclass
class GitCommit:
    hash: str
    message: str
    commit_type: str        # "feat", "fix", "perf", "docs", etc.


def load_git_log(limit: int = 30) -> list:
    """Load recent git commits. Returns list[GitCommit] newest-first."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{limit}"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
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
