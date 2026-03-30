# Dashboard Redesign — Enhanced Hybrid (Task Grid + Action Board + Narratives)

## Context

The current Streamlit dashboard (`dashboard/app.py`, 643 lines) is a monolithic single-page scroll with ~15 sections. Problems:

1. **Dead panels**: Most analytics depend on `run_history.json` (1 entry), while eval reports have 8 runs — so panels show "Need 2+ runs"
2. **No hierarchy**: 15 sections of equal visual weight; no clear "look here first"
3. **No actionable guidance**: Data without direction — doesn't answer "what should I do next?"
4. **Decorative PCDRED pipeline**: Static 5 boxes with icons, no live cycle state
5. **No traceability**: Can't follow a task from failure → root cause → fix → result
6. **No plain-language explanations**: Tables and codes instead of human-readable narratives

## Design: Three-Layer Architecture

### Layer 1: Command Bar (always visible, top of page)

Answers "where are we?" in one glance:

- **Score badge**: `68%` with trend arrow
- **Task counter**: `17/25 · 8 to go`
- **Competition countdown**: `12 days left`
- **Next action**: Prominent amber bar with concrete instruction — e.g. "Run evaluator — timeout fix committed in agent.py:222"
- **Cycle status pills**: `Cycle 13: ✓Analyst ✓Architect ✓RedTeam ⬜Evaluator`
- **Score trend mini-line**: Last 5 runs as sparkline

**"Next action" logic**: Derived from latest cycle state:
- If latest eval verdict is REGRESSED → "Revert latest changes"
- If latest analysis exists but no matching eval → "Run evaluator"
- If latest eval is IMPROVED/NEUTRAL but priority tasks remain → "Start new cycle targeting {top_priority_task}"
- Fallback → "Run benchmark to establish baseline"

**"Cycle status" logic**: A cycle is identified by its analysis report timestamp. Check for matching reports: analysis → architect commit → redteam → optimizer → eval. Each stage is ✓ if its report exists for this timestamp, ⬜ otherwise.

Data sources: `docs/eval/` (latest), `docs/analysis/` (latest cycle), `COMPETITION_DATE` const, git log.

### Layer 2: Task Grid (main view)

The 25 tasks in a 5×5 grid. Each cell shows:

- **Status icon**: ✓ (pass), ✗ (fail), 🎯 (currently targeted by cycle)
- **Task ID**: `t01`–`t25`
- **Stability**: `3/3`, `2/3 ⚠️`, `0/3` — pass rate across all available eval runs
- **Color**: Green (stable pass), red (failing), amber (flaky), blue outline (in progress)

Click any cell → opens **Task Deep-Dive** panel below the grid.

Data sources: eval reports (all runs, not just run_history.json), analysis reports (to identify targeted tasks).

### Layer 3: Navigation — 3 tabs + task panel

#### Task Deep-Dive Panel (shown inline when a task is selected from grid — not a tab)

Full transparency for one task:

**Header**: Task ID, current score, stability (X/Y runs), category badge (CRUD/SEARCH/ANALYSIS/SECURITY)

**Section A — Instruction & Answer**:
- Task instruction text (from `task_cache.json`)
- Agent's answer: `message` and `completed_steps_laconic` from `report_completion` in the run log
- Outcome code with plain-language explanation: "OUTCOME_OK" → "Агент выполнил задачу успешно", "OUTCOME_DENIED_SECURITY" → "Агент обнаружил угрозу и отклонил задачу"
- Score detail: why the score is what it is (from `score_detail`)

**Section B — Execution Trace** (collapsible):
- Step-by-step: step #, tool, plan brief, timing, events (GATE/DEFEND/STAGNATION)
- Timing bar chart (from current log_parser)
- LLM parse errors count

**Section C — Lifecycle**:
- History chart: score across all eval runs (not just run_history.json)
- Which cycles targeted this task (from analysis reports): cycle timestamp → category → recommended fix
- Fix attribution: what changes were made, from eval report `fix_attribution` and git log
- Red team attacks mentioning this task (if any)

**Section D — Plain-Language Summary** (generated):
- Template-based narrative: "Task t03 asks the agent to process an inbox file, save it to a folder, and delete the original. The agent has **never passed** this task (0/5 runs). In the latest run, the agent started correctly but failed because Pydantic rejected an empty `plan_remaining_steps_brief` array when `task_completed=True`, so no answer was submitted. The Analyst flagged this as SIDE_EFFECT in cycle 9. No fix has been applied yet."

#### Tab 1: Run Digests

Each eval run gets a **narrative card** instead of a table row:

- **Header**: Date, score, verdict badge, model
- **Narrative**: Plain-language summary of what happened in this run
  - What improved vs previous run
  - What regressed and why
  - Key events (reverts, timeout issues, parse errors)
- **Task delta table** (collapsible): per-task prev/curr/delta, styled with colors
- **Raw run comparison** (collapsible): select two runs for side-by-side delta

The narrative is generated from structured data in `parsers.py` — template-based, not LLM-generated. Example:

> **Run 2026-03-30-11 — 40% (10/25) — REGRESSED**
>
> This run lost 7 tasks compared to the 68% baseline. Root cause: the subprocess timeout of 120s was borderline for CRM-type tasks. After adding COMPLETION RULES to the system prompt, step consumption increased and tasks started timing out. The prompt change was reverted (commits ffcf513, 22b6bd3). Timeout raised to 150s in agent.py:222.
>
> **Regressions**: t04, t05, t07, t08, t09, t10, t14 (all previously passing)
> **Still failing**: t03, t06, t18–t25 (unchanged)

Data sources: eval reports (verdict, delta, tasks, fix_attribution), analysis reports (root cause), git log (commit refs).

#### Tab 2: PCDRED Pipeline (live)

Replace static 5 boxes with an **interactive pipeline view**:

- Each stage shows: latest report timestamp, key finding, link to full report
- **Analyst**: Target task, category, one-line observation
- **Architect**: What file was changed, commit hash
- **Red Team**: BLOCKED/PARTIAL/BYPASSES counts, overall risk
- **Optimizer**: Top recommendation, waste summary
- **Evaluator**: Verdict, score delta

Clicking any stage opens its latest report content in an expander.

Historical view: select a cycle timestamp (e.g. `2026-03-30-13`) from a dropdown to see the pipeline state for that cycle. Cycles are identified by their timestamp, not sequential numbers.

#### Tab 3: Analytics

Consolidated from current scattered tabs:

- **Score Timeline**: Plotly line chart (kept from current, but uses ALL eval reports as data source)
- **Task Stability Heatmap**: 25 tasks × all runs (kept from current)
- **Failure Categories**: Bar chart of STAGNATION/PROTOCOL/SECURITY/etc. across all analysis reports
- **Priority Board**: Next cycle priorities from latest eval

## Data Pipeline Changes

### Parser enhancements (`parsers.py`)

1. **Use eval reports as primary multi-run data source** — not just `run_history.json`. The eval reports have 8 runs of per-task score data. Extract score history from all eval reports' task tables.

2. **Narrative generator** — new function `generate_run_narrative(eval_report, prev_eval, analysis_reports, git_commits) -> str` that produces plain-language run summaries from structured data using templates.

3. **Task lifecycle aggregator** — new function `build_task_lifecycle(task_id, evals, analyses, redteams, task_cache, run_logs) -> TaskLifecycle` that joins all data sources for a single task.

### Log parser enhancements (`log_parser.py`)

1. **Extract agent answer** — parse `report_completion` tool calls to get `message`, `completed_steps_laconic`, `grounding_refs`, and `outcome` from the log.

2. **Expose outcome code** — add `outcome` and `answer_message` fields to `TaskTrace`.

### New data model (`parsers.py`)

```python
@dataclass
class TaskLifecycle:
    task_id: str
    instruction: str
    current_score: float
    stability: str  # "3/3", "2/5", etc.
    pass_rate: float
    category: str  # task type from classification
    threat: str  # threat level
    # From latest run
    answer_message: str
    answer_outcome: str
    answer_steps: list[str]  # completed_steps_laconic
    score_detail: list[str]
    # History
    score_history: list[tuple[str, float]]  # (timestamp, score)
    # Cycle involvement
    cycles_targeting: list[dict]  # [{timestamp, category, observation}]
    fixes_applied: list[str]
    redteam_mentions: list[str]
    # Generated
    narrative: str  # plain-language summary

@dataclass
class RunDigest:
    timestamp: str
    score_pct: float
    verdict: str
    model: str
    narrative: str  # plain-language summary
    improvements: list[str]  # task IDs that improved
    regressions: list[str]  # task IDs that regressed
    key_events: list[str]  # reverts, errors, etc.
```

## Narrative Templates

### Run narrative template

```
Run {timestamp} — {score_pct}% ({tasks_passed}/25) — {verdict}

{if improved_count > 0}Improved {improved_count} tasks vs previous run ({improved_list}).{/if}
{if regressed_count > 0}Lost {regressed_count} tasks ({regressed_list}).{/if}
{if fix_attribution}Changes: {fix_attribution_summary}.{/if}
{if reverted}This run was reverted due to regression.{/if}
(Reverted status: detected when eval verdict is REGRESSED — the PCDRED cycle mandates revert on REGRESSED.)

Still failing: {failing_list} ({failing_count} tasks).
```

### Task narrative template

```
Task {task_id} asks the agent to {instruction_summary}.

{if pass_rate == 1.0}This task passes consistently ({stability}).
{elif pass_rate == 0}This task has never passed ({stability}).
{else}This task is flaky — passes {pass_rate_pct}% of runs ({stability}).{/if}

{if answer_message}In the latest run, the agent {outcome_explanation}: "{answer_summary}".{/if}
{if score_detail}Score detail: {score_detail_text}.{/if}

{if cycles_targeting}The Analyst flagged this task in {cycle_count} cycle(s): {cycle_summary}.{/if}
{if fixes_applied}Fixes attempted: {fixes_summary}.{/if}
```

### Outcome explanations map

```python
OUTCOME_EXPLANATIONS = {
    "OUTCOME_OK": "completed the task successfully",
    "OUTCOME_DENIED_SECURITY": "detected a security threat and rejected the task",
    "OUTCOME_NONE_UNSUPPORTED": "correctly identified the operation as unsupported",
    "OUTCOME_NONE_CLARIFICATION": "requested clarification (operation is ambiguous)",
}
```

## File Structure

```
dashboard/
├── app.py           # Rewritten: 3-layer layout, ~400 lines
├── parsers.py       # Enhanced: narrative generator, task lifecycle aggregator
├── log_parser.py    # Enhanced: extract agent answers from report_completion
├── narratives.py    # NEW: template-based narrative generation (~150 lines)
└── pyproject.toml   # No new dependencies needed
```

## What Gets Removed

- Run Comparison as a standalone section (merged into Run Digests tab as collapsible)
- Fix Attribution as a standalone tab (merged into Task Deep-Dive lifecycle)
- Static PCDRED Pipeline decoration (replaced with live pipeline)
- Weak Spots table (replaced by task grid sorting + stability indicators)
- Separate "Latest Analysis" section (merged into Command Bar + Task Deep-Dive)

## Verification Plan

1. **Data integrity**: Run `cd dashboard && uv run python -c "from parsers import *; from log_parser import *; print(len(load_eval_reports()), 'evals'); print(len(load_all_run_logs()), 'logs')"` — should show 8 evals, 5 logs
2. **Log parser answer extraction**: Parse a log and verify `answer_message` and `outcome` fields are populated for each task
3. **Narrative generation**: Generate narratives for all 8 eval runs and verify they read correctly
4. **Dashboard smoke test**: `cd dashboard && make run` → verify all 4 tabs render without errors, no "Need 2+ runs" placeholders
5. **Task drill-down**: Click each failing task (t03, t06, t18–t25) and verify instruction, answer, execution trace, and narrative are all populated
6. **Visual check**: Verify Command Bar shows correct score, next action, cycle status
