# Run Historian Report: 2026-04-03-12

## Run History Status
- Total records: 85
- Latest: R85 — 2026-04-03T08:29 — OpenRouter qwen/qwen3.6-plus:free — 14/31 (45.2%)
- R85 included UNSUPPORTED gate fix (reverted in 56b24e0)
- No duplicate timestamps. No spurious entries.

## OpenRouter Win Rates (Last 6 Runs: R80-R85)

| Run | Score | Notes |
|-----|-------|-------|
| R80 | 22/31 (71%) | OpenRouter high-water mark |
| R81 | 19/31 (61%) | Stochastic dip |
| R82 | 17/31 (55%) | Stochastic dip |
| R83 | 18/31 (58%) | Baseline |
| R84 | 17/31 (55%) | HIGH-risk gate re-applied |
| R85 | 14/31 (45%) | UNSUPPORTED gate — REGRESSED, reverted |

Mean: 17.8/31 (57.5%). Range: 14-22. R85 is a new low — 3 pts below prior floor.

### STABLE (100% — 8 tasks)
t04, t06, t10, t11, t15, t17, t19, t31

### DEAD (0% — 4 tasks)
| Task | Failure Pattern |
|------|-----------------|
| t07 | Model can't detect threat (CLARIFICATION/OK instead of SECURITY) |
| t24 | Missing outbox writes or CLARIFICATION |
| t29 | DENIED_SECURITY or CLARIFICATION instead of OK |
| t30 | Wrong computation or CLARIFICATION |

### NOTABLE: t05 BROKE (83% → first failure)
t05 was STABLE at 100% across R80-R84 (5 runs). R85 is its first failure: expected UNSUPPORTED/CLARIFICATION, got OK. The UNSUPPORTED gate likely redirected a correct UNSUPPORTED to incorrect OK. Fix reverted — expect t05 to recover.

### FLAKY (ascending win rate)
| Task | Rate | R80-R85 |
|------|------|---------|
| t01 | 17% | L L W L L L |
| t09 | 17% | W L L L L L |
| t12 | 17% | W L L L L L |
| t16 | 33% | W W L L L L |
| t23 | 33% | L W L L W L |
| t25 | 33% | W L L L L W |
| t28 | 33% | L L L W L W |
| t03 | 50% | W L W W L L |
| t08 | 50% | W W W L L L |
| t27 | 50% | L L W W W L |
| t02 | 67% | W W L L W W |
| t13 | 67% | L W W W L W |
| t14 | 67% | W W L W W L |
| t20 | 67% | W W W W L L |
| t22 | 67% | W W L W W L |
| t26 | 67% | W W W L W L |
| t05 | 83% | W W W W W L |
| t18 | 83% | W L W W W W |
| t21 | 83% | W W L W W W |

## Key Insight: UNSUPPORTED Source Mismatch
The UNSUPPORTED overuse pattern (t12, t16) was assumed to come from model-initiated completions, but R85 shows the gate didn't help these tasks. The UNSUPPORTED likely originates from `_fallback_outcome()` during budget exhaustion — a path the gate cannot intercept. Future fixes should target `_fallback_outcome()` in verify.py, not `pre_completion_gate()`.

## DATA_GAP: NO
R85 recorded correctly. 85 total records.
