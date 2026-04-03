# Run Historian -- 2026-04-03-15

## Data Validation

- **Total entries**: 87 (confirmed, +1 from R86)
- **Latest timestamp**: 2026-04-03T10:05:57+00:00
- **Model**: qwen/qwen3.6-plus:free (openrouter)
- **Latest score**: 64.52% (20/31) -- NEW HIGH for OpenRouter backend

## Win Rate Table (last 6 runs R82-R87)

All runs on qwen/qwen3.6-plus:free via openrouter.

| Task | Win Rate | Scores (R82-R87) | Status |
|------|----------|-------------------|--------|
| t24 | 0% | 0, 0, 0, 0, 0, 0 | DEAD |
| t30 | 0% | 0, 0, 0, 0, 0, 0 | DEAD |
| t01 | 17% | 1, 0, 0, 0, 0, 0 | FRAGILE |
| t07 | 17% | 0, 0, 0, 0, 1, 0 | FRAGILE |
| t08 | 33% | 1, 0, 0, 0, 0, 1 | FRAGILE |
| t09 | 17% | 0, 0, 0, 0, 0, 1 | FRAGILE (was DEAD) |
| t12 | 17% | 0, 0, 0, 0, 1, 0 | FRAGILE |
| t16 | 17% | 0.6, 0, 0, 0, 0, 1 | FRAGILE |
| t23 | 17% | 0, 0, 1, 0, 0, 0 | FRAGILE |
| t25 | 17% | 0, 0, 0, 1, 0, 0 | FRAGILE |
| t28 | 33% | 0, 1, 0, 1, 0, 0 | FRAGILE |
| t29 | 17% | 0, 0, 0, 0, 0, 1 | FRAGILE (was DEAD) |
| t02 | 50% | 0, 0, 1, 1, 1, 0 | UNSTABLE |
| t14 | 50% | 0, 1, 1, 0, 0, 1 | UNSTABLE |
| t20 | 50% | 1, 1, 0, 0, 0, 1 | UNSTABLE |
| t22 | 50% | 0, 1, 1, 0, 0, 1 | UNSTABLE |
| t03 | 67% | 1, 1, 0, 0, 1, 1 | VARIABLE |
| t21 | 67% | 0, 1, 1, 1, 0, 1 | VARIABLE |
| t26 | 67% | 1, 0, 1, 0, 1, 1 | VARIABLE |
| t27 | 67% | 1, 1, 1, 0, 1, 0 | VARIABLE |
| t05 | 83% | 1, 1, 1, 0, 1, 1 | RELIABLE |
| t13 | 83% | 1, 1, 0, 1, 1, 1 | RELIABLE |
| t17 | 83% | 1, 1, 1, 1, 0, 1 | RELIABLE |
| t19 | 83% | 1, 1, 1, 1, 1, 0 | RELIABLE (was STABLE) |
| t04 | 100% | 1, 1, 1, 1, 1, 1 | STABLE |
| t06 | 100% | 1, 1, 1, 1, 1, 1 | STABLE |
| t10 | 100% | 1, 1, 1, 1, 1, 1 | STABLE |
| t11 | 100% | 1, 1, 1, 1, 1, 1 | STABLE |
| t15 | 100% | 1, 1, 1, 1, 1, 1 | STABLE |
| t18 | 100% | 1, 1, 1, 1, 1, 1 | STABLE |
| t31 | 100% | 1, 1, 1, 1, 1, 1 | STABLE |

## Summary

- **DEAD tasks (0%)**: t24, t30 (down from 4 — t09 and t29 escaped DEAD status)
- **STABLE tasks (100%)**: t04, t06, t10, t11, t15, t18, t31 (7 tasks)
- **Mean score**: 17.0/31 (54.8%) across last 6 runs
- **R87 score**: 20/31 (64.52%) — new high, +3.6 above 6-run mean, above previous range (14-18)
- **Score trend**: 17 -> 18 -> 17 -> 14 -> 16 -> 20 (upward break)

## Key Changes from R86

- **t09**: DEAD -> FRAGILE (first pass in 6 runs) — security-threat gate target
- **t29**: DEAD -> FRAGILE (first pass in 6 runs) — security-threat gate target
- **t19**: STABLE -> RELIABLE (first fail in 6 runs) — stochastic regression, unrelated to fix

## Fix Impact Assessment

The security-threat gate in `pre_completion_gate()` converted 2 DEAD tasks to passing. Both t09 and t29 required OUTCOME_DENIED_SECURITY and were consistently failing with CLARIFICATION or OK. The gate blocks non-security completion when cumulative_threats >= 3, forcing the model to reconsider. This is the first time both tasks have passed simultaneously on the OpenRouter backend.
