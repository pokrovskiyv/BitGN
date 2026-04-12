---
title: Code Wiki — главный индекс
last_updated: 2026-04-11T14:00:00Z
tags:
  - index
  - code
---

# Code Wiki — главный индекс

Это корневой файл **LLM-составляемой** части `docs/wiki/` — документация кода, архитектуры, концепций и спецификаций BitGN. Отдельно от Python-compiled части (`index.md`, `scoreboard.md`, `tasks/*`, ...), которую собирает `compile_wiki.py` из runtime-данных.

> **Важно:** этот файл называется `code-index.md`, а не `index.md`, потому что `index.md` принадлежит `compile_wiki.py`. См. [Knowledge Wiki](architecture/knowledge-wiki.md) про политику совместного владения `docs/wiki/`.

## О проекте

**BitGN** — платформа бенчмарков и соревнований для персональных ИИ-агентов. Этот репозиторий содержит два образцовых Python-агента для BitGN Agent Challenge (PAC — Personal & Trustworthy). Соревнование: **11 апреля 2026**. Два реализованных агента:

- **pac1-py** — основной агент: полный PCDRED-пайплайн, Domain Plugin Architecture, интеграция с A-Evolve, 22 Python-модуля.
- **sandbox-py** — минималистичный агент для sandbox/mini-окружения, 2 файла.

Полная карта архитектуры: [architecture/overview.md](architecture/overview.md).

## Разделы

| Раздел | Описание | Файлов |
|---|---|---|
| [Архитектура](#архитектура) | Cross-cutting системные представления | 8 |
| [Модули pac1-py](#модули-pac1-py) | Один файл на Python-модуль | 22 |
| [Модули sandbox-py](#модули-sandbox-py) | Один файл на Python-модуль | 2 |
| [Концепции](#концепции) | Доменные понятия | 9 |
| [Спецификации](#спецификации) | Сводки design-specs | 6 |
| [Глоссарий](glossary.md) | Термины и аббревиатуры | 1 |

## Архитектура

- [Обзор](architecture/overview.md) — карта репозитория, принципы, связи компонентов
- [PCDRED-пайплайн](architecture/pcdred-pipeline.md) — runtime-реализация шести фаз
- [Domain Plugin Architecture](architecture/domain-plugin-architecture.md) — DomainProtocol и плагинная схема
- [LLM-бэкенды](architecture/llm-backends.md) — Nebius / OpenRouter / Anthropic + prompt caching
- [Agent Team](architecture/agent-team.md) — 6 субагентов PCDRED dev-цикла
- [Интеграция A-Evolve](architecture/a-evolve-integration.md) — циклы мутаций workspace/
- [Модель безопасности](architecture/security-model.md) — 7 слоёв защиты
- [Knowledge Wiki](architecture/knowledge-wiki.md) — две системы документации в одной директории

## Модули pac1-py

Основной агент, разбитый на единицы с одной ответственностью (< 200 строк каждая):

- [agent](modules/pac1-py/agent.md) — тонкая обёртка → run_agent_loop
- [agent_loop](modules/pac1-py/agent_loop.md) — универсальный PCDRED-цикл
- [domain_protocol](modules/pac1-py/domain_protocol.md) — интерфейс плагина
- [domain_fs](modules/pac1-py/domain_fs.md) — файловый домен (11 инструментов)
- [classify](modules/pac1-py/classify.md) — rule-based классификация задач
- [strategy](modules/pac1-py/strategy.md) — выбор бюджета и сборка промпта
- [llm](modules/pac1-py/llm.md) — LLM-бэкенды + recovery
- [defend](modules/pac1-py/defend.md) — сканер угроз + wrap_tool_output
- [verify](modules/pac1-py/verify.md) — WriteTracker, StagnationDetector, pre_completion_gate
- [environment](modules/pac1-py/environment.md) — парсинг AGENTS.md
- [output_contract](modules/pac1-py/output_contract.md) — извлечение и проверка формата ответа
- [criteria](modules/pac1-py/criteria.md) — ISC-style извлечение критериев
- [hints](modules/pac1-py/hints.md) — контекстные подсказки для write-гейтов
- [second_opinion](modules/pac1-py/second_opinion.md) — независимый Claude-верификатор
- [main](modules/pac1-py/main.md) — CLI-оркестратор бенчмарка
- [settings](modules/pac1-py/settings.md) — RuntimeSettings (dev/final)
- [bitgn_client](modules/pac1-py/bitgn_client.md) — фабрики клиентов + API-ключ
- [bitgn_agent](modules/pac1-py/bitgn_agent.md) — BaseAgent для A-Evolve
- [bitgn_benchmark](modules/pac1-py/bitgn_benchmark.md) — BenchmarkAdapter для A-Evolve
- [evolve](modules/pac1-py/evolve.md) — CLI для эволюционного прогона
- [sample_tasks](modules/pac1-py/sample_tasks.md) — reconnaissance по blind-бенчмарку
- [synthetic_gauntlet](modules/pac1-py/synthetic_gauntlet.md) — локальный offline-бенчмарк готовности

## Модули sandbox-py

- [sandbox agent](modules/sandbox-py/agent.md) — весь агент в одном файле
- [sandbox main](modules/sandbox-py/main.md) — runner для `bitgn/sandbox`

## Концепции

Доменные идеи, повторяющиеся по всему коду:

- [PCDRED](concepts/pcdred.md) — шесть фаз как мета-модель
- [Prompt injection и семейства атак](concepts/threat-injection.md) — 14 категорий + Unicode-evasion
- [Классификация задач](concepts/task-classification.md) — семь классов и их бюджеты
- [Уровни риска инструментов](concepts/risk-levels.md) — low/medium/high + interlock
- [Детекция стагнации](concepts/stagnation-detection.md) — repeat/oscillation/semantic
- [Read-after-write](concepts/read-after-write.md) — почему каждая запись проверяется чтением
- [Коды исходов](concepts/outcome-codes.md) — пять OUTCOME_* и дерево решений
- [Иерархия инструкций](concepts/instruction-hierarchy.md) — TRUST HIERARCHY из system.md
- [Scoring](concepts/scoring.md) — как начисляются баллы бенчмарком

## Спецификации

Сводки ключевых design-документов из `docs/superpowers/specs/` и `docs/`:

- [PCDRED Meta-Model Spec](specs/pcdred-meta-model.md) — главная спецификация шести фаз
- [Domain Plugin Spec](specs/domain-plugin.md) — спецификация плагинной архитектуры
- [Dashboard Redesign](specs/dashboard-redesign.md) — three-layer Streamlit-дашборд
- [Variance-Reducer Spec](specs/variance-reducer.md) — measurement + phantom-agent review
- [SoTA Analysis](specs/sota-analysis.md) — gap assessment против SoTA
- [Handbook](specs/handbook.md) — канонические правила BitGN PAC

## Решения (ADR)

Каталог [decisions/](decisions) пока пуст — ADR-ы будут появляться по мере принятия новых архитектурных решений после финала.

## См. также

- [Глоссарий терминов](glossary.md)
- [Python-compiled wiki `index.md`](index.md) — runtime-данные (score, tasks, fix-registry, vulnerability-catalog, health)
