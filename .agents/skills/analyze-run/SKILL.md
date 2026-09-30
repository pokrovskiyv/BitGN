---
name: analyze-run
description: Analyze recent benchmark runs from run_history.json — surface regressions, wins, score trends, and per-task patterns. Use to understand agent performance over time.
---

# Analyze Run

Analyze benchmark run history and surface actionable insights.

## Arguments

`$ARGUMENTS` format: `[count]`
- Number of recent runs to analyze (default: 5)

## Steps

1. Read `docs/run_history.json` and load the last N runs (default 5).

2. **Score trend**: Show mean score progression across runs. Flag if trending up, down, or flat.

3. **Per-task analysis**: For each task that appeared in recent runs:
   - Current pass/fail status
   - Score history (last N runs)
   - Flag **regressions**: tasks that passed before but fail now
   - Flag **persistent failures**: tasks that have never passed
   - Flag **improvements**: tasks that recently started passing
   - Flag **new tasks** or tasks with only 1-2 historical runs

4. **Weak spots**: Identify the top 3 tasks with lowest average scores. For each, note:
   - Task type (from classify.py categories if recognizable)
   - Likely failure mode (wrong answer, security false positive, timeout, tool error)

5. **Benchmark drift**:
   - Compare the last two complete runs and note if benchmark size changed
   - Identify new failure classes that did not appear in prior runs
   - Separate likely deterministic failures from likely flakes using task-card history where needed

6. **Recommendations**: Based on the analysis, suggest:
   - Which task category to focus the next PCDRED cycle on
   - Whether to target pipeline hardening, prompt changes, or code changes
   - Specific files likely involved (reference workspace/prompts/fragments/ or agent modules)

## Output Format

Present as a concise summary table followed by:
- regressions
- new tasks / benchmark drift
- likely flakes
- actionable recommendations

Do not dump raw JSON.
