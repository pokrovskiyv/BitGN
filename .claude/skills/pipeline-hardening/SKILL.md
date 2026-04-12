---
name: pipeline-hardening
description: Harden the pac1-py run pipeline for a growing and unstable benchmark. Use when retries, parallelism, resume, reporting, or scaling limits need attention more than task-specific logic.
---

# Pipeline Hardening

Focus on run reliability and scaling, not on individual task answers.

## Read First

- `pac1-py/main.py`
- `pac1-py/llm.py`
- `pac1-py/second_opinion.py`
- `pac1-py/bitgn_benchmark.py`
- `pac1-py/evolve.py`
- `docs/run_history.json`
- `docs/wiki/index.md`

## Safe Write Set

- `pac1-py/main.py`
- `pac1-py/llm.py`
- `pac1-py/second_opinion.py`
- `pac1-py/bitgn_benchmark.py`
- `pac1-py/evolve.py`
- `pac1-py/Makefile`

## Priorities

1. Retries / backoff for transient LLM or API failures
2. Safer parallel mode for one-shot full runs
3. Resume and progress robustness
4. Scaling limits such as hard caps or hidden task truncation
5. Reporting or wiki-refresh issues only if they affect operator workflow

## Rules

- No task-ID hacks.
- No prompt tuning from this skill unless infra is blocked by prompt handling.
- Prefer the smallest generalizable diff.
- Keep the full-run path stable: do not change model or benchmark semantics.
- If a fix is risky close to the final, explain why and stop instead of guessing.

## Output

Always report:

- `CHANGED FILES`
- `RISKS REMOVED`
- `SMOKE COMMANDS`
- `OPEN RISKS`
