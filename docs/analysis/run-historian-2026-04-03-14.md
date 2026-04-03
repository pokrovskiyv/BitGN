# Run Historian -- 2026-04-03-14

## Data Validation

- **Total entries**: 86 (confirmed)
- **Latest timestamp**: 2026-04-03T08:57:59+00:00
- **Model**: qwen/qwen3.6-plus:free (openrouter)
- **Latest score**: 51.61% (16/31)

## Win Rate Table (last 5 runs)

Runs 82-86 (2026-04-03 07:19 through 08:57), all on qwen/qwen3.6-plus:free via openrouter.

| Task | Win Rate | Scores (R82-R86) | Status |
|------|----------|-------------------|--------|
| t09 | 0% | 0, 0, 0, 0, 0 | DEAD |
| t24 | 0% | 0, 0, 0, 0, 0 | DEAD |
| t29 | 0% | 0, 0, 0, 0, 0 | DEAD |
| t30 | 0% | 0, 0, 0, 0, 0 | DEAD |
| t01 | 20% | 1, 0, 0, 0, 0 | FRAGILE |
| t07 | 20% | 0, 0, 0, 0, 1 | FRAGILE |
| t08 | 20% | 1, 0, 0, 0, 0 | FRAGILE |
| t12 | 20% | 0, 0, 0, 0, 1 | FRAGILE |
| t16 | 20% | 0.6, 0, 0, 0, 0 | FRAGILE |
| t23 | 20% | 0, 0, 1, 0, 0 | FRAGILE |
| t25 | 20% | 0, 0, 0, 1, 0 | FRAGILE |
| t14 | 40% | 0, 1, 1, 0, 0 | UNSTABLE |
| t20 | 40% | 1, 1, 0, 0, 0 | UNSTABLE |
| t22 | 40% | 0, 1, 1, 0, 0 | UNSTABLE |
| t28 | 40% | 0, 1, 0, 1, 0 | UNSTABLE |
| t02 | 60% | 0, 0, 1, 1, 1 | VARIABLE |
| t03 | 60% | 1, 1, 0, 0, 1 | VARIABLE |
| t21 | 60% | 0, 1, 1, 1, 0 | VARIABLE |
| t26 | 60% | 1, 0, 1, 0, 1 | VARIABLE |
| t05 | 80% | 1, 1, 1, 0, 1 | RELIABLE |
| t13 | 80% | 1, 1, 0, 1, 1 | RELIABLE |
| t17 | 80% | 1, 1, 1, 1, 0 | RELIABLE |
| t27 | 80% | 1, 1, 1, 0, 1 | RELIABLE |
| t04 | 100% | 1, 1, 1, 1, 1 | STABLE |
| t06 | 100% | 1, 1, 1, 1, 1 | STABLE |
| t10 | 100% | 1, 1, 1, 1, 1 | STABLE |
| t11 | 100% | 1, 1, 1, 1, 1 | STABLE |
| t15 | 100% | 1, 1, 1, 1, 1 | STABLE |
| t18 | 100% | 1, 1, 1, 1, 1 | STABLE |
| t19 | 100% | 1, 1, 1, 1, 1 | STABLE |
| t31 | 100% | 1, 1, 1, 1, 1 | STABLE |

## Summary

- **DEAD tasks (0%)**: t09, t24, t29, t30
- **STABLE tasks (100%)**: t04, t06, t10, t11, t15, t18, t19, t31
- **Mean score**: 16.4/31 (52.9%) across last 5 runs
- **Score trend**: 54.84 -> 58.06 -> 54.84 -> 45.16 -> 51.61 (declining, high variance)
- **Key failure patterns**: t09/t29 security detection failures; t24 missing outbox writes; t30 wrong answer on analysis task
