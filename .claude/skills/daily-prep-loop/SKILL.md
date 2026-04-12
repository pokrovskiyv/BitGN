---
name: daily-prep-loop
description: Coordinate the BitGN daily preparation loop while benchmark tasks are still changing. Use to decide whether to run a full benchmark, triage benchmark drift, harden the pipeline, or run one focused PCDRED fix cycle.
---

# Daily Prep Loop

This is the lightweight coordinator skill for day-to-day work.

## Read First

- `docs/wiki/index.md`
- `docs/wiki/scoreboard.md`
- latest `docs/eval/run-*.md`
- `docs/run_history.json`

## Decision Modes

Choose exactly one primary mode:

1. `RUN`
   - No fresh full run exists
   - Recent code changes have not been evaluated yet

2. `TRIAGE`
   - Task count changed
   - New tasks appeared
   - Failure mix changed sharply

3. `HARDEN`
   - Infra errors, empty answers, resume issues, or parallel instability dominate

4. `FIX`
   - Benchmark is stable enough and there is one clear highest-value failure class

## Routing

- `RUN` → use `run-benchmark`
- `TRIAGE` → use `triage-benchmark-update`
- `HARDEN` → use `pipeline-hardening`
- `FIX` → use `pcdred-cycle`

## Output Format

Respond with only:

- `CURRENT STATUS`
- `PRIMARY MODE`
- `EXACT NEXT ACTION`
- `DO NOT TOUCH`

## Rules

- Pick one mode only.
- Prefer the next action that reduces uncertainty the most.
- Freeze broad refactors while task distribution is still moving.
