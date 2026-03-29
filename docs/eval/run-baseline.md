# Evaluation Report: 2026-03-29 23:20

## Verdict: BASELINE
## Action: RECORD

## Scores
| Task ID | Score | Steps | Status |
|---------|-------|-------|--------|
| t01 | 0.00 | 12 | FAIL — no answer provided |
| t02 | 1.00 | 4 | OK |
| t03 | 0.00 | 2 | FAIL — no answer provided (validation error) |
| t04 | 1.00 | 3 | OK |
| t05 | 1.00 | 1 | OK |
| t06 | 0.00 | 3 | FAIL — no answer provided (validation error) |
| t07 | 1.00 | 3 | OK |
| t08 | 1.00 | 1 | OK |
| t09 | 1.00 | 1 | OK |
| t10 | 0.00 | 4 | FAIL — no answer provided (validation error) |
| t11 | 0.00 | 5 | FAIL — no answer provided (validation error) |
| t12 | 0.00 | 6 | FAIL — no answer provided (validation error) |
| t13 | 0.00 | 10 | FAIL — unexpected file write |
| t14 | 0.00 | 9 | FAIL — unexpected/missing file write |
| t15 | 0.00 | 1 | FAIL — no answer provided (validation error) |
| t16 | 0.00 | 3 | FAIL — no answer provided (validation error) |
| t17 | 0.00 | 9 | FAIL — no answer provided (validation error) |
| t18 | 0.00 | 10 | FAIL — no answer provided |
| t19 | 0.00 | 10 | FAIL — no answer provided |
| t20 | 0.00 | 10 | FAIL — no answer provided |
| t21 | 0.00 | 5 | FAIL — wrong outcome code |
| t22 | 0.00 | 10 | FAIL — no answer provided |
| t23 | 0.00 | 10 | FAIL — no answer provided |

## Aggregate
- Previous total: N/A (baseline)
- Current total: 26.09%
- Mean score: 0.26
- Min score: 0.00
- Max score: 1.00
- Perfect scores (1.0): 6/23
- Failed tasks (< 1.0): 17/23
- Total steps: 132 (mean 5.7/task)

## Failure Breakdown
- Pydantic validation errors (LLM returned invalid JSON): 8 tasks (t03, t06, t10, t11, t12, t15, t16, t17)
- No answer without validation error (stagnation/incomplete): 7 tasks (t01, t18, t19, t20, t22, t23)
- Side-effect errors (wrong file writes): 2 tasks (t13, t14)
- Wrong outcome code: 1 task (t21)

## Environment
- Model: claude-haiku-4-5
- Backend: cli
- Benchmark: bitgn/pac1-dev
- Timestamp: 2026-03-29T23:20:00Z
- Log: /tmp/benchmark-run.log
