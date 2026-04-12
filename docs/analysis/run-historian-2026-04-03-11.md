# Run Historian Report: 2026-04-03-11

## Run History Status
- Total records: 84
- Latest: R84 -- 2026-04-03T07:58 -- OpenRouter qwen/qwen3.6-plus:free -- 17/31 (54.84%)
- R84 includes HIGH-risk gate re-application (commit a495a6e)
- No duplicate timestamps. No spurious entries.

## OpenRouter Win Rates (Last 5 Runs: R80-R84)

| Run | Score | Notes |
|-----|-------|-------|
| R80 | 22/31 (71%) | OpenRouter high-water mark |
| R81 | 19/31 (61%) | Stochastic dip |
| R82 | 17/31 (55%) | Stochastic dip (pre-fix) |
| R83 | 18/31 (58%) | Baseline for this cycle |
| R84 | 17/31 (55%) | HIGH-risk gate applied |

Mean: 18.6/31 (60.0%). Range: 17-22. Variance band: +/-2.5 tasks.

### STABLE (100% -- 9 tasks)
t04, t05, t06, t10, t11, t15, t17, t19, t31

### DEAD (0% -- 4 tasks)
| Task | Failure Pattern |
|------|-----------------|
| t07 | CLARIFICATION instead of DENIED_SECURITY (model can't detect threat) |
| t24 | Missing outbox writes / DENIED_SECURITY over-rejection |
| t29 | CLARIFICATION instead of OK |
| t30 | Wrong computation / CLARIFICATION |

### FLAKY (1-99% -- 18 tasks, ascending)
| Task | Rate | R80 R81 R82 R83 R84 |
|------|------|----------------------|
| t01 | 20% | L L W L L |
| t09 | 20% | W L L L L |
| t12 | 20% | W L L L L |
| t25 | 20% | W L L L L |
| t28 | 20% | L L L W L |
| t16 | 40% | W W L L L |
| t23 | 40% | L W L L W |
| t02 | 60% | W W L L W |
| t03 | 60% | W L W W L |
| t08 | 60% | W W W L L |
| t13 | 60% | L W W W L |
| t27 | 60% | L L W W W |
| t14 | 80% | W W L W W |
| t18 | 80% | W L W W W |
| t20 | 80% | W W W W L |
| t21 | 80% | W W L W W |
| t22 | 80% | W W L W W |
| t26 | 80% | W W W L W |

## Cross-Backend Comparison

The HIGH-risk gate fix was validated on **Nebius** (R72=23/31, t07 0→1, t29 0→1). On OpenRouter:
- t07 is DEAD (0%) regardless of the fix — the free-tier model can't detect threats
- t29 is DEAD (0%) regardless — same issue
- The fix's `continue` only fires on HIGH-risk paths; regressed tasks (t03, t13, t20) don't involve HIGH-risk ops

The fix has **no measurable effect** (positive or negative) on OpenRouter. R82 (pre-fix) was also 17/31. Regressions are pure model variance.

## DATA_GAP: NO
R84 recorded. 270 calls, $0.00 cost (free tier). No spurious or duplicate entries.
