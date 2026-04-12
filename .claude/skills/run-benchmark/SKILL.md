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
   - If no filter and agent is `pac1`: prefer `cd pac1-py && uv run python main.py --parallel=4`
   - If no filter and agent is `sandbox`: `cd sandbox-py && make run`

3. After the run completes:
   - Read the latest `docs/eval/run-*.md` if it exists and use it as the source of truth
   - Summarize: task count, pass/fail count, score, and benchmark size
   - If `docs/run_history.json` was updated, note the new entry
   - Highlight regressions (tasks that previously passed but now failed)
   - Highlight improvements (tasks that previously failed but now passed)
   - Flag whether this run introduced new task IDs or a changed task count

4. If any tasks failed, briefly categorize failures:
   - Wrong answer / precision
   - Security false positive
   - Security miss
   - Missing side effect or refs
   - Timeout / parse / infra issue
