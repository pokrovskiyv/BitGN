---
title: PCDRED Meta-Model Design
sources:
  - docs/superpowers/specs/2026-03-29-pcdred-meta-model-design.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - spec
  - pcdred
---

# PCDRED Meta-Model Design

> Источник: `docs/superpowers/specs/2026-03-29-pcdred-meta-model-design.md`

## Резюме

Проектная спецификация системы, выигрывающей 1-е место в BitGN Agent Challenge. Формулирует шестифазный когнитивный цикл **PCDRED** (Perceive → Classify → Decide → Run → Evaluate → Defend), применяемый одновременно на двух масштабах: в ходе разработки (Agent Team) и во время исполнения каждой задачи (runtime). Фиксирует декомпозицию pac1-py на специализированные модули и определяет Agent Team из пяти Claude Code-субагентов.

## Ключевые решения

- **Двухуровневый PCDRED**: dev-time и runtime. Одна и та же аббревиатура в двух масштабах — единый словарь для команды и кода.
- **Разделение файлов по фазам**: `classify.py` + `strategy.py` + `defend.py` + `verify.py` + `environment.py` — каждая фаза изолирована для независимого тестирования и A-Evolve-мутации.
- **Advisory-only детекция угроз, не hard-blocking**: `scan_content` выдаёт предупреждения, финальное решение принимает LLM — это минимизирует ложные срабатывания.
- **Rule-based классификация**: микросекунды, ноль стоимости; LLM-fallback только для ambiguous-случаев (в текущей реализации не задействован).
- **Immutable EnvironmentModel**: frozen dataclass, один раз извлекается в Perceive, далее переносится неизменным.
- **Pre-submission verification стоит 1-3 tool-call'а** — принятый trade-off. Ожидаемый impact: +10-15% балла.
- **Red Team как continuous process** — threat-pattern-library растёт с каждым циклом.
- **Six-agent team**: Analyst, Architect, Red Team, Optimizer, Evaluator, позже добавлен Memory Consolidator.
- **Decision protocol**: `new_score > old_score && 0 regressions → COMMIT`; `= → SKIP`; `< → REVERT`.

## Статус реализации

**Большая часть реализована.**

| Элемент | Статус | Где живёт |
|---|---|---|
| `classify.py` + 7 task types | ✅ | [classify](../modules/pac1-py/classify.md) |
| `strategy.py` + таблица | ✅ | [strategy](../modules/pac1-py/strategy.md) |
| `defend.py` + 14 категорий | ✅ | [defend](../modules/pac1-py/defend.md) |
| `verify.py` + gates | ✅ | [verify](../modules/pac1-py/verify.md) |
| `environment.py` + sensitive_paths | ✅ | [environment](../modules/pac1-py/environment.md) |
| Enhanced agent loop (stagnation, budget, threats) | ✅ | [agent_loop](../modules/pac1-py/agent_loop.md) |
| Agent Team (5 агентов) | ✅ | `.claude/agents/` |
| Scratchpad DAG | ✅ | `docs/scratchpad/` |

Пять запланированных фаз timeline (Foundation → Optimization → Hardening → Lock) в целом пройдены, финальная фаза Lock — 10 апреля.

## Связанные компоненты

- [PCDRED Pipeline](../architecture/pcdred-pipeline.md) — runtime-детализация
- [Agent Team](../architecture/agent-team.md) — dev-time реализация
- [Security Model](../architecture/security-model.md) — как Defend встроен в остальные слои
- [PCDRED Concept](../concepts/pcdred.md) — краткое описание
