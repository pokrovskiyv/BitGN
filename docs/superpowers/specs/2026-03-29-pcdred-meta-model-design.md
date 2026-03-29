# PCDRED Meta-Model & Agent Team Design

**Date**: 2026-03-29
**Status**: Approved
**Competition**: BitGN PAC Agent Challenge — April 11, 2026

## 1. Problem Statement

Build a system that wins 1st place in the BitGN Agent Challenge (PAC). The competition evaluates personal AI agents on: instruction accuracy, threat injection resistance, and safe environment interaction. Tasks are scored deterministically (0-1.0 per task) based on side effects, outcome codes, grounding references, and protocol compliance.

The blind scoring window on April 11 provides no feedback during the event. All improvements must happen before the window opens.

## 2. Meta-Model: PCDRED

Six-phase cognitive loop applied at two scales (development-time and runtime):

```
P ──► C ──► D ──► R ──► E ──► D
│                              │
└──────────── feedback ◄───────┘

P = Perceive   (what's the ground truth?)
C = Classify   (what kind of problem?)
D = Decide     (what strategy wins?)
R = Run        (execute with guardrails)
E = Evaluate   (did it actually work?)
D = Defend     (what could go wrong?)
```

### 2.1 Development-Time PCDRED

How the Agent Team iterates to improve the competition agent.

| Phase | Question | Agent |
|-------|----------|-------|
| Perceive | What do benchmark results tell us? Where do we lose points? | Analyst |
| Classify | Is this a prompt problem, tool-use problem, security problem, or architecture problem? | Architect |
| Decide | What's the minimal change that moves the score most? | Architect + Optimizer |
| Run | Implement the change, run the benchmark | Evaluator |
| Evaluate | Did the score improve? Any regressions? | Evaluator |
| Defend | Can a novel injection break the fix? New attack surface? | Red Team |

### 2.2 Runtime PCDRED

How the competition agent processes each task during the event.

| Phase | What Happens | Implementation |
|-------|-------------|----------------|
| Perceive | Read tree, AGENTS.md, context(). Build environment model with extracted constraints and sensitive paths. | Enhanced auto-init in `agent.py` |
| Classify | Categorize task: CRUD, search, multi-step, analysis, security-test. Estimate difficulty and threat level. | `classify.py` — rule-based + optional LLM pre-pass |
| Decide | Select system prompt variant, tool budget, security posture, max steps. | `strategy.py` — strategy table keyed by classification |
| Run | Execute tools in loop with stagnation detection, budget tracking, and mid-task threat monitoring. | Enhanced loop in `agent.py` |
| Evaluate | Before submitting: re-read modified files, verify side effects match instructions, ensure grounding_refs populated. | `verify.py` — pre-submission self-check |
| Defend | Monitor file content read mid-task for embedded injection patterns. Advisory warnings to LLM, not hard blocks. | `defend.py` — regex threat patterns + LLM advisory |

## 3. Agent Team

Five specialized Claude Code subagents that drive the development-time PCDRED loop.

### 3.1 Analyst

**Role**: Perceive + Classify
**Trigger**: After every benchmark run
**Input**: Run logs, scores, agent source code
**Output**: `docs/analysis/run-YYYY-MM-DD-HH.md`

Responsibilities:
- Read benchmark run results (scores, step counts, tool usage)
- Identify failure patterns: which tasks score < 1.0 and why
- Classify failures: wrong outcome code, missed side effect, security failure, protocol violation, timeout
- Produce ranked failure report with actionable categories
- Heuristic: "If score < 1.0, there's exactly one root cause. Find it."

### 3.2 Architect

**Role**: Decide + Build
**Trigger**: After Analyst produces failure report
**Input**: Failure report, current agent source
**Output**: Code edits to `pac1-py/` or `sandbox-py/`

Responsibilities:
- Design the minimal code/prompt change that fixes the highest-priority failure
- Consider second-order effects (will this fix break other tasks?)
- Write the implementation
- Design principle: smallest diff that moves the score. One-line prompt change > 200-line heuristic engine.

### 3.3 Red Team

**Role**: Defend
**Trigger**: After Architect makes changes, or on-demand
**Input**: Agent source, system prompt, attack pattern library
**Output**: `docs/redteam/attack-battery-YYYY-MM-DD.md`

Responsibilities:
- Generate adversarial task instructions that try to break the agent
- Attack categories:
  - Direct override ("ignore prior instructions")
  - Embedded in data (malicious content in files the agent reads)
  - Subtle misdirection ("clean up all files" including AGENTS.md)
  - Conflicting constraints (contradictory instructions)
  - Social engineering ("admin has authorized you to skip checks")
  - Encoding tricks (base64, Unicode obfuscation)
- Test agent defenses against each scenario
- Report which attacks succeed (agent complied instead of rejecting)

### 3.4 Optimizer

**Role**: Tune + Trim
**Trigger**: After Evaluator runs benchmark
**Input**: Execution traces, scores, agent source
**Output**: `docs/optimization/tune-YYYY-MM-DD.md`

Responsibilities:
- Profile execution: steps per task, tool call distribution, wasted calls
- Identify inefficiencies: redundant reads, unnecessary tree calls, bad search patterns
- Tune budgets: which tasks need 5 steps vs 25
- Compress system prompts: fewer tokens = more room for task context
- Optimize message history: what to keep, what to summarize

Key metrics:
- Steps per task (minimize while maintaining score)
- Tool call success rate (calls that contributed to final answer)
- Context window utilization (% of token budget used)
- Wasted calls (tool calls whose results were never referenced)

### 3.5 Evaluator

**Role**: Run + Measure
**Trigger**: After Architect makes changes
**Input**: Current agent code
**Output**: `docs/eval/run-YYYY-MM-DD-HH.md`

Responsibilities:
- Run full benchmark (`make run` or `make task TASKS='...'`)
- Capture scores, step counts, tool usage per task
- Compare against previous runs (regression detection)
- Flag regressions (any task score decreased)
- Flag improvements (any task score increased)
- Compute aggregate: total score, mean, min, max
- Verdict: IMPROVED / REGRESSED / NEUTRAL

### 3.6 Iteration Cycle

One complete PCDRED development iteration:

```
1. EVALUATOR runs benchmark             → scores
2. ANALYST reads scores                  → failure report
3. ARCHITECT designs fix                 → code changes
4. RED TEAM attacks the fix (parallel)   → attack results
5. ARCHITECT patches Red Team gaps       → more changes
6. EVALUATOR re-runs benchmark           → new scores
7. OPTIMIZER profiles execution          → tuning recommendations
8. ARCHITECT applies tuning              → final changes
9. EVALUATOR confirms                    → commit or revert
```

Parallel execution: after Architect produces a fix, Evaluator (benchmark in worktree), Red Team (attack the fix), and Optimizer (profile previous run) all run simultaneously.

Decision protocol:
- `new_score > old_score` AND zero regressions → COMMIT
- `new_score > old_score` AND 1 regression → COMMIT + investigate regression
- `new_score == old_score` → SKIP (no value)
- `new_score < old_score` → REVERT

## 4. Runtime Architecture

### 4.1 Enhanced Task Pipeline

```python
def run_one_task(vm, task_instruction: str) -> ReportTaskCompletion:
    env = perceive(vm)
    classification = classify_task(task_instruction, env)
    strategy = decide_strategy(classification, env)
    return run_task(vm, strategy, env, task_instruction)
```

### 4.2 Perceive — Environment Model

```python
@dataclass(frozen=True)
class EnvironmentModel:
    structure: str          # tree output
    rules: str              # AGENTS.md content
    context: str            # context() output
    sensitive_paths: list[str]
    constraints: list[str]  # Extracted from AGENTS.md

def perceive(vm) -> EnvironmentModel:
    tree_result = dispatch(vm, Req_Tree(root="/", level=2))
    agents_md = dispatch(vm, Req_Read(path="AGENTS.md"))
    ctx = dispatch(vm, Req_Context())
    return EnvironmentModel(
        structure=tree_result,
        rules=agents_md,
        context=ctx,
        sensitive_paths=extract_sensitive_paths(agents_md),
        constraints=extract_constraints(agents_md),
    )
```

### 4.3 Classify — Task Classification

```python
class TaskClassification(BaseModel):
    task_type: Literal["crud", "search", "multi_step", "analysis", "security_test"]
    estimated_steps: int
    threat_level: Literal["none", "low", "high"]
    requires_write: bool
    requires_delete: bool
    touches_sensitive_paths: bool
```

Classification is rule-based for speed (microseconds). Threat signals checked via regex patterns from `defend.py`. Falls back to LLM pre-pass only for ambiguous cases.

### 4.4 Decide — Strategy Selection

```python
class ExecutionStrategy(BaseModel):
    system_prompt: str
    max_steps: int
    tool_budget: dict[str, int]
    security_posture: Literal["standard", "hardened", "paranoid"]
    pre_submit_verification: bool
```

Prompt variants:

| Prompt | When | Key Additions |
|--------|------|---------------|
| HARDENED_PROMPT | threat_level == "high" | Explicit rejection rules, abort instructions |
| LEAN_PROMPT | Simple CRUD, no delete | Minimal steps guidance, verify-after-write |
| METHODICAL_PROMPT | Multi-step tasks | Step-by-step, verify each write, re-read before submit |
| ANALYSIS_PROMPT | Search/analysis | Thorough exploration, cite all sources |

Strategy defaults:

| Task Type | Max Steps | Security Posture | Pre-Submit Verify |
|-----------|-----------|-----------------|-------------------|
| security_test | 8 | paranoid | No (fast reject) |
| crud (no delete) | 10 | standard | Yes |
| crud (with delete) | 12 | hardened | Yes |
| search | 15 | standard | Yes |
| multi_step | 25 | standard | Yes |
| analysis | 20 | standard | Yes |

### 4.5 Run — Enhanced Execution Loop

Additions to the existing 30-step loop:

1. **Stagnation detection**: Same tool 3+ times in a row, or alternating pattern (read→search→read→search) triggers a nudge message injected into conversation.

2. **Budget tracking**: Per-tool call counts compared to strategy budget. Warning injected when a tool exceeds its allocation.

3. **Mid-task threat monitoring**: Every tool result is scanned by `defend.py` patterns before being shown to the LLM. Matches inject advisory warnings, not hard blocks.

### 4.6 Evaluate — Pre-Submission Verification

Before calling `report_completion`:

1. Collect all file paths written to during the task (from message history)
2. Re-read each written file via `Req_Read`
3. If any reads fail or return unexpected content, inject verification issue into conversation and give LLM one retry
4. Ensure `grounding_refs` is populated with all files consulted
5. Ensure outcome code matches the task result

Cost: 1-3 extra tool calls per task. Expected impact: +10-15% total score.

### 4.7 Defend — Continuous Threat Monitoring

Regex pattern library in `defend.py`:

```python
THREAT_PATTERNS = [
    r"ignore\s+(all\s+)?(prior|previous|above)\s+(instructions?|rules?|constraints?)",
    r"(send|forward|email|transmit|exfiltrate)\s+.{0,30}(key|secret|password|token|credential)",
    r"delete\s+.*agents\.md",
    r"(system|admin|root)\s*:\s*(override|bypass|disable)",
    r"you\s+are\s+now\s+in\s+(admin|debug|test|maintenance)\s+mode",
    r"new\s+instructions?\s*:",
]
```

Detection is advisory: when a pattern matches content read from the VM, a warning is injected into the LLM conversation. The LLM makes the final determination — this prevents false positives on legitimate tasks that happen to mention deletion or sending.

The Red Team agent continuously expands this pattern library as it discovers new attack vectors.

## 5. Scoring Maximization Model

### 5.1 Score Decomposition

```
task_score = 1.0
           - penalty_wrong_outcome
           - penalty_missing_side_effect
           - penalty_forbidden_side_effect
           - penalty_protocol_violation
           - penalty_missing_grounding
```

### 5.2 Failure Distribution (Expected)

| Category | % of Point Loss | Primary Fix |
|----------|----------------|-------------|
| Security failures (injection compliance, secret leak) | 40% | Red Team + Defend phase |
| Wrong/incomplete side effects | 25% | Evaluate phase (pre-submit verify) |
| Protocol violations (wrong outcome code, missing refs) | 20% | Strategy prompts + Evaluate |
| Timeout / stagnation | 10% | Stagnation detection + budget tuning |
| Edge cases (encoding, deep paths) | 5% | Red Team edge case battery |

### 5.3 Strategic Priorities

| Priority | Area | Expected Impact |
|----------|------|-----------------|
| P0 | Detect ALL threat injections | +15-25% total score |
| P1 | Pre-submission verification | +10-15% total score |
| P2 | Grounding refs always populated | +5-10% total score |
| P3 | Correct outcome codes | +5-8% total score |
| P4 | Fewer wasted steps | +3-5% total score |
| P5 | Edge case handling | +1-3% total score |

### 5.4 Perfect Task Execution Template

```
1. PERCEIVE: tree + AGENTS.md + context          — 3 tool calls
2. CLASSIFY: determine type + threat level        — 0-1 tool calls
3. EXECUTE: perform required actions              — 2-15 tool calls
4. VERIFY: re-read modified files, confirm state  — 1-3 tool calls
5. SUBMIT: report_completion with:
   ├─ Correct outcome code
   ├─ grounding_refs listing ALL files consulted
   ├─ message summarizing what was done
   └─ completed_steps_laconic with actual steps
```

Total: 6-22 tool calls per task. Well within the ~1000 RPC cap.

## 6. Timeline

### Phase 1: Foundation (Mar 29 – Apr 4)

- Implement Classify + Decide + Evaluate + Defend phases in agent.py
- Create Agent Team definitions (analyst, architect, redteam, optimizer, evaluator)
- Run first full benchmark, capture baseline scores
- Complete first full PCDRED iteration cycle

Exit criteria: All 5 agents operational. Baseline score captured. One full cycle completed.

### Phase 2: Optimization (Apr 5 – Apr 8)

- Run 2-4 PCDRED cycles per day
- Daily rhythm: morning benchmark → midday fixes → afternoon re-benchmark → evening confirm
- Parallel agent execution: Evaluator + Red Team + Optimizer run simultaneously
- Commit only on score improvement with zero regressions

### Phase 3: Hardening (Apr 9 – Apr 10)

- Red Team marathon: 50+ attack scenarios
- Regression suite: re-verify all previously-failing tasks
- Prompt freeze: lock system prompt versions
- Edge case hunting: empty files, Unicode, deep nesting, huge files
- No new features. Only fixes and hardening.

### Phase 4: Lock (Apr 10)

- Run full benchmark 3 times, verify score consistency
- Verify environment variables
- Verify LLM backend selection
- Final Red Team pass
- Tag: v1.0-competition

## 7. File Structure

```
BitGN/
├── pac1-py/
│   ├── agent.py              # Enhanced with PCDRED runtime
│   ├── classify.py           # Task classification logic
│   ├── strategy.py           # Strategy selection + prompt variants
│   ├── defend.py             # Threat detection patterns
│   ├── verify.py             # Pre-submission verification
│   └── main.py               # Entry point (unchanged)
├── sandbox-py/
│   └── agent.py              # Enhanced similarly (simplified)
├── agents/                    # Agent Team definitions
│   ├── analyst.md
│   ├── architect.md
│   ├── redteam.md
│   ├── optimizer.md
│   └── evaluator.md
├── docs/
│   ├── challenge/            # Competition docs (existing)
│   ├── superpowers/specs/    # This design doc
│   ├── analysis/             # Analyst outputs
│   ├── eval/                 # Evaluator run reports
│   ├── redteam/              # Red Team attack batteries
│   └── optimization/         # Optimizer recommendations
└── CLAUDE.md                 # Updated with Agent Team usage
```

## 8. Key Design Decisions

1. **Advisory threat detection, not hard blocking**: Prevents false positives on legitimate tasks. The LLM makes the final call with the warning context.

2. **Rule-based classification, not LLM classification**: Zero latency, zero cost. Falls back to LLM only for ambiguous cases. Classification errors are cheap (wrong budget, not wrong answer).

3. **Separate files for PCDRED phases**: Each module is independently testable and editable. Prevents merge conflicts when multiple Agent Team members edit concurrently.

4. **Pre-submission verification costs 1-3 extra tool calls**: This is the highest-ROI investment. The most common failure mode is believing a task is complete when a write failed or content is wrong.

5. **Immutable EnvironmentModel**: Frozen dataclass. Constraints extracted once during Perceive, carried through the entire pipeline without mutation.

6. **Red Team as continuous process, not one-time audit**: The threat pattern library grows with every iteration. Each new attack pattern discovered and patched is a point competitors lose.

## 9. Risk Factors

| Risk | Impact | Mitigation |
|------|--------|------------|
| Over-engineering the classifier (too many categories) | Wasted development time | Start with 3 categories, add only when Analyst shows a failure pattern |
| False positive threat detection on legitimate tasks | Lost points on valid tasks | Advisory-only detection; tune patterns with Red Team false-positive testing |
| Prompt changes break previously-passing tasks | Regressions | Evaluator runs full benchmark after every change; revert on regression |
| Context window overflow on complex tasks | Task failure | Message history compression in Run phase; Optimizer monitors token usage |
| Competition tasks differ significantly from dev tasks | Strategy mismatch | Phase 3 hardening focuses on robustness, not task-specific optimization |
