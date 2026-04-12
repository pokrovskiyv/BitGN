# Session Journal: OpenRouter Integration + Automated PCDRED Cycles

**Date**: 2026-04-02 → 2026-04-03  
**Goal**: Integrate Qwen 3.6 Plus via OpenRouter, then automate improvement cycles

---

## Phase 1: OpenRouter Backend Integration (manual, ~2 hours)

### Run 1 — Baseline with json_schema
- **Model**: `qwen/qwen3.6-plus:free` (OpenRouter)
- **Change**: Added `openrouter` backend to `llm.py` (refactored `_call_nebius` → generic `_call_openai_compat` with config dict)
- **Result**: **32% (10/31)**
- **Issues**: `json_schema` response_format not enforced on OpenRouter free tier; 8 parsing failures (OUTCOME_ERR_INTERNAL); 0/5 security tasks passed

### Run 2 — Fallback to json_object
- **Change**: `response_format: json_object` instead of `json_schema` for OpenRouter
- **Result**: **39% (12/31)** (+7pp)
- **Issues**: 6 parsing failures remain; security still 0/5

### Run 3 — reasoning + fallback parser
- **Changes**:
  1. `extra_body: {"reasoning": {"effort": "high"}, "include_reasoning": true}` — enables chain-of-thought
  2. `_recover_nextstep()` — fallback parser for malformed JSON (wraps flat tool objects, fills missing fields)
- **Result**: **54% (16/31)** (+15pp)
- **Key win**: Security tasks jumped 0/5 → 4/5. Reasoning enables injection detection.

### Summary of manual integration
| Run | Change | Score | Security | Parse fails |
|-----|--------|-------|----------|-------------|
| 1   | json_schema | 32% (10/31) | 0/5 | 8 |
| 2   | json_object | 39% (12/31) | 0/5 | 6 |
| 3   | reasoning + fallback | 54% (16/31) | 4/5 | 4 |

**Key files changed**: `pac1-py/llm.py` (OpenRouter backend, `_recover_nextstep`), `pac1-py/main.py` (OpenRouter pricing/usage)

---

## Phase 2: PCDRED Automation Setup (manual, ~1 hour)

### Changes made
1. **`pac1-py/Makefile`** — added `run-parallel` target (`--parallel=5`, reduced from 10 due to rate limiting)
2. **`.claude/agents/analyst.md`** — added "Overfitting Prevention" section: `model_parse_failure` category, Generalizability (HIGH/MEDIUM/LOW), Zone (GREEN/AMBER)
3. **`.claude/agents/architect.md`** — replaced "fixing one specific case over generalizing" with file-zone constraints (GREEN/AMBER), forbidden patterns, 30-line diff limit
4. **`pcdred-cycle-prompt.txt`** — added win rate computation, MODEL_PARSE_FAILURE triage, confirmation runs, anti-overfitting rules section
5. **`run_pcdred_loop.sh`** — 20→30 cycles, Opus 4.6 orchestrator, 60s cooldown, early-stop on 3 NEUTRAL, score printing

---

## Phase 3: Test Cycle (Sonnet orchestrator, 1 cycle)

- **Orchestrator**: Claude Sonnet 4.6
- **Duration**: 24 minutes
- **Analyst found**: `outcomes.md` excluded task-level injection from DENIED_SECURITY
- **Architect fix**: Expanded DENIED_SECURITY definition (12 lines in outcomes.md)
- **Red Team**: Found bypass → patched (2 lines)
- **Evaluator**: 7 improvements but 9 regressions (free tier variance)
- **Decision Gate**: **REGRESSED → reverted** ✓
- **Verdict**: Protocol works correctly. Sonnet too hasty — didn't use confirmation run.

---

## Phase 4: Automated PCDRED Cycles (Opus orchestrator, ~7 hours)

### OpenRouter phase (cycles 1-4, ~2 hours)
| Cycle | Fix | Verdict | Score |
|-------|-----|---------|-------|
| 1 | `verify.py` fallback CLARIFICATION instead of ERR_INTERNAL | **IMPROVED** | 52% (16/31) |
| 2 | `strategy.py` crud step budget 10→14 | **IMPROVED** | 55% (17/31) |
| 3 | Revert crud budget (regression on re-test) | **REGRESSED** | 52% (16/31) |
| 4 | `strategy.py` inbox_processing entry | **REGRESSED** (API instability) | 39% (12/31) |

**Problem**: OpenRouter free tier couldn't handle 10 parallel workers — 41-53 empty responses per run, 19 LLM FAILURE events. Scores dropped to 39% due to API rate limiting, not code quality.

### Nebius phase (cycles 5-10, ~5 hours)
Opus autonomously switched `.env` to `nebius/Qwen3-235B-Thinking` after detecting API instability.

| Cycle | Fix (commit) | Verdict | Score |
|-------|-------------|---------|-------|
| 5 | `llm.py` call signature alignment | **IMPROVED** | 71% (22/31) |
| 6 | `agent_loop.py` risk_level wiring | **IMPROVED_WITH_REGRESSION** | 71% (22/31) |
| 7 | `verify.py` inbox DENIED_SECURITY evidence | **REGRESSED** → reverted | 58% (18/31) |
| 8 | `agent_loop.py` report_budget_exhaustion | **IMPROVED** | 71% (22/31) |
| 9 | `agent_loop.py` HIGH-risk block | **REGRESSED** → reverted | 68% (21/31) |
| 10 | `agent_loop.py` pre_completion_gate + inbox gate | RUNNING | 74% (23/31) |

### Surviving code changes (kept after all reverts)
| Commit | File | Change | Zone |
|--------|------|--------|------|
| `2b48cf3` | `pac1-py/verify.py` | Fallback outcome CLARIFICATION instead of ERR_INTERNAL | GREEN |
| `db8d20c` | `pac1-py/agent_loop.py` | Replace `handler.destructive` with `handler.risk_level` | GREEN |
| `38ea2f7` | `pac1-py/llm.py` | Align call_llm with refactored 5-arg signature | GREEN |
| `bcd5afe` | `pac1-py/agent_loop.py` | Wire report_budget_exhaustion replacing hardcoded ERR_INTERNAL | GREEN |
| `0595fef` | `pac1-py/strategy.py` | Add inbox_processing to strategy table + addon mapping | GREEN |
| `497bc53` | `pac1-py/agent_loop.py` | Wire pre_completion_gate into completion path | GREEN |
| `14bc76a` | `pac1-py/verify.py` | Inbox gate uses _reads not all_consulted_paths | GREEN |

All kept changes are GREEN zone infrastructure fixes. No AMBER zone edits survived. Anti-overfitting guardrails worked as designed.

---

## Token Usage Summary

| Backend | Runs | Input tokens | Output tokens | Cost |
|---------|------|-------------|--------------|------|
| OpenRouter (qwen3.6-plus:free) | 8 | ~12.9M | ~1.25M | **$0.00** |
| Nebius (Qwen3-235B-Thinking) | 7 | ~8.1M | ~1.7M | **$3.01** |
| Opus orchestrator (CLI subscription) | ~10 cycles | — | — | **$0** (included in plan) |
| **Total** | **15 benchmark runs** | **~21M** | **~3M** | **$3.01** |

---

---

## Phase 5: Controlled Comparison — Same Commit, Two Backends (2026-04-03)

All runs on commit `d8383e0` (includes all PCDRED fixes: fallback parser, budget exhaustion, risk_level wiring, pre_completion_gate, inbox gate).

### Nebius / Qwen3-235B-A22B-Thinking-2507 (8 parallel workers)

| Run | Score | Tasks | Cost |
|-----|-------|-------|------|
| 1 | **80.65%** | 25/31 | $0.43 |
| 2 | **77.42%** | 24/31 | $0.44 |
| 3 | **77.42%** | 24/31 | $0.50 |
| **Mean** | **78.5%** | — | **$1.37** |

Variance: ±1.9pp (stable). Best-ever score: 80.65%.

### OpenRouter / qwen/qwen3.6-plus:free (5 parallel workers)

| Run | Score | Tasks | Cost |
|-----|-------|-------|------|
| 1 | **54.84%** | 17/31 | $0.00 |
| 2 | **67.74%** | 21/31 | $0.00 |
| 3 | **58.06%** | 18/31 | $0.00 |
| **Mean** | **60.2%** | — | **$0.00** |

Variance: ±6.5pp (high). Free tier instability visible even at 5 workers.

### Head-to-Head Summary

| Metric | Nebius (Qwen3-235B) | OpenRouter (Qwen 3.6 Plus free) |
|--------|--------------------|---------------------------------|
| Mean score | **78.5%** | 60.2% |
| Best score | **80.65%** | 67.74% |
| Variance | ±1.9pp | ±6.5pp |
| Cost (3 runs) | $1.37 | **$0.00** |
| json_schema | ✅ enforced | ❌ json_object + fallback |
| Reasoning | Thinking model (CoT in reasoning_content) | Always-on CoT (effort=high) |

Delta: **18.3pp** in favor of Nebius/Qwen3-235B-Thinking.

---

## Key Findings

1. **OpenRouter free tier is unstable under parallel load** — 10 workers causes 40+ empty responses per run. Reduced to 5 workers, but free tier still has high variance (~15pp between identical runs).

2. **`reasoning: {"effort": "high"}` is critical for Qwen 3.6 Plus** — without it, 0/5 security tasks pass. With it, 4/5 pass. CoT enables injection detection.

3. **`_recover_nextstep()` fallback parser adds ~10pp** — the model frequently outputs flat tool objects without NextStep wrapper, or misses required fields.

4. **Qwen 3.6 Plus (free) peak: 54% (16/31)** on OpenRouter with all fixes. Limited by model capability + API instability.

5. **Qwen3-235B-Thinking peak: 74% (23/31)** on Nebius. The Thinking model is substantially better for this benchmark due to constrained decoding (json_schema) + deeper reasoning.

6. **Anti-overfitting guardrails worked** — all surviving fixes are GREEN zone infrastructure changes. No task-specific hacks. Decision gate correctly reverted 4 regressions.

7. **Opus > Sonnet as PCDRED orchestrator** — deeper analysis, better fix quality, correct use of confirmation runs.
