---
title: SoTA Analysis — Gap Assessment
sources:
  - docs/sota-analysis.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - spec
  - sota
  - analysis
---

# SoTA Analysis — PCDRED Design Gap Assessment

> Источник: `docs/sota-analysis.md`

## Резюме

Активный документ (обновляется после каждой PCDRED-итерации), сопоставляющий текущий дизайн pac1-py с state-of-the-art паттернами в литературе и конкурирующих бенчмарках. Выступает входом для Architect, Red Team и Optimizer агентов: «где мы уже SoTA-aligned?», «где gap?», «какая расстановка приоритетов закрытия gap'ов?».

## Ключевые решения

### Design strengths (уже SoTA-aligned)

| Элемент | SoTA-источник |
|---|---|
| NextStep union-discriminated structured output | SWE-Agent, WebArena winners |
| Auto-init reconnaissance (tree, AGENTS.md, context) | Универсальный паттерн соревнований |
| Advisory-only threat detection | InjecAgent benchmark |
| Rule-based classification | AgentBench analysis |
| Immutable EnvironmentModel | Functional agent patterns |
| Red Team как continuous process | Iterative adversarial training |
| Unix-style output formatting | Spotlighting (Microsoft 2024) |

### Implementation gaps (к моменту написания)

Топ-13 gap'ов, отсортированных по impact:

| Gap | Impact | SoTA-рекомендация |
|---|---|---|
| System prompt — 3 строки | Critical | Full instruction hierarchy with data/instruction boundary |
| Tool outputs не обёрнуты | Critical | Delimiter markers + post-output reminders |
| Нет read-after-write | Critical | Auto re-read после каждого `Req_Write` |
| Всего 6 threat-паттернов | High | 20+ паттернов с base64 decode-and-rescan |
| Stagnation threshold = 3 | High | Detect at 2 + oscillation + semantic |
| Нет fast-path для simple tasks | High | 5-step pipeline для простого CRUD |
| Нет action-gating | High | Inject verification перед destructive ops |
| Error formatting raw | High | Include recovery hints |
| Нет constraint extraction | Medium | Parse task в structured constraint list |
| Нет tree-diff side-effect check | Medium | Snapshot tree до/после |
| Нет cross-run reflections | Medium | Reflexion pattern |
| Нет prompt composition | Medium | Base + category addendum + security |
| Нет few-shot examples | Medium | 2-3 solved примера на категорию |

## Приоритеты P0

Из P0-списка («Must Fix» в Phase 1):

### P0.1 Harden system prompt

**Impact**: +15-25% total score
**Basis**: Instruction Hierarchy (OpenAI, 2024, arXiv:2404.13208) — +63% robustness
**Элементы**: privilege hierarchy, explicit rejection rules, AGENTS.md anchoring, forbidden actions list, outcome code guidance

### P0.2 Delimiter wrapping of tool outputs

**Impact**: +10-15% total score
**Basis**: Spotlighting (Microsoft 2024, arXiv:2403.14720), InjecAgent
**Implementation**: `wrap_tool_output` добавляет `[FILE DATA]` + post-output reminder. -60% compliance с <1% false positive rate

## Статус

Большинство P0-фиксов реализовано:

| Фикс | Статус | Модуль |
|---|---|---|
| P0.1 System prompt | ✅ | [system.md](../../pac1-py/workspace/prompts/system.md) — TRUST HIERARCHY + CRITICAL SECURITY RULES |
| P0.2 Delimiter wrapping | ✅ | [defend.wrap_tool_output](../modules/pac1-py/defend.md) |
| Read-after-write | ✅ | [verify.WriteTracker](../modules/pac1-py/verify.md) + pre_submit_verification |
| 20+ threat-паттернов | ✅ | [defend.THREAT_PATTERNS](../modules/pac1-py/defend.md) — 14 категорий × ~50 regex'ов |
| Stagnation @ 2 + oscillation + semantic | ✅ | [verify.StagnationDetector](../modules/pac1-py/verify.md) |
| Action-gating | ✅ | [agent_loop](../modules/pac1-py/agent_loop.md) — MEDIUM/HIGH gates + interlock |
| Error formatting с hints | ✅ | `agent_loop` ловит `ConnectError` и добавляет «use tree/find» на `not_found` |
| Prompt composition | ✅ | [strategy](../modules/pac1-py/strategy.md) — base + task-addon + outcomes + reasoning + security |

Gap'ы, которые не закрыты целенаправленно:

- Constraint extraction из task (частично закрыто через [criteria](../modules/pac1-py/criteria.md) и `target_hints`).
- Tree-diff side-effect check (оставлено ради простоты).
- Cross-run reflections / Reflexion (не применимо — VM изолированы).
- Few-shot examples с решёнными ответами (запрещены anti-overfit правилами Architect).

## Связанные компоненты

- [PCDRED Pipeline](../architecture/pcdred-pipeline.md)
- [Security Model](../architecture/security-model.md)
- [Agent Team](../architecture/agent-team.md)
- [Scoring](../concepts/scoring.md)
