# Agent Scratchpad Protocol

Shared workspace for inter-agent communication. Each artifact uses YAML frontmatter for machine-readable metadata.

## Artifact Format

Every file in this directory uses this format:

```markdown
---
agent: <analyst|architect|red-team|optimizer|evaluator|variance-reducer>
type: <analysis|fix|attack|optimization|eval|variance>
run_id: <YYYY-MM-DD-HH>
status: <draft|final>
depends_on: []          # list of artifact filenames this depends on
produces: []            # list of files this agent modified
priority_fix: ""        # one-line top priority (analyst/red-team only)
mean_score: null        # numeric score (evaluator only)
verdict: null           # IMPROVED|REGRESSED|NEUTRAL|COMMIT|REVERT (evaluator only)
---
```

## Naming Convention

`{run_id}--{agent}--{type}.md`

Example: `2026-04-01-12--analyst--analysis.md`

## Consumption Rules

- Architect reads analyst artifacts to find fixes
- Red Team reads architect artifacts to find attack surfaces
- Evaluator reads all artifacts to decide commit/revert
- Optimizer reads eval artifacts to find performance bottlenecks
