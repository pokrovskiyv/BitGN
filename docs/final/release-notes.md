# BitGN PAC Finals — Release Notes (DRAFT, pre-soak)

**Created:** 2026-04-08
**Competition:** 2026-04-11
**Status:** PRE-SOAK DRAFT — finalize after the user-commanded validation run

---

## Final Profile

| Setting | Value | Source |
|---|---|---|
| `RUN_PROFILE` | `final` | `pac1-py/.env.final.example` |
| `LLM_BACKEND` | `api` (Anthropic) | profile default in `settings.py` |
| `MODEL_ID` (primary) | `claude-sonnet-4-6` | profile default in `settings.py` |
| `VERIFIER_MODEL` | `claude-haiku-4-5` | profile default in `settings.py` |
| `VERIFIER_POLICY` | `adaptive` | exported by Makefile target |
| `PARALLEL` | `4` | exported by Makefile target |
| `BENCHMARK_HOST` | `https://api.bitgn.com` | `.env.final.example` |
| `BENCHMARK_ID` | `bitgn/pac1-dev` | `.env.final.example` |
| `ANTHROPIC_API_KEY` | (operator must set) | `.env.final` |

Activation: `cp pac1-py/.env.final.example pac1-py/.env.final`, add `ANTHROPIC_API_KEY`, then `make run-final` from `pac1-py/`.

## Commit Inventory

| SHA | Subject | Role |
|---|---|---|
| `4acbe7e` | feat: final-profile scaffold | Rollback baseline. Sonnet+Haiku plumbing, settings.py, prompt split, per-task harness client, verifier accounting, runtime tool surface. |
| `182e30b` | fix: P0.3+P0.1 evidence-based fallback + security_posture-driven threat threshold | Removes the last task_type branch in `_fallback_outcome`. `_threat_threshold(security_posture)` helper now drives both `_fallback_outcome` and `pre_completion_gate` (paranoid=1, hardened=2, standard=3). |
| (TBD) | finals-ready tag | Applied after successful soak run + commander approval. |

## What changed since last benchmark commit (`8071f87`)

- Sonnet 4.6 + Haiku 4.5 architecture replaces Qwen3 (the prior 92.5% peak was Qwen3 on the OpenRouter free tier with high variance).
- Verifier triggers generalized from task-type-specific to evidence-based (any non-OK, any threat, any delete, plus 3 task-type fallbacks for safety net).
- Prompt static/dynamic split — task-derived hints (target, runtime tool surface, HINT env) are no longer in the cached static prefix. This is required for Anthropic prompt caching to work cross-task.
- Grounding refs auto-merged from `WriteTracker._consulted` (captures list/find/search results) — addresses the chronic t23/t40 "missing required reference" failures structurally rather than per-task.
- Search auto-retry per token when full pattern returns 0 matches (in `domain_fs.expand_search_result`).
- Budget-exhaustion fallback no longer assumes communication tasks → UNSUPPORTED. Decision is now: writes/deletes → OK, reads → CLARIFICATION, nothing → CLARIFICATION. Plus paranoid posture lowers the cumulative threat threshold from 3 → 1.
- Added 3 new agent files (`commander`, `generalization-analyst`, `bench-ops`) backing the runbook roles.

## Expected Score Range (honest, pre-soak)

The 92.5% practice peak was a single OUTLIER on Qwen3 + 40-task practice set. Realistic expectations on Sonnet+Haiku are unknown until the validation run. Baseline projections from the analysis report:

- **Pessimistic** (Sonnet+Haiku worse than Qwen3 on PAC due to model temperament differences): 65–75%
- **Median** (Sonnet+Haiku comparable, anti-overfit fixes neutral on practice): 75–85%
- **Optimistic** (Sonnet+Haiku stronger reasoning + Haiku gating prevents over-denial): 85–93%

On 100 unknown finals tasks, the realistic projection by failure-family weighting is **57–70%**, with the gap explained by:
- 37/40 practice tasks classified FLAKY (only 3 STABLE)
- Practice peak inflated by task-type-specific fixes (now removed in `_fallback_outcome`)
- Different session seeds in the finals harness

The single validation soak run will replace these projections with measured numbers.

## Known Risks (carry into the validation run)

| # | Risk | Mitigation |
|---|------|-----------|
| R1 | Sonnet generator weaker on PAC than Qwen3 (memory note: "Haiku 84% > Sonnet 76%" on PAC). | Flip `PRIMARY_MODEL_ID` env back to Qwen3 — no code change. Backend stays `api` if Haiku verifier is fine; otherwise revert to `nebius`. |
| R2 | Haiku verifier too restrictive (overrides Sonnet OK→DENIED on >15% of completions). | Track verifier agreement rate in run record. Add `VERIFIER_POLICY=conservative` if exceeded. |
| R3 | Anthropic prompt caching cold (no `cache_read_input_tokens` until run 2). | Check `api_usage` after the validation run; cache should be hot for repeated same-type prompts. |
| R4 | API cost spike per run. | `api_usage.cost_usd` should be <$10. Investigate if higher. |
| R5 | Per-task `HarnessServiceClientSync` instability under PARALLEL=4. | Fallback `PARALLEL=2` then `PARALLEL=1` (sequential). |
| R6 | The two retained `pre_completion_gate` task_type branches behave differently with Sonnet's reasoning style. | Watch the validation run for: (a) over-rejection of legitimate inbox completions, (b) over-acceptance of incomplete inbox completions. Diagnostic: failure family distribution from generalization-analyst. |

## Validation Procedure (single user-commanded run)

1. Operator copies `pac1-py/.env.final.example` to `pac1-py/.env.final`, adds `ANTHROPIC_API_KEY`.
2. Operator quick-test: `cd pac1-py && make task-final TASKS='t35 t38 t39'` — must return 3/3 (the 3 STABLE tasks).
3. **Wait for user command** to run the full benchmark.
4. On user command: `make run-final PARALLEL=4` (sequential within parallel pool).
5. After run: dispatch `bench-ops` for health check (HC1–HC7).
6. After PASS: dispatch `generalization-analyst` for family-level distribution.
7. `commander` reviews and decides ship / iterate / revert.

## Fallback Plan (competition day)

In failure escalation order:
1. `make resume-final` — preserves state across transient failures.
2. `make run-final PARALLEL=2` — reduces API pressure.
3. `make run-final PARALLEL=1` — sequential, slowest but safest.
4. Emergency revert: `git checkout 4acbe7e` (Codex scaffold without P0 fixes) and re-run.
5. Last-resort revert: flip `PRIMARY_LLM_BACKEND=nebius PRIMARY_MODEL_ID=Qwen/Qwen3-235B-A22B-Thinking-2507` — code stays on `main`, only env changes.

## Branch Freeze (finalize after soak)

After the validation run passes:
- Lock `.env.final` content into `.env.final.lock` (read-only reference).
- `git tag finals-ready-<SHA>` on the validated commit.
- Replace this DRAFT marker with FINAL.
- No more commits to `main` until 2026-04-12.
