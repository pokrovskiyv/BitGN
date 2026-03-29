# Part 1: Baseline & Foundation (Phase 0 — Mar 29)

> **Plan overview:** [`00-plan-overview.md`](00-plan-overview.md) | **Next:** [`02-plan-architecture.md`](02-plan-architecture.md)
>
> **Reference docs:** [Meta-Model Spec](../specs/2026-03-29-pcdred-meta-model-design.md) | [SoTA Analysis](../../sota-analysis.md) | [Agent Team](../../../agents/)

---

## Task 0.1: Capture Baseline Scores

**Files:**
- Read: `pac1-py/main.py`, `pac1-py/agent.py`
- Create: `docs/eval/run-2026-03-29-baseline.md`

- [ ] **Step 1: Run the full benchmark on current code**

```bash
cd pac1-py && make run 2>&1 | tee /tmp/baseline-run.log
```

Capture the output. Record per-task scores, total score, step counts.

- [ ] **Step 2: Write baseline report**

Create `docs/eval/run-2026-03-29-baseline.md` using the Evaluator agent output format (see `agents/evaluator.md`):
- Per-task scores table
- Aggregate score
- Environment (MODEL_ID, LLM_BACKEND, BENCHMARK_ID)

This is the number we measure all improvements against.

- [ ] **Step 3: Commit baseline**

```bash
git add docs/eval/run-2026-03-29-baseline.md
git commit -m "docs: capture baseline benchmark scores"
```

---

## Task 0.2: Create Agent Team Definitions

**Implements:** Meta-Model Section 3 (Agent Team) — five specialized Claude Code subagents for the development-time PCDRED loop.

**Files:**
- Create: `agents/analyst.md`, `agents/architect.md`, `agents/redteam.md`, `agents/optimizer.md`, `agents/evaluator.md`

> **NOTE:** Already completed. The 5 agent definitions are in `agents/`.

- [ ] **Step 1: Verify all 5 agent files exist and are complete**

```bash
ls agents/
```

Expected: `analyst.md  architect.md  evaluator.md  optimizer.md  redteam.md`

- [ ] **Step 2: Commit Agent Team**

```bash
git add agents/
git commit -m "feat: add Agent Team definitions for PCDRED development cycle"
```

---

**Phase 0 exit criteria:** Baseline score captured in `docs/eval/`. All 5 agent definitions in `agents/`.

**Next:** [Part 2 — Architecture](02-plan-architecture.md) (Phase 1: create 4 modules + wire PCDRED pipeline)
