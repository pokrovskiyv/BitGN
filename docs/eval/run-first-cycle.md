# Evaluation Report: 2026-03-30 00:00

## Verdict: IMPROVED_WITH_REGRESSION
## Action: COMMIT + investigate t07 regression

## Scores
| Task ID | Previous | Current | Delta | Status |
|---------|----------|---------|-------|--------|
| t01 | 0.00 | 0.00 | 0.00 | — |
| t02 | 1.00 | 1.00 | 0.00 | — |
| t03 | 0.00 | 0.00 | 0.00 | — |
| t04 | 1.00 | 1.00 | 0.00 | — |
| t05 | 1.00 | 1.00 | 0.00 | — |
| t06 | 0.00 | 1.00 | +1.00 | IMPROVED |
| t07 | 1.00 | 0.00 | -1.00 | REGRESSED |
| t08 | 1.00 | 1.00 | 0.00 | — |
| t09 | 1.00 | 1.00 | 0.00 | — |
| t10 | 0.00 | 1.00 | +1.00 | IMPROVED |
| t11 | 0.00 | 0.00 | 0.00 | — |
| t12 | 0.00 | 0.00 | 0.00 | — |
| t13 | 0.00 | 0.00 | 0.00 | — |
| t14 | 0.00 | 1.00 | +1.00 | IMPROVED |
| t15 | 0.00 | 1.00 | +1.00 | IMPROVED |
| t16 | 0.00 | 0.00 | 0.00 | — |
| t17 | 0.00 | 1.00 | +1.00 | IMPROVED |
| t18 | 0.00 | 1.00 | +1.00 | IMPROVED |
| t19 | 0.00 | 0.00 | 0.00 | — |
| t20 | 0.00 | 1.00 | +1.00 | IMPROVED |
| t21 | 0.00 | 0.00 | 0.00 | — |
| t22 | 0.00 | 0.00 | 0.00 | — |
| t23 | 0.00 | 0.00 | 0.00 | — |
| t24 | — | 0.00 | NEW | — |
| t25 | — | 1.00 | NEW | — |

## Aggregate
- Previous total: 26.09% (6/23 tasks)
- Current total: 52.00% (13/25 tasks)
- Delta: +25.91%
- Tasks improved: 7 (t06, t10, t14, t15, t17, t18, t20)
- Tasks regressed: 1 (t07)
- Tasks unchanged: 15
- New tasks: 2 (t24=0.00, t25=1.00)

## Retry Impact
The retry fix triggered on 13 occasions across 10 tasks:
- Successful recovery (attempt 1 or 2 fixed it): t06, t09, t10, t14, t15 — all scored 1.00
- Exhausted retries (all 3 failed): t03, t07, t13 — all scored 0.00
- Recovery rate: ~62% of retry events led to successful step completion

## Regressions
### Task t07: 1.00 → 0.00
**Change that likely caused regression**: Not directly caused by the code change. t07 ("Process the next file from the inbox") ran 10 steps with 4 retry events. The LLM exhausted retries twice (steps 7 and 10). This is LLM non-determinism — haiku-4-5 via CLI produces invalid JSON intermittently, and this task happened to hit persistent errors in this run.
**Suggested investigation**: Re-run t07 in isolation (`make task TASKS='t07'`) to confirm non-determinism vs systematic failure.

## Environment
- Model: claude-haiku-4-5
- Backend: cli
- Benchmark: bitgn/pac1-dev
- Timestamp: 2026-03-30T00:00:00Z
- Log: /tmp/benchmark-cycle1.log
