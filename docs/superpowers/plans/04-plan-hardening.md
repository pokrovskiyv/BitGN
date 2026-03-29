# Part 4: Hardening & Lock (Phases 4-5 — Apr 9-10)

> **Plan overview:** [`00-plan-overview.md`](00-plan-overview.md) | **Prev:** [`03-plan-cycles.md`](03-plan-cycles.md)
>
> **Reference docs:** [Meta-Model Spec](../specs/2026-03-29-pcdred-meta-model-design.md) (Section 3.3 — Red Team, Section 6 — Timeline) | [SoTA Analysis](../../sota-analysis.md) (Section 3 — attack categories) | [Agent Team](../../../agents/)
>
> **Depends on:** Phase 3 complete (score trending upward, P2 changes integrated — see [Part 3](03-plan-cycles.md))

---

## Phase 4: Hardening (Apr 9-10)

### Task 4.1: Red Team Marathon

**Implements:** Meta-Model Section 3.3 (Red Team responsibilities), SoTA analysis Section 3 (10 new attack categories)
**Research basis:** OWASP LLM Top 10 v2025, AgentDojo (arXiv:2406.13352), PyRIT/Garak attack methodologies

- [ ] **Step 1: Dispatch Red Team with full 15-category attack battery**

Test all attack categories from `docs/sota-analysis.md` Section 3. Generate 3+ attacks per category = 45+ total attack scenarios. Use `agents/redteam.md` agent definition.

Attack categories to cover (from SoTA analysis):

| # | Category | Min Attacks |
|---|----------|------------|
| 1 | Direct override | 3 |
| 2 | Embedded in data | 3 |
| 3 | Subtle misdirection | 3 |
| 4 | Conflicting constraints | 2 |
| 5 | Social engineering | 3 |
| 6 | Encoding tricks | 3 |
| 7 | History poisoning | 3 |
| 8 | Auto-init poisoning | 2 |
| 9 | Tool output format exploit | 2 |
| 10 | Conditional/sleeper | 2 |
| 11 | Write-then-read self-poison | 2 |
| 12 | Fragmented payload | 2 |
| 13 | Few-shot poisoning | 2 |
| 14 | Hierarchy spoofing | 3 |
| 15 | Error path manipulation | 2 |

Write results to `docs/redteam/attack-battery-2026-04-09.md`.

- [ ] **Step 2: Fix every BYPASSES result**

For each attack that bypasses defenses, dispatch Architect (`agents/architect.md`) to implement a fix. Priority: attacks that would cost the most points in competition.

- [ ] **Step 3: Re-test fixed attacks**

Verify each fix actually blocks the attack without introducing false positives on legitimate tasks.

---

### Task 4.2: Regression Suite

- [ ] **Step 1: Re-run benchmark on ALL tasks**

```bash
cd pac1-py && make run 2>&1 | tee /tmp/regression-run.log
```

Verify no regressions from the full development cycle. Compare against all previous evaluation reports in `docs/eval/`.

- [ ] **Step 2: Run benchmark 3 times**

```bash
cd pac1-py && for i in 1 2 3; do echo "=== Run $i ===" && make run; done 2>&1 | tee /tmp/consistency-run.log
```

Check score consistency across runs. Variance > 5% on any task indicates non-determinism that needs investigation.

---

### Task 4.3: Edge Case Hunting

Test with edge cases (from Meta-Model Section 9 — Risk Factors):

- [ ] Empty files (0 bytes)
- [ ] Files with only whitespace
- [ ] Unicode content (CJK, emoji, RTL text)
- [ ] Deep directory nesting (5+ levels)
- [ ] Very long file content (10K+ lines)
- [ ] Files with special characters in names

For each edge case that causes a failure, dispatch Architect to fix.

---

### Task 4.4: Prompt Freeze

**Implements:** Meta-Model Section 6, Phase 3 (Hardening) — "No new features. Only fixes and hardening."

- [ ] **Step 1: Lock system prompt versions**

No more prompt changes after this point. Copy final prompts to `docs/final-prompts.md` for reference:

```bash
cd pac1-py && uv run python -c "
from classify import TaskClassification
from strategy import decide_strategy
for tt in ['crud', 'search', 'analysis', 'multi_step', 'security_test']:
    c = TaskClassification(tt, 10, 'none', False, False)
    s = decide_strategy(c)
    print(f'=== {tt} ({len(s.system_prompt)} chars) ===')
    print(s.system_prompt[:200] + '...')
    print()
" > ../docs/final-prompts.md
```

- [ ] **Step 2: Lock defend.py patterns**

No more pattern changes. Document final pattern count and coverage:

```bash
cd pac1-py && uv run python -c "
import defend
print(f'Total compiled patterns: {len(defend._COMPILED)}')
cats = {}
for cat, _ in defend._COMPILED:
    cats[cat] = cats.get(cat, 0) + 1
for cat, count in sorted(cats.items()):
    print(f'  {cat}: {count} patterns')
"
```

---

## Phase 5: Lock (Apr 10)

### Task 5.1: Final Verification

**Implements:** Meta-Model Section 6, Phase 4 (Lock)

- [ ] **Step 1: Run full benchmark 3 times**

```bash
cd pac1-py && for i in 1 2 3; do echo "=== Run $i ===" && make run; done 2>&1 | tee /tmp/final-run.log
```

Verify score consistency across all 3 runs.

- [ ] **Step 2: Verify environment**

```bash
echo "MODEL_ID=${MODEL_ID:-claude-haiku-4-5}"
echo "LLM_BACKEND=${LLM_BACKEND:-cli}"
echo "BENCHMARK_HOST=${BENCHMARK_HOST:-https://api.bitgn.com}"
echo "BENCHMARK_ID=${BENCHMARK_ID:-bitgn/pac1-dev}"
```

- [ ] **Step 3: Final Red Team pass**

Quick smoke test: dispatch Red Team (`agents/redteam.md`) with 5 highest-risk attack scenarios only. All must be BLOCKED.

- [ ] **Step 4: Tag release**

```bash
git tag -a v1.0-competition -m "BitGN PAC competition release"
```

- [ ] **Step 5: Write final evaluation report**

Create `docs/eval/run-2026-04-10-final.md` with:
- Final scores across 3 runs
- Improvement from baseline (compare with `docs/eval/run-2026-03-29-baseline.md` from [Part 1](01-plan-baseline.md))
- Known risks
- Environment configuration
- Summary of all PCDRED cycles completed

---

**Phase 4-5 exit criteria:** 45+ attacks tested, zero BYPASSES. 3 consistent benchmark runs. Prompts and patterns frozen. Environment verified. Tagged `v1.0-competition`.
