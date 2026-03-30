---
name: run-benchmark
description: Run pac1-py or sandbox-py benchmark tasks with optional task filter. Use when you need to test agent changes against the BitGN benchmark.
---

# Run Benchmark

Run benchmark tasks for one of the two agents.

## Arguments

`$ARGUMENTS` format: `[agent] [task-filter]`
- Agent: `pac1` (default) or `sandbox`
- Task filter: space-separated task IDs like `t01 t03` (optional, runs all if omitted)

## Steps

1. Determine agent directory from arguments:
   - `pac1` or empty → `pac1-py/`
   - `sandbox` → `sandbox-py/`

2. Run the benchmark:
   - If task filter provided: `cd <agent-dir> && make task TASKS='<tasks>'`
   - If no filter: `cd <agent-dir> && make run`

3. After the run completes:
   - Read the terminal output and summarize: total tasks, pass/fail count, score
   - If `docs/run_history.json` was updated, note the new entry
   - Highlight any regressions (tasks that previously passed but now failed)
   - Highlight any improvements (tasks that previously failed but now passed)

4. If any tasks failed, briefly categorize failures:
   - Wrong answer vs security false positive vs timeout vs tool error
