# SkillOpt-Inspired PCDRED Architecture Update

**Date**: 2026-05-28
**Status**: Proposed, with Phase 0 evidence export implemented
**Scope**: Adapt Microsoft SkillOpt ideas to BitGN PAC next-challenge preparation without vendoring SkillOpt wholesale.

## 1. Executive Decision

Use SkillOpt as an architecture pattern, not as a direct runtime dependency.

SkillOpt's transferable core is not the benchmark adapters themselves; it is the discipline around treating a compact natural-language skill document as trainable state for a frozen agent. The useful loop is:

1. rollout scored tasks with the current skill;
2. reflect over failure and success minibatches;
3. aggregate overlapping suggestions;
4. clip edits by a textual learning rate;
5. apply bounded skill edits;
6. accept only when validation improves.

For BitGN, this maps cleanly onto our existing PCDRED development loop and `pac1-py/workspace/prompts/` fragments. We should not import the full SkillOpt package yet because its env adapters, dataset format, and model routing are built for its own benchmark suite; BitGN already has a custom harness, VM lifecycle, and security-critical runtime loop.

## 2. What We Should Take

| SkillOpt idea | BitGN adaptation | Why it matters |
|---|---|---|
| Skill document as trainable state | Treat `workspace/prompts/system.md` and fragments as deployable skill artifacts | Keeps inference-time runtime simple: one frozen agent plus better instructions |
| Rollout evidence | Store task text, score, outcome, step/tool trace, verifier verdict in A-Evolve trajectories | Gives the optimizer real behavioral evidence instead of only final scores |
| Failure/success minibatches | Reflect separately over failed and passed task families | Fixes recurring errors while preserving working behavior |
| Bounded edits / learning rate | Limit each candidate to a small number of prompt-fragment edits | Prevents broad prompt rewrites that destroy known-good rules |
| Held-out gate | Accept a prompt candidate only if selection improves and holdout does not regress | Turns prompt mutation into propose-and-test, not self-editing |
| Rejected-edit buffer | Feed rejected prompt changes back into the next reflection prompt | Avoids repeating harmful edits |
| Slow/meta update | End-of-epoch summaries of regressions, improvements, persistent failures | Captures longer-horizon strategy without bloating runtime prompts |

## 3. What We Should Not Take Yet

- Do not vendor `skillopt/engine/trainer.py`: it assumes SkillOpt env adapters, train/val/test item loaders, and its own output tree.
- Do not let an optimizer rewrite Python runtime code as part of the first SkillOpt-style loop. Start with prompt fragments only.
- Do not replace PCDRED. SkillOpt is the optimization layer around PCDRED, not the runtime policy layer.
- Do not train on task IDs or benchmark-specific filenames. The next challenge needs family-level rules.

## 4. Target Architecture

```text
BitGN tasks
   |
   v
PAC runner / A-Evolve adapter
   |
   +--> rollout evidence
        - task_description
        - score and grader detail
        - agent outcome
        - step/tool digest
        - verifier verdict
        - failure_mode
   |
   v
SkillOpt-lite optimizer loop
   |
   +-- Reflect: failure minibatches + success minibatches
   +-- Aggregate: merge duplicated suggestions
   +-- Clip: max 2-4 edits per step
   +-- Apply: prompt fragments only
   +-- Gate: selection improvement + holdout non-regression
   +-- Memory: rejected edits + epoch meta skill
   |
   v
Validated workspace/prompts/
   |
   v
Frozen runtime PCDRED agent
```

## 5. Immediate Phase 0 Change

Implemented now:

- `BitgnAgent.solve()` exports compact rollout evidence into `Trajectory.conversation[0]`.
- `BitgnBenchmarkAdapter.evaluate()` appends task text, agent metrics, verifier verdict, and the first step/tool digests to `Feedback.detail`.

This is intentionally small: it improves the optimizer's visibility without changing runtime behavior inside the BitGN VM.

## 6. Phase 1: Prompt-Only SkillOpt-Lite

Add a local trainer script, separate from `evolve.py`, with this contract:

```bash
cd pac1-py
uv run python skillopt_lite.py --epochs 3 --batch-size 24 --edit-budget 3
```

The first implementation should:

1. use the existing train/holdout split, plus a deterministic selection subset inside train;
2. run only prompt-fragment candidates, not Python mutations;
3. produce JSON patch suggestions with operations `{append, insert_after, replace, delete}`;
4. store outputs under `pac1-py/workspace/skillopt_runs/<run_id>/`;
5. accept candidates only when selection score improves and holdout score is neutral or better;
6. write `best_skill.md` or `best_fragments/` as the deployable artifact.

## 7. Phase 2: Memory And Stability

Add SkillOpt's two stabilizers after the prompt-only loop works:

- **Rejected-edit buffer**: append rejected edits, candidate score, and reason to `rejected_edits.jsonl`; include a compact summary in the next reflection prompt.
- **Slow/meta update**: after each epoch, compare previous accepted prompt set vs current accepted prompt set on the same sampled tasks. Summarize regressions, improvements, persistent failures, and stable successes into an optimizer-only memory file.

The meta memory should guide future edits but should not be injected into the runtime system prompt unless it survives the same gate.

## 8. Gate Policy For The Next Challenge

Candidate acceptance rules:

1. `selection_score > current_selection_score` is required.
2. `holdout_score >= current_holdout_score` is required for prompt changes within 72 hours of a challenge.
3. Any new security false negative is an automatic reject, even if aggregate score improves.
4. Any prompt candidate that mentions task IDs, exact practice-set answers, or one-off filenames is an automatic reject.
5. Maximum prompt diff per accepted step: 4 bounded edits or 1 full-fragment rewrite after a manual review.

## 9. Relationship To Existing PCDRED

PCDRED remains the runtime and development framework:

- PCDRED Runtime: perceive/classify/decide/run/evaluate/defend inside each task.
- PCDRED Development: analyst/architect/red-team/evaluator artifacts around each benchmark run.
- SkillOpt-lite: the optimizer that proposes bounded prompt changes from scored PCDRED trajectories.

In other words: PCDRED is the agent's nervous system; SkillOpt-lite is the training loop for its operating rules.

## 10. References

- SkillOpt project page: https://microsoft.github.io/SkillOpt/
- SkillOpt repository: https://github.com/microsoft/SkillOpt
- arXiv paper: https://arxiv.org/abs/2605.23904
