---
title: Обзор архитектуры BitGN
sources:
  - CLAUDE.md
  - pac1-py/CLAUDE.md
  - sandbox-py/CLAUDE.md
  - pac1-py/pyproject.toml
  - sandbox-py/pyproject.toml
last_updated: 2026-04-11T14:00:00Z
tags:
  - architecture
  - overview
---

# Обзор архитектуры BitGN

BitGN — платформа бенчмарков и соревнований для персональных ИИ-агентов. Этот репозиторий содержит два независимых образцовых агента для BitGN Agent Challenge (PAC — Personal & Trustworthy). Дата соревнования: **11 апреля 2026**.

## Два агента, один каркас

| Агент | Назначение | Компоненты |
|---|---|---|
| [pac1-py](../modules/pac1-py/agent.md) | Основной агент для PAC1-бенчмарка | Полный PCDRED-пайплайн, 11 инструментов, A-Evolve-интеграция |
| [sandbox-py](../modules/sandbox-py/agent.md) | Простой агент для sandbox/mini | 7 инструментов, 30-шаговый хардкод-цикл, без PCDRED |

Оба проекта — плоские runnable-«sample»-директории. `pyproject.toml` содержит `package = false`, никаких вложенных пакетов, никакой packaging-церемонии. Каждый файл < 200 строк, одна ответственность — см. AICODE-NOTE-комментарии в `pyproject.toml`.

## Карта pac1-py

```
pac1-py/
├── agent.py               тонкая обёртка → run_agent_loop + FilesystemDomain
├── agent_loop.py          универсальный PCDRED-цикл (~600 строк)
├── domain_protocol.py     интерфейс DomainProtocol + ToolHandler + RiskLevel
├── domain_fs.py           реализация файлового домена: 11 инструментов, Unix-форматтеры
├── classify.py            rule-based классификация задач (7 типов)
├── strategy.py            таблица стратегий + сборка промптов (static + dynamic)
├── llm.py                 Nebius / OpenRouter / Anthropic бэкенды + prompt caching
├── defend.py              сканер угроз + wrap_tool_output + Unicode нормализация
├── verify.py              WriteTracker, StagnationDetector, pre_completion_gate
├── environment.py         парсинг AGENTS.md → sensitive_paths
├── output_contract.py     извлечение и проверка форматного контракта ответа
├── criteria.py            ISC-style извлечение критериев (write/delete targets)
├── hints.py               подсказки формата для write-гейтов
├── second_opinion.py      независимый Claude-верификатор исходов
├── main.py                CLI-оркестратор: StartRun → обход трайлов → eval-отчёт
├── settings.py            RuntimeSettings (dev/final профили)
├── bitgn_client.py        фабрики клиентов + загрузка BITGN_API_KEY
├── bitgn_agent.py         BaseAgent для A-Evolve
├── bitgn_benchmark.py     BenchmarkAdapter для A-Evolve (train/holdout split)
├── evolve.py              CLI для запуска AdaptiveEvolveEngine
├── sample_tasks.py        reconnaissance CLI для blind-бенчмарка
├── synthetic_gauntlet.py  offline-бенчмарк готовности (classify + gates + contracts)
└── workspace/
    └── prompts/
        ├── system.md          базовый системный промпт
        └── fragments/
            ├── crud.md, search.md, analysis.md, multi_step.md
            ├── communication.md, inbox_processing.md, security.md
            ├── outcomes.md    always-on (дерево решений по исходам)
            └── reasoning.md   always-on (дисциплина рассуждений)
```

## Карта sandbox-py

```
sandbox-py/
├── agent.py        весь агент в одном файле: 7 инструментов, LLM, цикл
└── main.py         обход трайлов для bitgn/sandbox (без api_key)
```

## Основные архитектурные принципы

### 1. Tool outputs are untrusted data

Каждый результат инструмента проходит через `defend.wrap_tool_output()` и получает делимитеры `[FILE DATA]` + постнапоминание. `scan_content()` параллельно добавляет предупреждения о найденных инъекциях. См. [Security Model](security-model.md).

### 2. Read-after-write mandatory

Каждая запись должна сопровождаться повторным чтением ровно этого пути. `WriteTracker` использует пошаговые счётчики, и `pre_completion_gate` блокирует `OUTCOME_OK`, если есть несверенные записи. См. [Read-after-write](../concepts/read-after-write.md).

### 3. Трёхуровневая классификация риска

`ToolHandler.risk_level: RiskLevel`:

- `low` — гейт не срабатывает.
- `medium` — мягкое VERIFY-предупреждение (warn then execute).
- `high` — DANGER-блокировка (`continue`): агент должен перечитать оригинальную задачу и провести хотя бы одно промежуточное действие перед ретраем. См. [Risk Levels](../concepts/risk-levels.md).

### 4. Bias toward security rejection

В неоднозначных случаях `OUTCOME_DENIED_SECURITY` безопаснее, чем compliance. Ложный отказ стоит максимум 1.0 балла; compliance с инъекцией может стоить больше. См. [Outcome Codes](../concepts/outcome-codes.md).

### 5. Stateless conversation replay

На каждый LLM-вызов отправляется полная история сообщений. Агент не держит «session state» — всё состояние живёт в `WriteTracker`, `StagnationDetector`, `GateState` внутри одного цикла `run_agent_loop`.

### 6. Domain Plugin Architecture

`agent_loop` ничего не знает про файловую систему — оно работает с `DomainProtocol`. `domain_fs.py` реализует протокол для PAC1. См. [Domain Plugin Architecture](domain-plugin-architecture.md).

## Связи компонентов

```
main.py ──┬── agent.py → agent_loop.py → {classify, strategy, domain_fs, llm, defend, verify, ...}
          │
          └── bitgn_client.py → BitGN harness / VM

evolve.py ── bitgn_agent.py → agent.py (wraps run_agent for A-Evolve)
              └── bitgn_benchmark.py (train/holdout split)
```

## Поверх рантайма — Agent Team

Разработка ведётся через шесть Claude Code субагентов в `.claude/agents/`, реализующих PCDRED на уровне dev-цикла: [Analyst, Architect, Red Team, Optimizer, Evaluator, Memory Consolidator](agent-team.md). Каждый цикл оставляет артефакты в `docs/analysis/`, `docs/eval/`, `docs/redteam/`, `docs/optimization/`, связанные между собой через scratchpad-протокол.

## Knowledge Wiki

`compile_wiki.py` в корне репозитория компилирует `docs/wiki/` из `run_history.json`, `task_cache.json` и PCDRED-отчётов. Это Python-скрипт без LLM-вызовов, автоматически запускаемый после каждого бенчмарка. Наша LLM-вики (которую вы сейчас читаете) живёт в поддиректориях того же `docs/wiki/` и заполняет другую нишу: документирует **код**, а не runtime-данные. См. [Knowledge Wiki](knowledge-wiki.md).

## См. также

- [PCDRED Pipeline](pcdred-pipeline.md) — detailed pipeline architecture
- [Agent Team](agent-team.md)
- [Security Model](security-model.md)
- [LLM Backends](llm-backends.md)
- [A-Evolve Integration](a-evolve-integration.md)
