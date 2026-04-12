# Fix Registry

Consolidated DO_NOT_REPEAT from all PCDRED cycles.

| Cycle | Fix | Verdict |
|-------|-----|---------|
| 2026-04-02-20 | outcomes.md boundary expansion | REGRESSED, reverted. DO_NOT_REPEAT. |
| 2026-04-02-21 | verify.py _fallback_outcome ERR_INTERNAL | CLARIFICATION → IMPROVED_WITH_REGRESSION, accepted. |
| 2026-04-02-22 | inbox_processing strategy table only (gap #1) | could not validate, reverted |
| 2026-04-02-22 | crud step budget increase | no improvement |
| 2026-04-02-23 | inbox DENIED_SECURITY evidence challenge | REGRESSED |
| 2026-04-03-00 | inbox_processing strategy table only | REGRESSED (API variance), reverted |
| 2026-04-03-01 | inbox_processing strategy table + addon mapping | REGRESSED (API variance), reverted |
| 2026-04-03-03 | inbox_processing strategy wiring | IMPROVED_WITH_REGRESSION (accepted) |
| 2026-04-03-05 | agent_loop call_llm + risk_level signature fix | IMPROVED_WITH_REGRESSION (accepted) |
| 2026-04-03-08 | wire report_budget_exhaustion | IMPROVED_WITH_REGRESSION (accepted) |
| 2026-04-03-09 | HIGH-risk gate blocking | REGRESSED (reverted), R72 confirmed safe |
| 2026-04-03-12 | UNSUPPORTED overuse gate | REVERTED |
| 2026-04-03-12 | UNSUPPORTED overuse gate (any step count) | REVERTED |
| 2026-04-03-14 | fallback reorder reads > communication UNSUPPORTED | REVERTED |
| 2026-04-03-15 | security-threat gate in pre_completion_gate | IMPROVED_WITH_REGRESSION (accepted) |
| 2026-04-03-16 | count deletes as actions in _fallback_outcome | REVERTED |
| 2026-04-03-17 | _fallback_outcome security threshold 5 | 3 -> REGRESSED |
| 2026-04-03-18 | premature completion gate for complex task types | REGRESSED |
| 2026-04-03-19 | premature UNSUPPORTED gate at step 0-1 | REGRESSED |

## Summary

- **IMPROVED_WITH_REGRESSION (accepted)**: 4
- **REVERTED**: 4
- **REGRESSED**: 3
- **REGRESSED (API variance), reverted**: 2
- **REGRESSED, reverted. DO_NOT_REPEAT.**: 1
- **CLARIFICATION → IMPROVED_WITH_REGRESSION, accepted.**: 1
- **could not validate, reverted**: 1
- **no improvement**: 1
- **REGRESSED (reverted), R72 confirmed safe**: 1
- **3 -> REGRESSED**: 1
