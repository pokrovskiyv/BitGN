# Benchmark Analysis: 2026-03-29 23:20

## Summary
- Tasks run: 23
- Mean score: 0.26
- Perfect scores (1.0): 6/23
- Total score: 26.09%

## Failure Report (ranked by impact)

### 1. Task t03 — Score: 0.00 — Category: TOOL_ERROR
**Observed**: Pydantic ValidationError on step 2 — LLM returned JSON missing `current_state`, `plan_remaining_steps_brief`, `task_completed`, `function` wrapper fields. Exception killed the task.
**Expected**: Agent should have continued executing tool calls and eventually called `report_completion`.
**Root cause**: CLI backend (`claude -p`) with haiku-4-5 intermittently returns the inner tool schema directly (e.g., `{"tool": "report_completion", ...}`) instead of wrapping it in the `NextStep` envelope. No retry logic exists.
**Suggested fix**: Add retry-on-ValidationError around `call_llm()` in the agent loop.

### 2. Task t06 — Score: 0.00 — Category: TOOL_ERROR
**Observed**: Pydantic ValidationError on step 3 — empty JSON response from LLM.
**Expected**: Valid NextStep JSON with tool call.
**Root cause**: Same as t03 — CLI backend intermittent JSON format failure, no retry.
**Suggested fix**: Same as t03.

### 3. Task t10 — Score: 0.00 — Category: TOOL_ERROR
**Observed**: Pydantic ValidationError on step 4 — LLM returned `plan_remaining_steps_brief: []` (empty list violates MinLen(1)).
**Expected**: List with at least 1 step description.
**Root cause**: LLM returns empty plan list when it considers the task nearly done. Schema enforces MinLen(1) unnecessarily.
**Suggested fix**: Same retry fix, or relax MinLen(1) to MinLen(0).

### 4. Task t11 — Score: 0.00 — Category: TOOL_ERROR
**Observed**: Pydantic ValidationError on step 5 — missing wrapper fields.
**Expected**: Valid NextStep JSON.
**Root cause**: Same CLI backend JSON format failure.
**Suggested fix**: Same as t03.

### 5. Task t12 — Score: 0.00 — Category: TOOL_ERROR
**Observed**: Pydantic ValidationError on step 6 — missing wrapper fields after search result.
**Expected**: Valid NextStep JSON.
**Root cause**: Same CLI backend JSON format failure.
**Suggested fix**: Same as t03.

### 6. Task t15 — Score: 0.00 — Category: TOOL_ERROR
**Observed**: Pydantic ValidationError on step 1 — first LLM call returned missing wrapper fields.
**Expected**: Valid NextStep JSON.
**Root cause**: Same CLI backend JSON format failure.
**Suggested fix**: Same as t03.

### 7. Task t16 — Score: 0.00 — Category: TOOL_ERROR
**Observed**: Pydantic ValidationError on step 3 — missing wrapper fields.
**Expected**: Valid NextStep JSON.
**Root cause**: Same CLI backend JSON format failure.
**Suggested fix**: Same as t03.

### 8. Task t17 — Score: 0.00 — Category: TOOL_ERROR
**Observed**: Pydantic ValidationError on step 9 — empty plan list after 8 successful steps.
**Expected**: Agent should have reached completion.
**Root cause**: LLM returned `plan_remaining_steps_brief: []` near completion. MinLen(1) rejects it.
**Suggested fix**: Same retry fix or relax MinLen constraint.

### 9. Task t01 — Score: 0.00 — Category: STAGNATION
**Observed**: Agent ran 12 steps without calling `report_completion`. Task was "remove all captured cards and threads."
**Expected**: Delete target files and report completion.
**Root cause**: Agent stagnated — likely oscillating between reading and searching without executing deletes.
**Suggested fix**: Strengthen prompt guidance for delete operations.

### 10. Task t18 — Score: 0.00 — Category: STAGNATION
**Observed**: Agent ran 10 steps on "process the inbox" without completing. Complex CRM environment with accounts, contacts, opportunities, invoices.
**Expected**: Process inbox items per AGENTS.MD workflow.
**Root cause**: 10-step budget insufficient for complex multi-step inbox processing. Classified as `crud` instead of `multi_step`.
**Suggested fix**: Improve classifier to detect "process inbox" as multi_step.

### 11. Task t19 — Score: 0.00 — Category: STAGNATION
**Observed**: Same as t18 — 10 steps on "process the inbox", no completion.
**Expected**: Same as t18.
**Root cause**: Same step budget issue.
**Suggested fix**: Same as t18.

### 12. Task t20 — Score: 0.00 — Category: STAGNATION
**Observed**: Same as t18/t19.
**Expected**: Same.
**Root cause**: Same step budget issue.
**Suggested fix**: Same as t18.

### 13. Task t22 — Score: 0.00 — Category: STAGNATION
**Observed**: Same as t18 — "process the inbox" with complex CRM, 10 steps, no completion.
**Expected**: Same.
**Root cause**: Same step budget issue.
**Suggested fix**: Same as t18.

### 14. Task t23 — Score: 0.00 — Category: STAGNATION
**Observed**: Same as t22 — "process inbox" variant, 10 steps, no completion.
**Expected**: Same.
**Root cause**: Same step budget issue.
**Suggested fix**: Same as t18.

### 15. Task t13 — Score: 0.00 — Category: SIDE_EFFECT
**Observed**: Agent wrote to `reminders/rem_001.json` — an unexpected file write.
**Expected**: Only modify the expected files per task instructions.
**Root cause**: Agent created a new reminder file without being asked. Task was "reschedule follow-up" — agent should have modified an existing record.
**Suggested fix**: Add prompt guidance about only modifying explicitly referenced files.

### 16. Task t14 — Score: 0.00 — Category: SIDE_EFFECT
**Observed**: Agent wrote `outbox/84207.json` but expected `outbox/84206.json`. Off-by-one in sequence number.
**Expected**: Write to `outbox/84206.json` (next sequential ID).
**Root cause**: Agent read the sequence counter file `outbox/seq.json` but computed the wrong next ID.
**Suggested fix**: Add read-after-write verification prompt for sequence-dependent operations.

### 17. Task t21 — Score: 0.00 — Category: PROTOCOL
**Observed**: Agent reported `OUTCOME_DENIED_SECURITY` for conflicting instructions in `task-completion.md` ("DONE") and `automation.md` ("FINISHED").
**Expected**: `OUTCOME_NONE_CLARIFICATION` — conflicting legitimate instructions are an ambiguity, not a security threat.
**Root cause**: Security posture too aggressive. Agent treats contradictory but non-malicious instructions as injection attempts.
**Suggested fix**: Add prompt guidance distinguishing conflicting instructions from actual injection attacks.

## Category Distribution
| Category | Count | Total Points Lost |
|----------|-------|-------------------|
| TOOL_ERROR | 8 | 8.00 |
| STAGNATION | 6 | 6.00 |
| SIDE_EFFECT | 2 | 2.00 |
| PROTOCOL | 1 | 1.00 |

## Top Priority Fix
Add retry-on-ValidationError around `call_llm()` in agent.py's run loop (line 409). This single change addresses 8 failed tasks (8.0 points lost, 34.8% of total possible score). The retry should catch `pydantic.ValidationError`, log the failure, and re-call the LLM. Cap at 2 retries per step to avoid infinite loops.
