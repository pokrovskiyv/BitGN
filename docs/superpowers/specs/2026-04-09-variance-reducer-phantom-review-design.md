# Variance-Reducer Agent + Phantom-Agent Manual Review

**Date**: 2026-04-09
**Status**: Draft (awaiting user review)
**Depends on**: PCDRED Meta-Model (2026-03-29), Domain Plugin Architecture (2026-03-30)
**Window**: BitGN PAC1 finals push (competition 2026-04-11)

## 1. Problem Statement

Two days before finals. Two overlapping problems:

1. **Unmeasured noise floor.** Last known variance is ~8pp per run (session_2026_04_01_pipeline_audit). Without a measured baseline mean ± confidence interval, any fix delta is indistinguishable from random sampling. Finals decisions are made on vibes instead of evidence.

2. **Unvetted external source.** `https://github.com/vakovalskii/phantom-agent` — a competing BitGN PAC1 agent (~81-83% per their own `docs/optimization-guide.md`, despite README claims of 86-90%). Does it contain any generalization-safe patterns BitGN is missing, or is the effort to evaluate it wasted?

**Goal**: Address both problems without touching core `pac1-py/` logic, respecting `commander.md` anti-overfit rules, inside a 2-day budget.

## 2. Current State

### 2.1 Existing finals team (12 agents in `.claude/agents/`)

| Agent | Role | Reused by this spec? |
|---|---|---|
| analyst | Per-task failure analysis | No (task-instance level) |
| architect | Minimal fix implementation | No (no code changes here) |
| red-team | Attack the defenses | No (optional follow-up) |
| optimizer | Performance profiling | No |
| evaluator | Run benchmark + verdict | **Yes** (downstream from variance-reducer) |
| memory-consolidator | autoDream memory | No (not in session scope) |
| dashboard-updater | Dashboard updates | No |
| run-narrator | Narrative reports | No |
| run-historian | Run history tracking | No |
| **commander** | Anti-overfit gate | **Yes** (gates any phantom-review diff) |
| **generalization-analyst** | Family-level failure clustering | **Yes** (downstream from variance-reducer for interpretation) |
| **bench-ops** | Post-run health checklist | **Yes** (invoked between sweep runs) |

### 2.2 What generalization-analyst already covers

Reading `.claude/agents/generalization-analyst.md`, it already computes:
- Mean of last 3 runs
- Stdev
- Tasks that flipped pass/fail across runs
- Stdev delta from previous

This means a variance-reduction agent must **not duplicate** family interpretation. Its unique value is (a) triggering controlled N runs with identical config, (b) producing a focused variance-only artifact, (c) handing off to generalization-analyst.

### 2.3 What BitGN's defend.py already covers vs phantom-agent

BitGN `pac1-py/defend.py`: 12 threat categories × ~50 regex patterns, Unicode normalization (zero-width, Cyrillic/Greek/Armenian homoglyphs), base64/hex/URL encoding decoders, `wrap_tool_output()` delimiter scheme.

phantom-agent security: literal phrase list in `agent_v2/system_prompt.md`, relying on LLM attention. No pre-scanner. No Unicode normalization. No decoders.

Structural verdict: **BitGN's defend.py is materially more mature** than phantom-agent's security approach.

## 3. Scope & Non-Goals

### In scope
- Create one new development-time agent: `variance-reducer.md`
- Update `docs/scratchpad/README.md` (two lines)
- Conduct ≤60 min manual review of phantom-agent, produce `docs/analysis/phantom-agent-extraction-2026-04-09.md`
- Conditional: if the review finds a generalization-safe pattern that passes commander rules, apply a ≤10 line diff in GREEN zone and invoke `commander.md`

### Out of scope (explicit non-goals to prevent scope creep)
- **No variance-reducer execution** in this session (that's a separate invocation: ~75 min wall time + API budget)
- **No core pac1-py/ changes** except the conditional ≤10 line diff
- **No new LLM backends, task types, or tools**
- **No AMBER zone edits** (`classify.py`, `fragments/inbox_processing.md`, `fragments/communication.md`, `fragments/multi_step.md`, `criteria.py`, `hints.py`)
- **No fix evaluation** (that's `evaluator.md`'s role)
- **No family analysis inside variance-reducer** (that's `generalization-analyst.md`'s role)
- **No commits in this session** — all changes uncommitted, user decides when to commit
- **No writing-plans invocation** — for this scope the spec IS the plan

## 4. Decision Rationale

### ADR-1: Variance measurement over external pattern extraction

**Decision**: Prioritize building a variance-reducer agent over a phantom-agent extractor team.

**Why**: After deep analysis, phantom-agent's extractable value is small (1-2 genuinely useful patterns after filtering). Their defend.py equivalent is architecturally inferior. Their "unresolved cases" are GPT-OSS Harmony-format artifacts not applicable to BitGN's Claude/Qwen backends. Time invested in variance measurement has higher expected value because it changes our confidence in every subsequent decision, not just a narrow threat category.

**Rejected alternative**: A 2-agent extractor pipeline (`phantom-extractor` + `security-porter`). Cost: ~2 hours for agent creation + commander/evaluator cycle. Expected impact: <1pp, below noise floor. Net negative ROI under time pressure.

### ADR-2: Thin orchestrator over full analyst

**Decision**: `variance-reducer` triggers runs and aggregates raw stats only. It hands off interpretation to `generalization-analyst`.

**Why**: `generalization-analyst.md` already computes mean/stdev/flipped-tasks. Building a second analyst duplicates work and risks drift. Separation of concerns: measurement (new) vs interpretation (existing).

**Rejected alternative**: A full variance-analyst with family clustering. Duplication of generalization-analyst, confusing downstream handoff.

### ADR-3: Sequential runs over parallel

**Decision**: `variance-reducer` runs N cycles sequentially.

**Why**: BitGN API quota concerns, verifier cost spike risk, and `run_history.json` write-race prevention. Sequential is safer and deterministic. Trade-off: ~75 min wall time for N=5. Acceptable.

**Rejected alternative**: Parallel runs via `AGENT_CONCURRENCY`. Adds complexity, conflict risk, and doesn't measurably reduce wall time when each run is already parallelized internally via `PARALLEL=4`.

### ADR-4: Manual phantom-review over new extractor agent

**Decision**: The phantom-agent review is done manually in the current session, not via a new agent.

**Why**: One-off task. Agent creation overhead (spec + file + invocation + artifact interpretation) exceeds manual review time (30-60 min). Reusability is low (post-finals we likely won't revisit phantom-agent).

**Rejected alternative**: `phantom-extractor.md` as one of the new Agent Team members. Over-engineered for the task.

### ADR-5: New `variance` scratchpad type over reusing `optimization`

**Decision**: Extend `docs/scratchpad/README.md` to allow `type: variance` and `agent: variance-reducer`.

**Why**: Type drives downstream consumption rules. `type: optimization` implies `optimizer.md` is the producer and bench runtime analysis is the content. Variance reports are structurally different — baseline measurement, not bottleneck identification. Explicit naming prevents confusion.

**Rejected alternative**: `type: optimization` reuse. Semantically misleading; generalization-analyst would need to guess which optimization artifacts are variance reports vs runtime bottlenecks.

## 5. Architecture

```
┌─ MANUAL (this session, ≤60 min) ─────────────────────────────┐
│                                                              │
│  Claude (current session)                                    │
│  ├─ read phantom-agent remaining files                       │
│  │    (security_denial.md, inbox_processing.md)              │
│  ├─ grep BitGN defend.py / fragments / classify.py           │
│  │    for each candidate pattern                             │
│  ├─ apply 6-point gate per candidate                         │
│  └─ write docs/analysis/phantom-agent-extraction-            │
│        2026-04-09.md                                         │
│                                                              │
│  IF a candidate passes all 6 gates:                          │
│  └─ ≤10 line diff in GREEN zone                              │
│    └─ invoke commander.md via Agent tool                     │
│      └─ APPROVE → leave uncommitted for user                 │
│      └─ REJECT → git checkout -- <files>, log reason         │
│                                                              │
└──────────────────────────────────────────────────────────────┘

┌─ NEW AGENT (created but not executed in this session) ──────┐
│                                                              │
│  .claude/agents/variance-reducer.md                          │
│                                                              │
│  Phase 1 — config snapshot                                   │
│    ├─ cat pac1-py/.env.final                                 │
│    ├─ git rev-parse HEAD                                     │
│    └─ capture {model, verifier_model, parallel, benchmark}   │
│                                                              │
│  Phase 2 — execute N runs sequentially                       │
│    for i in 1..N:                                            │
│      ├─ bash: cd pac1-py && make run-final                   │
│      ├─ wait for exit (30 min timeout)                       │
│      ├─ invoke bench-ops.md via Agent tool                   │
│      ├─ switch verdict:                                      │
│      │    PASS          → continue                           │
│      │    RESUME_NEEDED → make resume-final, re-check        │
│      │    INCIDENT      → abort, partial report              │
│      └─ sleep 30s                                            │
│                                                              │
│  Phase 3 — aggregate                                         │
│    ├─ read last N records from docs/run_history.json         │
│    ├─ compute mean, stdev, 95% CI, noise floor = 2×stdev     │
│    ├─ build per-task outcome matrix                          │
│    ├─ classify stable_pass / stable_fail / unstable          │
│    └─ per task_type breakdown                                │
│                                                              │
│  Phase 4 — write scratchpad artifact                         │
│    ├─ path: docs/scratchpad/{run_id}--variance-reducer--     │
│    │        variance.md                                      │
│    └─ YAML frontmatter + tables + handoff note               │
│                                                              │
│  Handoff: user invokes generalization-analyst.md pointing    │
│  at the artifact for family-level interpretation             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 6. Component 1: `variance-reducer.md`

### 6.1 Location
`.claude/agents/variance-reducer.md`

### 6.2 Frontmatter

```yaml
---
description: Thin orchestrator that runs N identical benchmark cycles and produces a structured variance report (baseline mean ± stdev, unstable task list, noise floor). Use to measure true baseline before/during finals window. Does NOT evaluate fixes (use evaluator.md). Does NOT analyze failure families (use generalization-analyst.md). Input: "run variance sweep N=5". Output: scratchpad variance artifact.
---
```

### 6.3 Role

Thin orchestrator. Three responsibilities only:
1. Trigger N identical `make run-final` cycles
2. Coordinate with `bench-ops.md` after each run
3. Aggregate raw stats into a variance artifact

**Not its responsibility**: fix evaluation, family analysis, fix approval, individual task runs, cross-SHA comparison, remediation recommendations.

### 6.4 Workflow

**Phase 1 — Config snapshot**

```
bash: cat pac1-py/.env.final   (do NOT log API keys)
bash: git rev-parse HEAD
capture config_sha = {model, verifier_model, parallel, benchmark_id, git_sha}
```

**Phase 2 — Execute N runs**

```
N_default = 5
N_max = 10
sleep_between = 30s

for i in 1..N:
  bash: cd pac1-py && make run-final
  (timeout: 30 min per run)

  bash: tail -1 docs/run_history.json
  check: new record written, config matches config_sha

  invoke bench-ops.md (via Agent tool)

  match bench-ops_verdict:
    PASS          → continue
    RESUME_NEEDED → bash: cd pac1-py && make resume-final
                    invoke bench-ops.md again
                    if still RESUME_NEEDED → abort
    INCIDENT      → abort, write partial report, exit

  sleep 30s
```

**Phase 3 — Aggregate**

```
records = read last N records of docs/run_history.json
          filter by config_sha = snapshot

scores = [r.score / r.tasks_total for r in records]
mean = Σ scores / N
stdev = sqrt(Σ (s - mean)² / (N - 1))
ci_95 = mean ± t(df=N-1, α=0.025) × stdev / sqrt(N)
noise_floor = 2 × stdev

outcome_matrix = {}
for r in records:
  for task_id, score_detail in r.score_detail.items():
    outcome_matrix[task_id].append(outcome_from(score_detail))

stable_pass = {tid for tid, outs in matrix if all(o == OK for o in outs)}
stable_fail = {tid for tid, outs in matrix if all(o != OK for o in outs)}
unstable = {tid for tid, outs in matrix if len(set(outs)) > 1}
err_internal = {tid for tid, outs in matrix if any(o == OUTCOME_ERR_INTERNAL for o in outs)}

per_type_stats = groupby(task_type) → (mean, stdev, stable_count, unstable_count)

cost_total = Σ r.api_usage.cost_usd
time_total = Σ r.run_duration_sec
```

**Phase 4 — Write scratchpad artifact**

Path: `docs/scratchpad/{run_id}--variance-reducer--variance.md`

### 6.5 Output artifact schema

```yaml
---
agent: variance-reducer
type: variance
run_id: 2026-04-09-14
status: final
config:
  model: claude-sonnet-4-6
  verifier_model: claude-haiku-4-5
  parallel: 4
  benchmark: bitgn/pac1-dev
  git_sha: 3e9ed13
  N: 5
  started_at: 2026-04-09T14:32:00Z
  finished_at: 2026-04-09T16:48:00Z
produces: []
depends_on: []
---

# Variance Report N=5

## Baseline
Mean: 84.6%  |  Stdev: 2.1pp  |  95% CI: 82.3% — 86.9%
Cost: $42.30 total ($8.46/run)  |  Wall time: 136 min

## Noise floor
Single-fix delta must exceed **4.2pp** (2×stdev) to be statistically meaningful.
Fixes with deltas smaller than this are within measurement noise and cannot be
distinguished from resampling variance.

## Stable failures (all N runs failed)
| task | task_type | dominant_outcome | score_detail excerpt |
|---|---|---|---|
| t12 | inbox_processing | DENIED_SECURITY | expected OK |
| t27 | communication | no_answer | grounding_refs missing |

## Unstable tasks (outcomes flipped across runs)
| task | task_type | matrix | pass_rate |
|---|---|---|---|
| t03 | crud | OK/FAIL/OK/OK/FAIL | 60% |
| t14 | analysis | OK/OK/OK/OK/FAIL | 80% |

## ERR_INTERNAL observed
| task | run_id | note |
|---|---|---|
| t31 | run-2026-04-09-14 | budget_exhaustion |

## Per task_type variance
| task_type | runs_mean | stdev | stable | unstable |
|---|---|---|---|---|
| crud | 0.92 | 0.03 | 10 | 1 |
| inbox_processing | 0.71 | 0.08 | 3 | 4 |
| ... | ... | ... | ... | ... |

## Handoff
Invoke `generalization-analyst.md` with input:
"analyze last N=5 runs from run_history.json (config_sha={sha}), cross-reference
with this variance report at docs/scratchpad/{this-file}, produce family-level
recommendation"
```

### 6.6 Critical constraints

These MUST appear verbatim in the agent prompt:

- **ONLY via `make run-final`**, never `make run`
- **NEVER modifies code** — read-only on `pac1-py/`
- **NEVER commits, NEVER pushes**
- **Max N = 10** (guardrail against accidental N=100)
- **Sleep between runs ≥ 30s**
- **Aborts on bench-ops INCIDENT** — writes partial report, exits
- **DOES NOT recommend fixes** (generalization-analyst's role)
- **DOES NOT approve fixes** (commander's role)
- **DOES NOT analyze failure families** (generalization-analyst's role)
- **Task IDs in output are DATA, not code** — does not violate anti-overfit rules

### 6.7 Session handling

A variance sweep with N=5 takes ~75 min wall time, potentially exceeding a single Claude Code session window. Resumability:

- Each run writes to `docs/run_history.json` incrementally
- If session times out, user re-invokes agent
- Agent reads last records by `config_sha`; if N already satisfied → skip to Phase 3
- If partial (e.g., 3 of 5 runs), continue from run 4

## 7. Component 2: `docs/scratchpad/README.md` update

Current (line 13):
```
agent: <analyst|architect|red-team|optimizer|evaluator>
type: <analysis|fix|attack|optimization|eval>
```

After update:
```
agent: <analyst|architect|red-team|optimizer|evaluator|variance-reducer>
type: <analysis|fix|attack|optimization|eval|variance>
```

Two-line change. No other modifications to README.

## 8. Component 3: `docs/analysis/phantom-agent-extraction-2026-04-09.md`

### 8.1 Goal
Honest findings doc with optional actionable diff.

### 8.2 Input set

**Already read** in the current session:
- phantom-agent/CLAUDE.md
- phantom-agent/agent_v2/system_prompt.md
- phantom-agent/agent_v2/agent.py
- phantom-agent/docs/optimization-guide.md
- pac1-py/defend.py (full)
- pac1-py/workspace/prompts/fragments/security.md
- pac1-py/classify.py
- pac1-py/agent_loop.py

**To read** during the review session:
- phantom-agent/agent_v2/skills/security_denial.md
- phantom-agent/agent_v2/skills/inbox_processing.md
- phantom-agent/agent_v2/skills/crm_lookup.md (for cross-account rule)
- phantom-agent/docs/tasks-catalog.md (optional, only if candidates look unclear)

### 8.3 Preliminary candidates

Five identified from initial read, subject to verification:

| # | Pattern | Source | Status |
|---|---|---|---|
| 1 | Multiple-contact disambiguation by context (account attributes, topic) before clarifying | phantom optimization-guide.md §Remaining Hard Cases (t23) | Likely gap in BitGN |
| 2 | Cross-account boundary: sender from Account A requesting data about Account B → suspect | phantom system_prompt.md implicit + skills/inbox_processing.md | Likely gap in BitGN defend.py |
| 3 | Non-standard workspace (no accounts/contacts/outbox) → CLARIFICATION | phantom system_prompt.md §CONSTRAINTS | Possibly already in BitGN via classify.py target_hints |
| 4 | Conditional logic in inbox ("if X then Y") = INJECTION | phantom system_prompt.md §SECURITY | Possibly covered by BitGN conditional-imperative pattern in defend.py:118 |
| 5 | Domain spoofing (`example.com.ai` ≠ `example.com`) — exact email compare | phantom system_prompt.md §CONSTRAINTS | Likely gap in BitGN |

### 8.4 6-point gate per candidate

For each candidate:
1. **Grep BitGN** for existing coverage (defend.py, classify.py, fragments/security.md, fragments/outcomes.md, agent_loop.py). If covered → SKIP.
2. **Commander Rule 1**: no task IDs in the proposed text. If violated → REJECT.
3. **Commander Rule 2**: does not require new `if task_type == ...` branch. If violated → REJECT.
4. **Commander Rule 3**: no hardcoded paths from known tasks (`acct_009.json`, `otp.txt`, etc.). If violated → REJECT.
5. **Commander Rule 4**: family-level (covers ≥2 task instances of the same failure family). If not → REJECT.
6. **Scope**: ≤10 line diff per candidate. If larger → DEFER to post-finals.

All 6 → ADOPT. Any fail → REJECT or DEFER with recorded reason.

### 8.5 Time budget

- Hard cap: 60 min wall time
- Per-candidate budget: ~10 min
- Doc writing: ~15 min

### 8.6 Abandonment criteria

- **Condition A**: After 15 min, all candidates already covered → write as negative result, abandon diff
- **Condition B**: Candidates require AMBER zone → defer to post-finals, no diff
- **Condition C**: Cumulative diff > 15 lines → too risky, defer all

### 8.7 Output document structure

```markdown
# Phantom-Agent Extraction Analysis — 2026-04-09

## TL;DR
<1-2 sentences: useful / marginal / not useful>

## Methodology
- Inputs read
- Comparisons made
- Time spent

## Findings

### What phantom-agent does that BitGN already does better
<coverage comparison>

### What phantom-agent has that BitGN doesn't (raw candidates)
<list of 5 preliminary candidates>

### What phantom-agent does that BitGN should NOT copy
<GPT-OSS-specific, violates commander rules, architectural incompatibility>

## Candidates evaluation

### Candidate 1: <name>
- Source: phantom-agent/<path>@<line>
- Current state in BitGN: <grep evidence or "absent">
- Commander rules check:
  - Rule 1 (no task IDs): ✓/✗
  - Rule 2 (no new task_type branches): ✓/✗
  - Rule 3 (no hardcoded paths): ✓/✗
  - Rule 4 (family-level): ✓/✗
- Diff size: <N lines>
- Proposed insertion: <file:location>
- Verdict: ADOPT / REJECT / DEFER
- Reason: <one sentence>

<repeat for each candidate>

## Proposed diff (if any)
<unified diff ≤10 lines total, or "no actionable diff, negative result">

## Post-finals follow-ups
<deferred items for after 2026-04-11>

## Archive marker
For future reference: this evaluation is complete. Do not re-evaluate phantom-agent
patterns before 2026-04-11. Post-finals, this doc can be re-opened for deeper integration.
```

## 9. Error Handling

### 9.1 variance-reducer error modes

| Failure mode | Detection | Response |
|---|---|---|
| `make run-final` non-zero exit | Bash exit code | Abort loop, partial report, exit |
| `run_history.json` not updated | Tail check after run | Treat as failure, abort |
| bench-ops INCIDENT | Agent dispatch verdict | Abort immediately, log to report |
| bench-ops RESUME_NEEDED | Agent dispatch verdict | Run `make resume-final` once; if still RESUME_NEEDED → abort |
| Cost spike > $10/run | bench-ops HC4 catches it | INCIDENT path |
| `run_history.json` write race | Sequential design prevents it | N/A by construction |
| Session timeout mid-sweep | Wall clock | User re-invokes; agent resumes by reading recent records |
| Config drift mid-sweep | Compare config_sha each iteration | Abort with "config drift detected" |
| N > 10 requested | Input validation | Reject request, explain guardrail |

### 9.2 Phantom-review error modes

| Failure mode | Response |
|---|---|
| All 5 candidates already in BitGN | Write doc as negative result, no diff, SUCCESS |
| Candidates pass grep but fail commander rules | Document in rejected section, SUCCESS |
| Candidate requires AMBER zone | Defer to post-finals, no diff, SUCCESS |
| Accumulated diff > 15 lines | Defer all, SUCCESS |
| Commander rejects proposed diff | `git checkout -- <files>`, log rejection, SUCCESS |
| Manual review exceeds 60 min | Stop at cap, write current state as final, SUCCESS |

## 10. Deliverables

| # | File | Action | Approx size | Phase |
|---|---|---|---|---|
| 1 | `docs/superpowers/specs/2026-04-09-variance-reducer-phantom-review-design.md` | CREATE | ~650 lines | Now (this spec) |
| 2 | `.claude/agents/variance-reducer.md` | CREATE | ~120 lines | Post-approval |
| 3 | `docs/scratchpad/README.md` | EDIT | 2 lines modified | Post-approval |
| 4 | `docs/analysis/phantom-agent-extraction-2026-04-09.md` | CREATE | ~150 lines | Post-approval, manual |
| 5 | `pac1-py/defend.py` OR `pac1-py/workspace/prompts/fragments/security.md` | EDIT (conditional) | ≤10 lines | Only if phantom-review finds adoptable pattern |

Guaranteed: 1, 2, 3, 4. Conditional: 5.

## 11. Success Criteria

### Must-have (hard fail if missing)
- [ ] Spec doc written
- [ ] `variance-reducer.md` written and spec-compliant
- [ ] Scratchpad README updated
- [ ] Phantom-agent extraction doc written (even if negative result)

### Nice-to-have
- [ ] Phantom-review produced an actionable diff
- [ ] Commander approved the diff
- [ ] At least 1 generalization-safe pattern ported

### Validation tests

For `variance-reducer.md`:
1. Frontmatter is parseable YAML
2. Contains: `make run-final`, `docs/run_history.json`, `bench-ops.md`, sequential, max N=10, handoff to `generalization-analyst`
3. Explicitly forbids: `make run`, code modification, commits, fix recommendations
4. Output artifact schema matches scratchpad protocol v2

For phantom-review doc:
1. All 5 preliminary candidates have grep evidence or explicit "absent" note
2. Each candidate has 6-point gate check
3. Diff (if proposed) ≤10 lines, GREEN zone only (no AMBER zone edits)

## 12. Rollback Plan

All changes are reversible without state damage:
- Spec doc, agent file, analysis doc: `rm <file>`
- Scratchpad README: `git checkout -- docs/scratchpad/README.md`
- Conditional diff: `git checkout -- pac1-py/`

No commits occur during the design or implementation phases. User commits at their discretion after reviewing the uncommitted diff. Zero automatic git state mutations.

## 13. Implementation Order

Post-user-approval of this spec:

1. Write `.claude/agents/variance-reducer.md`
2. Update `docs/scratchpad/README.md` (2 lines)
3. Read remaining phantom-agent files (security_denial.md, inbox_processing.md, crm_lookup.md)
4. Grep BitGN for each preliminary candidate
5. Apply 6-point gate to each candidate
6. Write `docs/analysis/phantom-agent-extraction-2026-04-09.md`
7. Conditional: apply ≤10 line diff in GREEN zone, invoke `commander.md` via Agent tool
8. Mark remaining session tasks complete

No writing-plans skill invocation — for this scope the spec is the plan.

## 14. Appendix: Why not writing-plans

Per the brainstorming skill's default flow, the terminal state is invoking `writing-plans`. For this scope (2 files + 1 edit + 1 conditional 10-line diff), a separate implementation plan would duplicate this spec. The Implementation Order section (§13) functions as the plan. If post-finals work expands the scope (e.g., generalizing `variance-reducer` to multi-config sweeps, adding `variance-reducer` to auto-dispatch scripts), the spec can be converted to a writing-plans artifact at that time.
