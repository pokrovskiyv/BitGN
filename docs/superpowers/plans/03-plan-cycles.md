# Part 3: Benchmark & Optimization Cycles (Phases 2-3 — Apr 1-8)

> **Plan overview:** [`00-plan-overview.md`](00-plan-overview.md) | **Prev:** [`02-plan-architecture.md`](02-plan-architecture.md) | **Next:** [`04-plan-hardening.md`](04-plan-hardening.md)
>
> **Reference docs:** [Meta-Model Spec](../specs/2026-03-29-pcdred-meta-model-design.md) (Section 3.6 — Iteration Cycle) | [SoTA Analysis](../../sota-analysis.md) (P2 changes) | [Agent Team](../../../agents/)
>
> **Depends on:** Phase 1 complete (all 4 modules created, agent.py refactored — see [Part 2](02-plan-architecture.md))

---

## Phase 2: Benchmark & Validate (Apr 1)

### Task 2.1: Full Benchmark After Architecture

**Files:**
- Create: `docs/eval/run-2026-04-01-post-architecture.md`

- [ ] **Step 1: Run full benchmark**

```bash
cd pac1-py && make run 2>&1 | tee /tmp/post-arch-run.log
```

- [ ] **Step 2: Write evaluation report**

Use the Evaluator agent format (see `agents/evaluator.md`). Compare against baseline from [Part 1, Task 0.1](01-plan-baseline.md).

- [ ] **Step 3: Decision gate**

Apply the decision protocol (from Meta-Model Section 3.6):
- `new_score > old_score` AND zero regressions -> COMMIT
- `new_score > old_score` AND 1 regression -> COMMIT + investigate
- `new_score == old_score` -> OK (architecture is neutral, improvements come from P0)
- `new_score < old_score` -> INVESTIGATE AND FIX before proceeding

- [ ] **Step 4: Commit report**

```bash
git add docs/eval/
git commit -m "docs: evaluation report post-architecture refactor"
```

---

### Task 2.2: First PCDRED Iteration Cycle

**Implements:** Meta-Model Section 3.6 (Iteration Cycle) — steps 1-9 of the development-time PCDRED loop.
**Agent Team reference:** `agents/*.md` — each agent has its own trigger, input/output format, and constraints.

Run the first complete development-time PCDRED cycle using the Agent Team:

- [ ] **Step 1: Dispatch Analyst** (`agents/analyst.md`) — read benchmark results, produce failure report to `docs/analysis/`
- [ ] **Step 2: Dispatch Architect** (`agents/architect.md`) — fix highest-priority failure from report
- [ ] **Step 3: Dispatch Red Team** (`agents/redteam.md`, parallel) — attack the Architect's fix, write to `docs/redteam/`
- [ ] **Step 4: Dispatch Evaluator** (`agents/evaluator.md`) — re-run benchmark, measure impact, write to `docs/eval/`
- [ ] **Step 5: Decision gate** — COMMIT if improved, REVERT if regressed

This validates the full Agent Team workflow.

- [ ] **Step 6: Commit cycle results**

```bash
git add docs/
git commit -m "docs: first PCDRED iteration cycle results"
```

---

## Phase 3: Optimization Cycles (Apr 2-8)

### Task 3.1: Daily PCDRED Rhythm

**Implements:** Meta-Model Section 3.6 (Iteration Cycle), Section 2.1 (Development-Time PCDRED)

Run 2-4 PCDRED cycles per day. Each cycle follows Meta-Model steps 1-9:

1. **EVALUATOR** (`agents/evaluator.md`) runs benchmark -> scores
2. **ANALYST** (`agents/analyst.md`) reads scores -> failure report in `docs/analysis/`
3. **ARCHITECT** (`agents/architect.md`) designs fix -> code changes to `pac1-py/`
4. **RED TEAM** (`agents/redteam.md`) attacks the fix (parallel with Evaluator) -> `docs/redteam/`
5. **ARCHITECT** patches Red Team gaps -> more changes
6. **EVALUATOR** re-runs benchmark -> new scores
7. **OPTIMIZER** (`agents/optimizer.md`) profiles execution (parallel) -> `docs/optimization/`
8. **ARCHITECT** applies tuning -> final changes
9. **EVALUATOR** confirms -> commit or revert

**Parallel execution**: After Architect produces a fix, dispatch Evaluator (benchmark in worktree), Red Team (attack analysis), and Optimizer (profile previous run) simultaneously.

**Decision protocol per cycle** (from Meta-Model Section 3.6):
- `new > old` AND zero regressions -> COMMIT
- `new > old` AND 1 regression -> COMMIT + investigate
- `new == old` -> SKIP
- `new < old` -> REVERT

---

### Task 3.2: P2 Implementation (interleaved with cycles)

**Implements:** SoTA P2.1-P2.4 from `docs/sota-analysis.md` Section 2, driven by Analyst failure reports.

Implement P2 changes as they become relevant based on Analyst reports:

- [ ] **P2.1: Constraint extraction** — parse task into structured constraint list, verify each via tool call before submission. Add to `pac1-py/verify.py`.
  - **Research basis:** Chain-of-Verification (arXiv:2309.11495)

- [ ] **P2.2: Tree-diff side-effect check** — capture tree output before/after task, diff for unintended changes. Add to `pac1-py/verify.py`.
  - **Research basis:** SWE-bench verification patterns

- [ ] **P2.3: Cross-run reflections** — after failed tasks, generate verbal reflection and store in `docs/analysis/reflections/`. Inject relevant reflections into system prompt on next run. Add reflection storage to `pac1-py/main.py`, retrieval to `pac1-py/strategy.py`.
  - **Research basis:** Reflexion (arXiv:2303.11366): verbal reinforcement learning

- [ ] **P2.4: Few-shot examples** — add 2-3 solved example tasks per category to prompt addons in `pac1-py/strategy.py`.
  - **Research basis:** KATE (arXiv:2101.06804): kNN-based example selection

Each P2 change follows the cycle: implement -> benchmark -> compare -> commit/revert.

---

**Phase 2-3 exit criteria:** Full benchmark passed. First PCDRED cycle completed. Score >= baseline. 2-4 cycles running per day. Score trending upward. P2 changes integrated as needed.

**Next:** [Part 4 — Hardening & Lock](04-plan-hardening.md) (Phases 4-5: Red Team marathon, regression, freeze, tag)
