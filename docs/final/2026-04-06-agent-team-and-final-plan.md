# Final Prep Plan - 2026-04-06

## Mission

We should optimize for blind-final robustness, not for one more practice-set point. The official docs make three constraints explicit:

1. The competition task set is unseen during the blind window, and detailed feedback is suppressed.
2. Task instances vary across seeded worlds, which is meant to punish hard-coding.
3. Scoring is deterministic on side effects, forbidden actions, references, and protocol compliance.

That means the right target is stable family-level behavior:

- correct outcome selection under ambiguity
- safe side effects under prompt injection
- low variance across task variants and providers
- graceful degradation when the model is uncertain or the provider is unstable

## Agent Team

### 1. Commander

Owns release decisions before the final.

- Accept only GREEN-zone changes that improve stability across repeated runs.
- Reject single-task fixes, task-ID reasoning, or prompt text that encodes practice-set facts.
- Freeze the branch once the final profile is stable and only allow break-fix edits after that.

### 2. Architect

Owns the runtime and control loop in `pac1-py/`.

- Keep the main agent general-purpose and domain-driven.
- Prefer infrastructure fixes over prompt hacks.
- Push all model/provider choices into config, not into task logic.

### 3. Generalization Analyst

Owns failure families, not individual tasks.

- Group failures by pattern: wrong outcome, missing side effect, grounding miss, no answer, security miss, security false positive.
- Treat any fix as valid only if it helps a class of tasks or removes a structural bottleneck.
- Watch for practice-set overfitting signals: path-specific assumptions, folder-specific behavior, and task-type shortcuts.

### 4. Red Team

Owns unknown-unknowns.

- Attack prompt hierarchy, tool-output poisoning, history poisoning, false trust, new directory shapes, and future tool surfaces.
- Prefer attacks that look legitimate rather than explicit "ignore instructions" payloads.
- Keep a standing battery for blind-final regressions.

### 5. Evaluator and Historian

Own run quality and stability evidence.

- Require repeated confirmation runs before accepting a change.
- Track variance, not just best score.
- Promote metrics that matter in the blind final: no-answer rate, wrong-outcome rate, unexpected side effects, grounding misses, and token/latency blowups.

### 6. BenchOps

Owns execution reliability.

- Keep resume, run history, task cache, and provider settings healthy.
- Prepare for rate limits, temporary provider failures, and long-run cost spikes.
- Maintain a simple "final profile" that can be executed without ad hoc edits.

## What Is Good Already

- The repo already has a PCDRED-style team shape in `agents/`.
- The agent loop is domain-pluggable through `DomainProtocol`, which is the right direction for new task surfaces.
- The challenge docs explicitly reward deterministic, protocol-safe behavior over clever prose, which matches the current architecture.

## Observed Evidence

- `docs/run_history.json` has 149 recorded runs, which is enough to distinguish structural issues from one-off regressions.
- The dominant failure details are still structural, not cosmetic: wrong outcome selection, "no answer provided", wrong security outcome, and missing deterministic side effects such as `outbox/seq.json`.
- `docs/task_cache.json` shows prompt-token blowups on long tasks and at least one zero-step failure, which confirms that budget and provider resilience still matter even when the top-line practice score is high.

## Highest Risks Before The Final

### 1. Current logic still leans on practice-era task taxonomy

`classify.py`, `strategy.py`, and `verify.py` still make strong decisions from a fixed set of task types such as `crud`, `communication`, and `inbox_processing`. That is useful for the current practice benchmark, but it is also the biggest overfit surface if the final adds new task families or mixes capabilities differently.

What to do:

- Reduce reliance on task-type-specific fallbacks.
- Prefer evidence-based decisions from observed tool results and side effects.
- Make domain-contributed rules first-class instead of keeping `classification_rules` and `strategy_entries` unused.

### 2. Security posture is partly declarative, not behavioral

`strategy.py` computes `security_posture`, but the runtime does not use it to materially change loop behavior. Red-team notes already call this out.

What to do:

- Make `security_posture` control real policy: stricter completion gates, lower tolerance for risky writes, stronger fallback on cumulative threats, and tighter verifier escalation.

### 3. Semantic stagnation is still weak

The project has a repeated-call stagnation detector, but a blind final will include more ways to waste budget than exact repeated tool calls. Search misses, unique-but-futile reads, and error clusters can still burn the whole task.

What to do:

- Add semantic stagnation: repeated `not_found`, repeated empty search/list evidence, and "no new files consulted" windows.
- Separate productive steps from gate-only loops when evaluating progress.

### 4. Fallback outcomes still contain task-family assumptions

`_fallback_outcome()` in `verify.py` still guesses from tracker state plus task type. That can turn a stuck run into the wrong answer family, especially if the final introduces new communication-like tasks or partial-capability tasks.

What to do:

- Base fallback on observed evidence and completed side effects, not on one task-type branch.
- Track whether writes were relevant to the requested objective, not just whether any write happened.

### 5. Grounding is stronger than before, but still incomplete

Grounding refs merge read/write paths, but list/search-derived evidence is still easier to lose. The latest practice failures include missing required refs, which is exactly the kind of deterministic mistake that will hurt in a blind final.

What to do:

- Track consulted evidence at the artifact level, including list/search-derived hits when they materially informed the answer.
- Add a last-mile grounding verifier before `report_completion`.

### 6. Provider and model volatility can masquerade as product regressions

Run history shows strong score variance by model and by period, and prior analysis already noted stretches where API instability blurred the true baseline.

What to do:

- Keep one primary final profile and one fallback profile.
- Compare changes under the same provider/profile before drawing conclusions.
- Monitor no-answer failures separately from logic failures.

## Final Model Strategy

The final profile should be:

- primary model: `claude-sonnet-4-6`
- verifier model: `claude-haiku-4-5`

Why this split:

- Sonnet is the right class for main-loop planning, ambiguity handling, and threat-aware completion decisions.
- Haiku is fast and cheap enough to stay as an independent verifier without doubling main-loop cost.
- The verifier must stay architecturally independent from the main loop so disagreement is meaningful.

What is already in the repo:

- `pac1-py/settings.py` supports primary/verifier role separation.
- `pac1-py/.env.final.example` already documents the Sonnet/Haiku profile.
- `make run-final` and `make task-final` now pin the same profile directly from the Makefile.

## Anti-Overfit Rules For The Team

1. Never encode task IDs, contact names, file names, or known answers into code or prompts.
2. Reject fixes whose only defense is "this helps tNN".
3. Prefer structural improvements in `llm.py`, `agent_loop.py`, `verify.py`, `defend.py`, and the domain abstraction over narrow prompt wording.
4. Require confirmation runs before accepting score gains.
5. Track mean score and variance together. A higher peak with higher variance is not a final-ready improvement.
6. Treat blind-window constraints as primary. If a fix depends on grader feedback detail, it is not final-ready.

## Priority Backlog Before Final

### P0 - Must land before final

1. Real behavioral use of `security_posture`.
2. Semantic stagnation detector and progress scoring.
3. Fallback outcomes based on evidence relevance, not just task type.
4. Completion-time grounding verifier for required references.
5. Final-profile soak runs with Sonnet primary and Haiku verifier.

### P1 - Strongly recommended

1. Activate domain-level classification and strategy contributions instead of leaving them dormant.
2. Add a provider fallback profile and a small canary suite for same-day sanity checks.
3. Track invisible helper RPCs and gate-only loops as separate operational metrics.

### P2 - Nice to have if time remains

1. Cross-run reflection memory for failure families.
2. Better search/list evidence capture.
3. Wider domain plugin prep for tools beyond the filesystem mini benchmark.

## Exit Criteria

We are final-ready when all of the following are true:

- the final model profile is one command away
- recent runs show low variance and near-zero no-answer failures
- no accepted change in the last stretch is justified by a single task
- red-team battery does not show an obvious bypass on new-tool or mixed-capability scenarios
- the team can explain each remaining failure as a general limitation, not as a missing practice-set patch
