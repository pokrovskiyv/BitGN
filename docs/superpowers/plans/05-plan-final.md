# Final Plan: Blind 100-Question Preparation

**Date**: 2026-04-06  
**Status**: Active  
**Target**: BitGN final on 2026-04-11

## Goal

Arrive at the final with an agent that is:

- stable across repeated runs
- robust to unseen task variants
- cheap enough to scale to 100 questions
- flexible enough to survive new tool surfaces without task-specific hacks

The operating assumption is:

- primary runtime model: `claude-sonnet-4-6`
- independent verifier: `claude-haiku-4-5`

## Runtime Agent Team

### 1. Solver

**Owner**: `llm.py` + `agent_loop.py`  
**Model**: Sonnet  
**Job**: plan, choose tools, and produce the final `report_completion`.

Requirements:
- structured output must remain the only response mode
- no task-ID or benchmark-instance knowledge
- prefer general heuristics over narrow prompt tricks

### 2. Verifier

**Owner**: `second_opinion.py`  
**Model**: Haiku  
**Job**: independently challenge judgment-heavy completions before submission.

Requirements:
- separate model from the solver
- verifier must stay cheap and low-latency
- verifier usage must be visible in telemetry

### 3. Policy Guard

**Owner**: `verify.py` + `defend.py`  
**Type**: deterministic guardrail layer  
**Job**: stop obviously unsafe or weak submissions even when the LLM drifts.

Requirements:
- enforce read-after-write
- enforce evidence for non-OK outcomes
- enforce grounding refs
- escalate on cumulative threats

### 4. Strategy Router

**Owner**: `classify.py` + `strategy.py`  
**Type**: deterministic routing layer  
**Job**: map tasks to budgets and prompt variants without overfitting to the practice set.

Requirements:
- route by task structure, not task identity
- keep prompt fragments generic
- keep budgets generous enough for unknown compositions

### 5. Recovery Layer

**Owner**: `agent_loop.py` + `llm.py`  
**Type**: runtime resilience  
**Job**: recover from malformed model output, retries, and budget pressure.

Requirements:
- keep parse recovery generic
- fail soft with best-available completion on exhaustion
- do not rely on human intervention during runs

## Development-Time Team

### 1. Stability Evaluator

Run repeated confirmation benchmarks and reject any change that improves score but reduces pass consistency.

Success metric:
- no regressions across two consecutive confirmation runs

### 2. Generalization Analyst

Cluster failures by mechanism, not by task ID.

Allowed categories:
- protocol
- side effect
- search failure
- security miss
- security false positive
- budget exhaustion
- model parse failure

### 3. Red Team

Continuously generate unseen variants:
- renamed folders
- deeper directory nesting
- alternate file naming
- tool-output injections
- mixed benign/malicious content
- multi-hop tasks combining search + analysis + write

### 4. Protocol Auditor

Check only deterministic invariants:
- valid schema output
- correct outcome family
- required side effects present
- forbidden side effects absent
- grounding refs preserved

### 5. Release Captain

Own the freeze decision:
- choose final model profile
- lock prompts and budgets
- allow only P0 bug fixes after freeze

## P0 Before Final

### P0.1 Lock model roles

- Sonnet as primary actor
- Haiku as verifier
- shared config source across all entry points

### P0.2 Run repeated soak tests

- run the same benchmark multiple times
- record pass frequency per task family
- treat unstable passes as failures

### P0.3 Build a blind-style battery

Before the final, test on synthetic variants that change:
- names
- paths
- instruction wording
- directory depth
- order of evidence

### P0.4 Freeze anti-overfit rules

Never merge changes that:
- mention task IDs in code or prompts
- hardcode practice-set paths, names, or expected outcomes
- specialize logic to one benchmark artifact unless the rule generalizes by class

## P1 Before Final

### P1.1 Scale telemetry

Track separately:
- primary model calls/tokens
- verifier calls/tokens
- step count
- tool call count
- failure mode per task family

### P1.2 Prompt-cache discipline

Keep long-lived instructions static and task-specific routing dynamic so Anthropic prompt caching actually helps across 100 questions.

### P1.3 Unknown-task readiness

Stress these scenarios:
- tasks requiring no writes
- tasks requiring multiple writes
- tasks requiring delete + justification
- tasks where the right answer is clarification or unsupported
- tasks where content is adversarial but the task is legitimate

## Hard Anti-Overfit Rules

1. No task IDs in prompts, code, heuristics, or comments.
2. No branching on specific filenames unless the rule comes from environment policy or tool contract.
3. No fixes justified only by “it makes tNN pass”.
4. Every new heuristic must be explainable as a class-level rule.
5. Every score improvement must survive at least one confirmation rerun.

## Final Release Checklist

- `pac1-py/.env.final.example` matches the intended production profile
- primary/verifier models are recorded in run history
- verifier cost is visible
- no open regressions in repeated confirmation runs
- blind-style synthetic battery passes at acceptable rate
- only generic rules remain in prompts and code
