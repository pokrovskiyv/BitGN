---
title: Domain Plugin Architecture (спецификация)
sources:
  - docs/superpowers/specs/2026-03-30-domain-plugin-architecture.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - spec
  - architecture
  - plugin
---

# Domain Plugin Architecture

> Источник: `docs/superpowers/specs/2026-03-30-domain-plugin-architecture.md`

## Резюме

Спецификация pluggable-архитектуры, позволяющей одному обобщённому `agent_loop` работать поверх разных доменов: файловой системы, мессенджера, календаря, email-инбокса, браузера. Цель — устранить дублирование между `pac1-py` и `sandbox-py` и сделать добавление нового домена одним файлом, а не копированием всего `agent.py`.

## Ключевые решения

- **ADR-1: `typing.Protocol` вместо ABC.** Структурное подтипирование — без зависимостей между доменными модулями. `@runtime_checkable` для safety.
- **ADR-2: Dict-based tool registry** вместо `isinstance`-цепочек. Добавление tool'а = одна запись в словарь.
- **ADR-3: Динамический Pydantic union** из реестра. Сохраняет structured output и JSON Schema для LLM.
- **ADR-4: Синхронное polling для реактивных доменов.** `run_agent()` остаётся синхронным (инвариант A-Evolve), а реактивные домены поддерживаются через `poll_events()`.
- **ADR-5: Открытый `str` для task_type** вместо `Literal` union — домены добавляют типы без правки общих типов.
- **ADR-6: Frozen dataclass tuples** для ThreatProfile — immutable, хэш-safe, согласуется с уже принятым в коде паттерном.

## Пятифазный план миграции

1. **Extract shared agent loop** → `agent_loop.py` (~120 строк), параметризованный `DomainProtocol`.
2. **Create filesystem domain** → `domain_fs.py` (~180 строк), перенос всех `Req_*` моделей и форматтеров.
3. **Thin out agent.py** → 15 строк: обёртка вокруг `run_agent_loop` + `FilesystemDomain()`.
4. **Create sandbox domain** (optional, отдельный PR) → `domain_mini.py` в sandbox-py.
5. **Parameterize classify/strategy/defend** — домены контрибутят свои `classification_rules`, `strategy_entries`, `threat_profile`.

## Статус

**Фазы 1-3 реализованы.**

| Фаза | Статус | Примечание |
|---|---|---|
| Phase 1 — shared agent_loop | ✅ | [agent_loop.py](../modules/pac1-py/agent_loop.md) |
| Phase 2 — FilesystemDomain | ✅ | [domain_fs.py](../modules/pac1-py/domain_fs.md) |
| Phase 3 — thin agent.py | ✅ | [agent.py](../modules/pac1-py/agent.md) |
| Phase 4 — sandbox domain | ⚪ | Не сделано — sandbox-py остался плоским, это осознанное решение до появления второго реального домена |
| Phase 5 — parameterize classify/strategy/defend | ⚪ | Частично: `FilesystemDomain.threat_profile = None`, `classification_rules = ()`, `strategy_entries = ()` — логика пока живёт в модуль-уровне для скорости разработки |

## A-Evolve совместимость (проверено)

| Constraint | Сохранён? | Как |
|---|---|---|
| Сигнатура `run_agent(model, harness_url, task_text)` | Да | Тонкая обёртка в `agent.py` |
| `workspace/` на старом пути | Да | Путь не менялся |
| Fragment hot-reload | Да | `_load()` перечитывает файлы при каждом `decide_strategy` |
| `Trajectory.conversation[0]` schema | Да | `bitgn_agent.py` не трогали |
| Flat project (`package = false`) | Да | Все новые файлы в корне `pac1-py/` |

## Связанные компоненты

- [Domain Plugin Architecture view](../architecture/domain-plugin-architecture.md)
- [domain_protocol](../modules/pac1-py/domain_protocol.md)
- [domain_fs](../modules/pac1-py/domain_fs.md)
- [Risk Levels](../concepts/risk-levels.md)
