---
title: Dashboard Redesign — Enhanced Hybrid
sources:
  - docs/superpowers/specs/2026-03-30-dashboard-redesign.md
  - dashboard/app.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - spec
  - dashboard
---

# Dashboard Redesign — Enhanced Hybrid

> Источник: `docs/superpowers/specs/2026-03-30-dashboard-redesign.md`

## Резюме

Переработка Streamlit-дашборда (`dashboard/app.py`, ~643 строки на момент написания спецификации). Старый дашборд — монолитный скролл-лист из ~15 секций равной визуальной важности. Проблемы: большинство аналитических панелей зависят от `run_history.json` (мало записей), тогда как eval-отчётов уже восемь; нет иерархии, нет actionable-guidance, нет трассировки «задача → root cause → фикс → результат», нет plain-language объяснений.

## Ключевые решения

- **Three-Layer Architecture**:
  - **Layer 1 — Command Bar** (всегда видимый): score badge с трендом, task counter, countdown до соревнования, «Next action» (amber-баннер с конкретной инструкцией), cycle status pills, score trend mini-line.
  - **Layer 2 — Task Grid**: 25 задач в сетке 5×5, каждая ячейка показывает status icon, task_id, stability, цветовую подсказку. Клик открывает Task Deep-Dive.
  - **Layer 3 — Navigation**: три таба плюс инлайн-панель Task Deep-Dive с секциями Instruction/Answer, Execution Trace, Lifecycle, Plain-Language Summary.
- **«Next action» logic**: производная от последнего cycle-state. REGRESSED → «Revert latest changes»; analysis есть но нет eval → «Run evaluator»; IMPROVED/NEUTRAL + приоритетная задача → «Start new cycle targeting {task}»; иначе → «Run benchmark to establish baseline».
- **Cycle status pills**: цикл идентифицируется timestamp'ом analysis-отчёта. Стадии: analysis → architect commit → redteam → optimizer → eval. Каждая помечена ✓ или ⬜ в зависимости от существования соответствующего файла.
- **Plain-language narratives** вместо таблиц: каждый eval получает narrative card, каждая task deep-dive получает template-сгенерированный summary.
- **Источники данных** — не только `run_history.json`, но и полный набор eval-отчётов, analysis/redteam/optimization артефактов.

## Статус

Частично реализовано. Точный статус лучше смотреть в самом `dashboard/app.py` — там есть секции, соответствующие описаниям Layer 1/2, но полная реализация task deep-dive и cycle status pills может отставать.

## Связанные компоненты

- `dashboard/app.py` (не документируется как модуль — дашборд не входит в scan_patterns текущей LLM-wiki)
- [Knowledge Wiki](../architecture/knowledge-wiki.md) — источники данных, которые использует дашборд
- [Agent Team](../architecture/agent-team.md) — агенты, чьи артефакты визуализируются
