# PCDRED Implementation Plan — Overview

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the pac1-py agent from a flat 431-line script into a modular PCDRED pipeline that maximizes the BitGN PAC competition score on April 11, 2026.

**Architecture:** Decompose `agent.py` into 5 focused modules (classify, strategy, defend, verify + agent core) while preserving the working dispatch/LLM infrastructure. Each module maps to a PCDRED phase. Changes are applied incrementally with benchmark verification after each phase.

**Tech Stack:** Python 3.14+, Pydantic v2, Protobuf/ConnectRPC (bitgn SDK), Anthropic SDK, `uv` package manager.

**Verification:** No test framework. All verification via benchmark runs: `cd pac1-py && make run` (full) or `make task TASKS='t01 t03'` (targeted). Scores are deterministic.

---

## Plan Parts

| Part | File | Content | Timeline |
|------|------|---------|----------|
| **Overview** | `00-plan-overview.md` (this file) | Reference docs, mappings, file structure, exit criteria | — |
| **Part 1** | [`01-plan-baseline.md`](01-plan-baseline.md) | Phase 0: baseline benchmark + Agent Team | Mar 29 |
| **Part 2** | [`02-plan-architecture.md`](02-plan-architecture.md) | Phase 1: 4 new modules + pipeline wiring | Mar 30-31 |
| **Part 3** | [`03-plan-cycles.md`](03-plan-cycles.md) | Phase 2-3: benchmark validation + PCDRED iteration cycles | Apr 1-8 |
| **Part 4** | [`04-plan-hardening.md`](04-plan-hardening.md) | Phase 4-5: Red Team marathon, regression, freeze, lock | Apr 9-10 |

---

## Reference Documents

Read these before starting any task. They contain the design rationale and research backing for every decision in this plan.

| Document | Path | What It Provides |
|----------|------|-----------------|
| **PCDRED Meta-Model Spec** | `docs/superpowers/specs/2026-03-29-pcdred-meta-model-design.md` | Architecture, runtime pipeline (Section 4), scoring model (Section 5), timeline (Section 6), risk factors (Section 9) |
| **SoTA Gap Analysis** | `docs/sota-analysis.md` | Prioritized changes (P0-P3), expanded threat patterns (Section 3), key papers with arXiv IDs (Section 4) |
| **Competition Handbook** | `docs/challenge/handbook.md` | Scoring rules, penalty categories, trustworthiness rubric |
| **Agent Team Definitions** | `agents/*.md` | Role, trigger, input/output format for each PCDRED development agent |
| **CLAUDE.md** | `CLAUDE.md` | Key Design Principles, build commands, environment variables |

---

## How This Plan Maps to the Meta-Model

| Meta-Model Section | Plan Task | Module Created | Plan Part |
|-------------------|-----------|----------------|-----------|
| Section 4.2 — Perceive (EnvironmentModel) | Task 1.5 (pipeline wiring) | `agent.py` (auto-init preserved + wrapped) | [Part 2](02-plan-architecture.md) |
| Section 4.3 — Classify (TaskClassification) | Task 1.2 | `classify.py` | [Part 2](02-plan-architecture.md) |
| Section 4.4 — Decide (ExecutionStrategy) | Task 1.3 | `strategy.py` | [Part 2](02-plan-architecture.md) |
| Section 4.5 — Run (enhanced loop) | Task 1.5 | `agent.py` (refactored `run_agent()`) | [Part 2](02-plan-architecture.md) |
| Section 4.6 — Evaluate (pre-submit verify) | Task 1.4 | `verify.py` | [Part 2](02-plan-architecture.md) |
| Section 4.7 — Defend (threat monitoring) | Task 1.1 | `defend.py` | [Part 2](02-plan-architecture.md) |
| Section 5 — Scoring Maximization | SoTA P0.1-P0.3 | `strategy.py`, `defend.py`, `verify.py` | [Part 2](02-plan-architecture.md) |
| Section 3 — Agent Team | Task 0.2 | `agents/*.md` | [Part 1](01-plan-baseline.md) |
| Section 3.6 — Iteration Cycle | Task 2.2, 3.1 | Development-time PCDRED loop | [Part 3](03-plan-cycles.md) |
| Section 6 — Timeline | Phases 0-5 | Aligned with spec Phases 1-4 | All parts |

---

## How This Plan Maps to SoTA Findings

| SoTA Priority | Research Basis | Plan Task | Plan Part |
|---------------|---------------|-----------|-----------|
| P0.1 System prompt hardening | Instruction Hierarchy (arXiv:2404.13208): +63% robustness | Task 1.3 (`strategy.py` — `_BASE_PROMPT`) | [Part 2](02-plan-architecture.md) |
| P0.2 Delimiter wrapping | Spotlighting (arXiv:2403.14720): -20% ASR; Remind-and-Delimit: -60% compliance | Task 1.1 (`defend.py` — `wrap_tool_output()`) | [Part 2](02-plan-architecture.md) |
| P0.3 Read-after-write | Huang et al. (arXiv:2310.01798): LLMs cannot self-correct without external signals | Task 1.4 (`verify.py` — `WriteTracker`) | [Part 2](02-plan-architecture.md) |
| P1.1 Expanded threat patterns | OWASP LLM Top 10 v2025, AgentDojo (arXiv:2406.13352) | Task 1.1 (`defend.py` — 30+ patterns) | [Part 2](02-plan-architecture.md) |
| P1.2 Stagnation at 2 reps | LATS (arXiv:2310.04406), AdaPlanner (arXiv:2305.16653) | Task 1.4 (`verify.py` — `StagnationDetector`) | [Part 2](02-plan-architecture.md) |
| P1.3 Fast path for CRUD | Agentless (arXiv:2407.01489): pipeline beats loop for simple tasks | Task 1.3 (`strategy.py` — reduced max_steps) | [Part 2](02-plan-architecture.md) |
| P1.4 Action-gating | InjecAgent: destructive-action defense | Task 1.4 (`verify.py` — `action_gate_message()`) | [Part 2](02-plan-architecture.md) |
| P2.1-P2.4 Medium-impact changes | CoVe (arXiv:2309.11495), Reflexion (arXiv:2303.11366), DSPy (arXiv:2310.03714) | Task 3.2 | [Part 3](03-plan-cycles.md) |

---

## File Structure (target)

```
pac1-py/
├── agent.py       # PCDRED runtime loop, dispatch, LLM backends, output formatting
├── classify.py    # TaskClassification model + classify_task()
├── strategy.py    # ExecutionStrategy model + prompt variants + decide_strategy()
├── defend.py      # THREAT_PATTERNS, scan_content(), scan_for_encoded_threats()
├── verify.py      # pre_submit_verify(), read_after_write(), tree_diff()
├── main.py        # Entry point (unchanged)
├── Makefile       # (unchanged)
└── pyproject.toml # (unchanged)
```

Each new module is < 200 lines, single responsibility, independently readable.

---

## Exit Criteria Summary

| Phase | Part | Exit Criteria |
|-------|------|---------------|
| Phase 0 | [Part 1](01-plan-baseline.md) | Baseline captured. Agent Team operational. |
| Phase 1 | [Part 2](02-plan-architecture.md) | All 4 modules created. agent.py refactored. Agent loads and runs. |
| Phase 2 | [Part 3](03-plan-cycles.md) | Full benchmark passed. First PCDRED cycle completed. Score >= baseline. |
| Phase 3 | [Part 3](03-plan-cycles.md) | 2-4 cycles per day. Score trending upward. P2 changes integrated. |
| Phase 4 | [Part 4](04-plan-hardening.md) | 45+ attacks tested. Zero BYPASSES. 3 consistent runs. Prompts frozen. |
| Phase 5 | [Part 4](04-plan-hardening.md) | 3 consistent runs. Environment verified. Tagged v1.0-competition. |
