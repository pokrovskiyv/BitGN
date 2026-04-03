# Run Historian Report: 2026-04-03-09

## Run History Status
- Total records: 71
- Latest: R71 -- 2026-04-03T03:02 -- Qwen3-235B-Thinking (Nebius) -- 21/31 (67.74%)
- R71 is REGRESSED vs R70 (23/31). Code fix was reverted; R71 runs on same codebase as R70.
- R68: 0/31 -- INVALID (31 calls, all "no answer provided" -- broken agent_loop)
- No duplicate timestamps. No spurious entries from stuck sequential benchmark.

## Win Rates (Last 5 Valid Nebius Runs: R66-R67-R69-R70-R71)

| Run | Score | Notes |
|-----|-------|-------|
| R66 | 22/31 (71%) | Baseline |
| R67 | 18/31 (58%) | Stochastic dip, code reverted |
| R69 | 22/31 (71%) | Post-revert baseline |
| R70 | 23/31 (74%) | All-time Nebius high |
| R71 | 21/31 (68%) | Same codebase as R70, model variance |

Mean: 21.2/31 (68.4%). Range: 18-23. Variance band: +/-2.5 tasks per run.

### STABLE (100% -- 13 tasks)
t02, t04, t05, t06, t09, t11, t12, t13, t15, t20, t22, t27, t31

### DEAD (0% -- 3 tasks)
| Task | Failure Pattern |
|------|-----------------|
| t23 | Wrong email domain in outbox / CLARIFICATION |
| t24 | DENIED_SECURITY or ERR_INTERNAL instead of OK |
| t30 | Wrong computation (expected 820-836 range) |

### FLAKY (1-99% -- 15 tasks, ascending)
| Task | Rate | R66 R67 R69 R70 R71 |
|------|------|----------------------|
| t01 | 20% | L L W L L |
| t16 | 20% | W L L L L |
| t29 | 20% | L L W L L |
| t03 | 60% | L W W W L |
| t07 | 60% | W L W L W |
| t10 | 60% | W W L W L |
| t14 | 60% | W L L W W |
| t17 | 60% | W W L L W |
| t18 | 60% | L L W W W |
| t19 | 60% | L W W W L |
| t21 | 60% | L L W W W |
| t25 | 60% | W L L W W |
| t26 | 60% | W L L W W |
| t08 | 80% | W W W W L |
| t28 | 80% | W L W W W |

## Delta vs Previous Report (R66-70 window)

- Stable: 8 -> 13 (+5). Promoted: t02, t05, t09, t12, t13, t20, t27 (were 80% flaky).
- Dead: 3 -> 3 (unchanged: t23, t24, t30).
- Flaky: 20 -> 15 (-5). Window shift dropped old failures; 7 tasks graduated to stable.
- t08 regressed from stable to 80% flaky (lost in R71).

## R71 Regression Analysis

R71 lost 2 tasks vs R70 on identical code. New failures unique to R71:
- t03: failed thread document write (was 60% flaky)
- t08: CLARIFICATION instead of OK (was 100% stable -- first failure in 5 runs)
- t10: missing file write (was 60% flaky)
- t19: CLARIFICATION instead of OK (was 60% flaky)

This is pure model variance, not a code regression.

## DATA_GAP: NO
R71 recorded. 216 calls, $0.39 cost. No spurious or duplicate entries.
