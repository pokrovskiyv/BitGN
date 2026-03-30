---
name: pcdred-cycle
description: Dispatch a full PCDRED improvement cycle (Analyst → Architect → Red Team → Evaluator). Use after a benchmark run to systematically improve the agent.
disable-model-invocation: true
---

# PCDRED Cycle

Run one full Perceive-Classify-Decide-Refine-Evaluate-Defend cycle to improve the pac1-py agent.

## Steps

1. **Pre-check**: Verify `docs/run_history.json` has recent run data. If the last run is stale (> 1 hour old), suggest running `/run-benchmark` first.

2. **Analyst** (Perceive + Classify): Dispatch the Analyst agent to analyze the latest benchmark run and produce a failure classification report in `docs/analysis/`.
   ```
   Use Agent tool with .claude/agents/analyst.md role
   ```

3. **Architect** (Decide + Refine): Dispatch the Architect agent to read the Analyst report and implement ONE minimal fix. The fix should target the highest-impact failure category.
   ```
   Use Agent tool with .claude/agents/architect.md role
   ```

4. **Red Team** (Defend): Dispatch the Red Team agent to attack the Architect's changes and write a report to `docs/redteam/`.
   ```
   Use Agent tool with .claude/agents/red-team.md role
   ```

5. **Evaluator** (Evaluate): Run the benchmark via the Evaluator agent. It compares new_mean vs old_mean.
   ```
   Use Agent tool with .claude/agents/evaluator.md role
   ```

6. **Verdict**: Report the cycle outcome:
   - IMPROVED (new_mean > old_mean) → commit the changes
   - REGRESSED (new_mean < old_mean) → revert and explain what went wrong
   - NEUTRAL (new_mean == old_mean) → do NOT commit; explain why the fix had no effect

## Rules

- ONE fix per cycle only — do not batch multiple changes
- Never touch `defend.py` or `classify.py` without Red Team review
- Prefer prompt edits in `workspace/prompts/` over Python code changes
- The Evaluator has final say — do not override its verdict
