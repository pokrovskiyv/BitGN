---
title: agent — точка входа pac1-py
sources:
  - pac1-py/agent.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - entrypoint
---

# agent

> Источник: `pac1-py/agent.py`

## Назначение

Тонкая обёртка над [agent_loop](agent_loop.md), сохраняющая историческую сигнатуру `run_agent(model, harness_url, task_text)`. Вся доменная логика вынесена в [domain_fs](domain_fs.md), а универсальный цикл — в [agent_loop](agent_loop.md). Этот файл существует ради обратной совместимости: `bitgn_agent.py`, `main.py` и `evolve.py` импортируют именно `from agent import run_agent`.

## Интерфейс

| Функция | Сигнатура | Описание |
|---|---|---|
| `run_agent` | `(model: str, harness_url: str, task_text: str) -> AgentResult` | Создаёт единичный экземпляр `FilesystemDomain` и проксирует вызов в `run_agent_loop()` |

На уровне модуля объявляется константа `_domain = FilesystemDomain()` — один инстанс на весь процесс, состояние не мутируется.

## Зависимости

**Импорты:** `AgentResult` и `run_agent_loop` из `agent_loop`, `FilesystemDomain` из `domain_fs`.

**Импортируют:** `bitgn_agent.py`, `main.py`, `evolve.py`.

## См. также

- [agent_loop](agent_loop.md) — обобщённый PCDRED-цикл
- [domain_fs](domain_fs.md) — реализация доменного плагина для файловой системы
- [Domain Plugin Architecture](../../architecture/domain-plugin-architecture.md) — почему тонкая обёртка, а не монолит
