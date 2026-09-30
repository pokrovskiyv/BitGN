---
name: triage-benchmark-update
description: Compare the latest full benchmark run against the previous complete run when task count, task wording, or task mix changed. Use to surface new tasks, new failure modes, regressions, likely flakes, and the next 3 fixes.
---

# Triage Benchmark Update

Use after a full run when the benchmark may have changed.

## Inputs

`$ARGUMENTS` format: `[run-path]`
- Optional explicit path to `docs/eval/run-YYYY-MM-DD-HH.md`
- If omitted, use the latest full run in `docs/eval/`

## Steps

1. Read the latest full run and the previous full run.
2. Read `docs/run_history.json` and `docs/wiki/index.md`.
3. Detect benchmark drift:
   - task count changed;
   - new task IDs appeared;
   - tasks with only 1-2 historical runs;
   - regressions concentrated in one task type or one failure class.
4. Cluster failures into a small set of classes:
   - infrastructure / transient API;
   - security miss;
   - security false positive;
   - missing side effect or grounding refs;
   - precision / answer format;
   - budget / parse failure.
5. Use task-card history in `docs/wiki/tasks/tNN.md` to separate:
   - likely deterministic failures;
   - likely flakes;
   - genuinely new task patterns.
6. Recommend exactly 3 next actions:
   - pipeline hardening;
   - task-logic or prompt fix;
   - defer / watch only.

## Output Format

Present a concise memo with:

- `LATEST RUN`
- `BENCHMARK DRIFT`
- `NEW TASKS`
- `REGRESSIONS`
- `LIKELY FLAKES`
- `TOP 3 NEXT ACTIONS`

## Rules

- Prefer absolute numbers and exact task IDs.
- Treat benchmark-size changes as first-class signal, not noise.
- Do not edit code from this skill unless explicitly asked.
- Keep the memo short enough to guide the next engineering step immediately.
