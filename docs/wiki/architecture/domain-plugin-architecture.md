---
title: Domain Plugin Architecture
sources:
  - pac1-py/domain_protocol.py
  - pac1-py/domain_fs.py
  - pac1-py/agent_loop.py
  - pac1-py/agent.py
  - docs/superpowers/specs/2026-03-30-domain-plugin-architecture.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - architecture
  - plugin
  - protocol
---

# Domain Plugin Architecture

Чтобы одинаковым агентским циклом можно было поверх разных поверхностей (файловая система, мессенджер, календарь, браузер), BitGN-pac1 разделён на два уровня: универсальный `agent_loop` и набор доменных плагинов, соответствующих `DomainProtocol`. В текущем коде реализован один домен — `FilesystemDomain`.

## Компоненты

| Слой | Модуль | Роль |
|---|---|---|
| Универсальный цикл | [agent_loop](../modules/pac1-py/agent_loop.md) | PCDRED-цикл, ничего не знающий про конкретные инструменты |
| Контракт домена | [domain_protocol](../modules/pac1-py/domain_protocol.md) | `DomainProtocol`, `ToolHandler`, `RiskLevel`, `ThreatProfile`, `LoopMode` |
| Файловый домен | [domain_fs](../modules/pac1-py/domain_fs.md) | `FilesystemDomain`: 11 инструментов, Unix-форматтеры, boot-последовательность |
| Тонкая обёртка | [agent](../modules/pac1-py/agent.md) | Склеивает `run_agent_loop` + `FilesystemDomain` и сохраняет историческую сигнатуру `run_agent(...)` |

## Поток вызова

```
bitgn_agent.solve(task)
       │
       ▼
agent.run_agent(model, harness_url, task_text)
       │
       ▼
agent_loop.run_agent_loop(model, harness_url, task_text, domain=_domain)
       │                                                    │
       │                                                    ▼
       │                                    FilesystemDomain (domain_fs.py)
       │                                                    │
       ▼                                                    │
  call_llm(...)                                             │
       │                                                    │
       ▼                                                    │
  NextStep.function = Req_Read(path="...")                  │
       │                                                    │
       └────────── domain.dispatch(client, cmd) ────────────┘
                                │
                                ▼
                      handler = domain.tool_registry[cmd.tool]
                                │
                                ▼
                      handler.execute(client, cmd)
                                │
                                ▼
                      result → handler.format(cmd, result) → str
```

## Ключевые архитектурные решения

### ADR-1: `typing.Protocol` вместо ABC

Структурное подтипирование. У pac1-py и sandbox-py нет общего базового модуля (flat-project constraint, `package = false`), поэтому импортировать общий `DomainBase` некуда. `Protocol` позволяет каждому агенту объявить свой домен независимо. `@runtime_checkable` даёт минимальную проверку совместимости во время инициализации.

### ADR-2: dict-based tool registry вместо isinstance-цепочек

До рефакторинга `dispatch` был 11-ветвевым `isinstance`-чейном. Сейчас — `TOOL_REGISTRY: dict[str, ToolHandler]`. Добавление нового инструмента = одна запись в словарь, никакой модификации диспетчера. Exception за неизвестный инструмент: `ValueError(f"Unknown tool: {tool_name}")`.

### ADR-3: Pydantic union с дискриминатором `tool`

`NextStep.function` — это union из всех `Req_*` плюс `ReportTaskCompletion`. LLM получает полный JSON Schema и обязан эмитить валидный tool call. Дискриминатор `propertyName="tool"` добавляется в схему перед отправкой в Nebius/OpenRouter, чтобы API корректно валидировало тип по полю.

### ADR-4: синхронное polling для реактивных доменов

`run_agent(model, harness_url, task_text)` — синхронный вызов, потому что `bitgn_agent.solve()` (A-Evolve) ожидает такую сигнатуру. Реактивные домены (мессенджер) поддерживаются через `DomainProtocol.poll_events(client) -> list[dict] | None`: вместо stream'а — короткие опросы. В текущей реализации `FilesystemDomain.poll_events` всегда возвращает `None` (batch-режим).

### ADR-5: строки вместо `Literal` для task_type

`classify.py` пользуется `Literal`-union'ом из семи классов, но в `DomainProtocol.classification_rules` тип — открытая строка. Это нужно, чтобы новый домен мог регистрировать новые классы задач («channel_management», «contact_merge») без правки общего типа.

### ADR-6: frozen tuples в ThreatProfile

`ThreatProfile` — `frozen dataclass` с tuples (`patterns: tuple[ThreatPattern, ...]`, `protected_resources: tuple[str, ...]`). Это согласуется с уже принятым в коде паттерном (`TaskClassification`, `ExecutionStrategy` тоже `frozen=True`). Tuples вместо списков нужны, чтобы frozen dataclass был hashable и безопасно передавался между потоками.

## Текущее состояние

- `FilesystemDomain.threat_profile = None` — defend.py пока использует свои модуль-уровневые `THREAT_PATTERNS`, не доменные. Это запланированная миграция из Phase 5 спецификации.
- `classification_rules = ()` и `strategy_entries = ()` — `classify.py` и `strategy.py` тоже пока хранят свои правила локально.
- sandbox-py не использует DomainProtocol — архитектура дизайн-only для простой mini-песочницы, и даёт больше пользы тогда, когда появится второй реальный домен (мессенджер / календарь).

## Будущий пример: MessengerDomain

В спецификации описан гипотетический `MessengerDomain` с инструментами `send_message`, `read_channel`, `list_channels`. Его `ThreatProfile` содержит `impersonation`, `mass_send`, `unauthorized_read` паттерны; `classification_rules` регистрирует `channel_mgmt` и `message_search`; `loop_mode = LoopMode(kind="reactive", poll_interval_ms=500)`. Всё это добавляется как единый новый файл без правки `agent_loop` или других существующих доменов.

## A-Evolve совместимость

Все пять констрейнтов A-Evolve сохранены:

1. Сигнатура `run_agent(model, harness_url, task_text)` — `agent.py` остаётся тонкой обёрткой.
2. `workspace/` на старом месте (`pac1-py/workspace/`).
3. Fragment-файлы перечитываются свежо при каждом `decide_strategy` — мутации A-Evolve применяются без рестарта.
4. `Trajectory.conversation[0]` schema не меняется.
5. Flat project (`package = false`) — все новые файлы в корне `pac1-py/`.

## См. также

- [domain_protocol](../modules/pac1-py/domain_protocol.md)
- [domain_fs](../modules/pac1-py/domain_fs.md)
- [agent_loop](../modules/pac1-py/agent_loop.md)
- [Domain Plugin Spec](../specs/domain-plugin.md)
- [Risk Levels](../concepts/risk-levels.md)
