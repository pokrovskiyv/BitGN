---
title: PCDRED
sources:
  - docs/superpowers/specs/2026-03-29-pcdred-meta-model-design.md
  - pac1-py/agent_loop.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - concept
  - pcdred
---

# PCDRED

## Определение

PCDRED — это шестифазная когнитивная петля, принятая в BitGN-pac1 как **мета-модель** работы агента. Аббревиатура: **Perceive → Classify → Decide → Run → Evaluate → Defend**. Применяется одновременно на двух уровнях:

1. **Runtime** — внутри одного прогона задачи, см. [PCDRED Pipeline](../architecture/pcdred-pipeline.md).
2. **Dev-time** — в цикле разработки агента Agent Team'ом, см. [Agent Team](../architecture/agent-team.md).

## Шесть фаз

| Фаза | Вопрос | Runtime | Dev-time |
|---|---|---|---|
| **P — Perceive** | Что сейчас есть в среде? | `boot_messages` + `extract_environment` | Analyst читает `docs/eval/`, `docs/analysis/` |
| **C — Classify** | Что это за задача/провал? | `classify_task` | Analyst маркирует failure_mode |
| **D — Decide** | Какая минимальная правильная стратегия? | `decide_strategy` → `ExecutionStrategy` | Architect выбирает один smallest-generalizable-diff |
| **R — Run** | Исполнить под охраной | `run_agent_loop` с гейтами, трекером, стагнацией | Architect правит код, Evaluator прогоняет `make run` |
| **E — Evaluate** | Действительно ли сделано правильно? | `pre_completion_gate` + `second_opinion` + `check_criteria` | Evaluator сравнивает task-by-task с предыдущим |
| **D — Defend** | Что может пойти не так? | `scan_content` + action-gate interlock | Red Team генерирует атаки |

## Feedback loop

```
 P ──► C ──► D ──► R ──► E ──► D
 │                              │
 └──────── feedback ◄───────────┘
```

Каждый cycle оставляет артефакт, и следующий cycle смотрит на него. В runtime это история сообщений и `WriteTracker`. В dev-time это `docs/analysis/`, `docs/eval/`, `docs/redteam/`, `docs/optimization/`, связанные через scratchpad-протокол.

## Как это работает в коде

Эта фаза задаётся не только последовательностью вызовов в `agent_loop`, но и **разделением файлов**:

| Фаза | Модуль |
|---|---|
| Perceive | [domain_fs.boot_messages](../modules/pac1-py/domain_fs.md), [environment](../modules/pac1-py/environment.md) |
| Classify | [classify](../modules/pac1-py/classify.md) |
| Decide | [strategy](../modules/pac1-py/strategy.md) |
| Run | [agent_loop](../modules/pac1-py/agent_loop.md), [llm](../modules/pac1-py/llm.md), [domain_fs](../modules/pac1-py/domain_fs.md) |
| Evaluate | [verify](../modules/pac1-py/verify.md), [output_contract](../modules/pac1-py/output_contract.md), [criteria](../modules/pac1-py/criteria.md), [second_opinion](../modules/pac1-py/second_opinion.md) |
| Defend | [defend](../modules/pac1-py/defend.md), action-gate interlock в [agent_loop](../modules/pac1-py/agent_loop.md) |

Разделение намеренное: каждую фазу можно изолированно тестировать и мутировать через A-Evolve.

## См. также

- [PCDRED Pipeline](../architecture/pcdred-pipeline.md)
- [Agent Team](../architecture/agent-team.md)
- [PCDRED Meta-Model Spec](../specs/pcdred-meta-model.md)
