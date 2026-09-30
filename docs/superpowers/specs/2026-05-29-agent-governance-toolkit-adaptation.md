# Agent Governance Toolkit adaptation for BitGN ECOM

**Date:** 2026-05-29
**Source:** `microsoft/agent-governance-toolkit` at `6572fd0`
**Decision:** adopt AGT patterns, not the full dependency stack for the benchmark agent.

## What AGT contributes

AGT's strongest idea for BitGN is deterministic action governance: the LLM may
propose an action, but application code evaluates policy before the action can
reach the runtime. This matches our existing action gates, but makes the design
more explicit and testable.

Useful concepts:

1. **Deterministic pre-tool policy.** Runtime allow/deny must be code/policy,
   not another LLM call. This is especially relevant for ECOM actions such as
   checkout, refund, discount, 3DS recovery, and `/bin/sql`.
2. **Fail closed.** If policy evaluation errors, block the action and ask the
   agent to report a safe outcome or collect new evidence.
3. **Decision/audit record.** For every risky dispatch, record action, args
   digest, matched policy, decision, and later outcome. This gives PCDRED and
   SkillOpt cleaner trajectories than free-form logs.
4. **PromptDefense static check.** The AGT prompt scanner is lightweight enough
   to run against our prompt fragments during preflight.
5. **Decision BOM view.** Reconstruct why a run allowed or denied an action
   from existing traces, instead of asking the agent to self-report.

## What not to import wholesale

Do not add `agentmesh_platform` / full AGT as a runtime dependency for the
competition loop yet. It brings identity, mesh, crypto, server, and compliance
machinery that is valuable for production systems but too heavy for the
single-process benchmark agent. It also supports Python >=3.11 while this repo
runs Python 3.14 via `uv`, so compatibility is plausible but not worth adding
on the critical path.

## Concrete BitGN adaptation

### P0: prompt hardening

Ran AGT `PromptDefenseEvaluator` against
`pac1-py/workspace/prompts/system.md`.

- Before patch: `C`, score `50`, coverage `6/12`.
- After compact prompt patch: `A`, score `100`, coverage `12/12`.

The patch adds explicit language for data leakage, multilingual bypass,
unicode/encoding attacks, indirect injection, social engineering, harmful
workflows, and input validation.

### P1: policy gate module

Add a small local module rather than AGT dependency:

```python
Decision = allow | warn | deny
evaluate_tool_policy(task_text, domain_name, cmd, env_model, tracker) -> Decision
```

Initial rules should be narrow and deterministic:

- deny writes/deletes to `AGENTS.md`, `.env`, credentials, and hidden control
  paths unless the original task explicitly names them;
- deny `/bin/sql` statements containing destructive SQL verbs (`insert`,
  `update`, `delete`, `drop`, `alter`, `truncate`, `create`);
- warn on any ECOM `exec` outside known safe helpers until AGENTS/runtime docs
  prove it is an intended action helper;
- deny retries of a previously denied high-risk action unless new evidence was
  consulted.

This complements existing `RiskLevel` gates: `RiskLevel` warns the model;
policy gate makes unsafe dispatch structurally impossible.

### P2: audit trace for optimization

Extend `steps_detail` with policy fields:

```json
{
  "policy_decision": "allow|warn|deny",
  "policy_rule": "ecom-sql-readonly",
  "policy_reason": "...",
  "args_hash": "sha256:..."
}
```

This gives A-Evolve/SkillOpt failure analysis a crisp signal:
`model wanted unsafe action` versus `policy overblocked legitimate task`.

### P3: preflight check

Add a Make target later:

```bash
make prompt-defense
```

It can run a local copy of the deterministic scanner or a repo-native
equivalent. Do not require network or AGT installation in the hot path.

## Expected benefit for ECOM

The ECOM task set contains many policy-source authority traps: cross-customer
checkout, unauthorised discount issuers, social-pressure refunds, 3DS recovery,
archived fraud review, and SQL/catalogue lookup. AGT's core model maps cleanly:
the model can reason about what it wants to do, but checkout/refund/discount/SQL
actions need a deterministic pre-dispatch rule boundary.
