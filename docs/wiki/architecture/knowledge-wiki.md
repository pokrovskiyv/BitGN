---
title: Knowledge Wiki — две системы в одной директории
sources:
  - compile_wiki.py
  - CLAUDE.md
  - .gitignore
last_updated: 2026-04-11T14:00:00Z
tags:
  - architecture
  - wiki
  - documentation
---

# Knowledge Wiki

В `docs/wiki/` сосуществуют **две разных системы документации**, отвечающие на разные вопросы о проекте. Обе — `.gitignore`-ed, обе рассчитаны на полную пересборку по требованию.

## Две системы

| Система | Отвечает на вопрос | Вход | Выход | Запуск |
|---|---|---|---|---|
| `compile_wiki.py` | **«Как сейчас идёт агент?»** (runtime-данные) | `docs/run_history.json`, `docs/task_cache.json`, `docs/analysis/`, `docs/eval/`, `docs/redteam/`, `docs/optimization/`, `docs/sota-analysis.md` | `docs/wiki/{index,scoreboard,fix-registry,vulnerability-catalog,health}.md`, `docs/wiki/_meta.json`, `docs/wiki/tasks/t*.md` | Автоматически после каждого `make run` (см. `main._append_run_history`) |
| LLM-wiki (`/wiki` skill) | **«Как работает код?»** (архитектура, модули, концепции) | Исходники `pac1-py/`, `sandbox-py/`, `docs/superpowers/specs/`, `.claude/agents/`, CLAUDE.md | `docs/wiki/modules/`, `docs/wiki/architecture/`, `docs/wiki/concepts/`, `docs/wiki/specs/`, `docs/wiki/decisions/`, `docs/wiki/glossary.md` | По команде `/wiki compile` или `/wiki rebuild` |

## Почему сосуществуют

Оба инструмента нужны: Python-компилятор даёт свежие данные после каждого прогона без тарификации LLM, LLM-вики даёт семантические объяснения, которые было бы дорого перегенерировать на каждый run. Они разделены по **непересекающимся путям** внутри `docs/wiki/`:

```
docs/wiki/
├── index.md                     ← Python-compiled (⚠ LLM-wiki НИКОГДА не трогает)
├── scoreboard.md                ← Python-compiled
├── fix-registry.md              ← Python-compiled
├── vulnerability-catalog.md     ← Python-compiled
├── health.md                    ← Python-compiled
├── _meta.json                   ← Python-compiled
├── tasks/                       ← Python-compiled (per-task карточки)
│   ├── t01.md
│   ├── t02.md
│   └── …
│
├── code-index.md                ← LLM-owned (root of code docs)
├── glossary.md                  ← LLM-owned
├── modules/                     ← LLM-owned (один файл на Python-модуль)
│   ├── pac1-py/
│   └── sandbox-py/
├── architecture/                ← LLM-owned (cross-cutting views)
├── concepts/                    ← LLM-owned (domain concepts)
├── specs/                       ← LLM-owned (spec summaries)
├── decisions/                   ← LLM-owned (ADRs)
│
└── .state/                      ← LLM-wiki scanner state
    ├── config.json
    ├── manifest.json
    └── backlinks.json
```

## compile_wiki.py

Чистый Python, без LLM-вызовов. Запускается за ≈1 секунду. Что он делает:

1. `load_run_history()` парсит `docs/run_history.json` в список `RunRecord`.
2. `load_task_cache()` парсит `docs/task_cache.json` — тексты инструкций и последние агентские ответы.
3. `parse_cycle_report`, `parse_eval_report_w`, `parse_redteam_report`, `parse_opt_report` — regex-парсеры markdown-отчётов PCDRED-агентов.
4. Составляет `ScoreboardData`, `TaskCard`, `VulnEntry`, `HealthAlert`, `FixEntry`, `AttackEntry`.
5. Пишет плоский markdown в `docs/wiki/{index,scoreboard,fix-registry,vulnerability-catalog,health}.md` и один файл на задачу в `docs/wiki/tasks/`.
6. `docs/wiki/_meta.json` содержит build-метаданные.

## Конвенция владения

1. **Python-compiled файлы — это «данные»**. Не редактировать вручную, не модифицировать LLM-вики.
2. **LLM-owned поддиректории — это «код-доки»**. `compile_wiki.py` их не видит и не трогает.
3. `compile_wiki.py` использует только `mkdir(exist_ok=True)` и `write_text()`; никаких `rmtree`/`unlink`. Это защищает LLM-вики от случайного затирания.
4. `/wiki rebuild` удаляет файлы только в явно заданных секциях LLM-вики (`modules/`, `architecture/`, …). `.state/`, `raw/`, `changelog/` и Python-compiled-файлы не трогаются.

## Каноничный index

Есть намеренный nuance: в `docs/wiki/index.md` лежит Python-compiled главная (со скоринг-борда, health-alerts, сводной таблицей задач). LLM-вики НЕ должна этот файл перезаписывать. Собственный «главный индекс» LLM-вики лежит в `code-index.md`. MkDocs-nav, генерируемый сканером, видит и index.md (как «Главная» через автоматическое правило), и все секции LLM-вики.

## Интеграция с Agent Team

Agent Team читает Python-compiled страницы как входные данные:

- **Analyst** стартует с `docs/wiki/index.md` и `docs/wiki/fix-registry.md` (чтобы не повторить провалившийся фикс) и `docs/wiki/tasks/tNN.md` для конкретной задачи.
- **Red Team** читает `docs/wiki/vulnerability-catalog.md`, чтобы атаковать нетестированные категории.
- **Optimizer** смотрит `docs/wiki/scoreboard.md` для per-model-паттернов.

Это Karpathy-style рабочий поток: «каждый ответ делает wiki умнее» — агенты читают вики вместо 100+ сырых отчётов в `docs/`.

## Auto-run после каждого бенчмарка

В `main._append_run_history` зашит хук:

```python
wiki_script = Path(__file__).parent.parent / "compile_wiki.py"
if wiki_script.exists():
    subprocess.run([sys.executable, str(wiki_script)], cwd=..., capture_output=True, timeout=10)
```

Поэтому любой `make run` автоматически обновляет Python-compiled wiki. LLM-compiled wiki не обновляется автоматически — требуется `/wiki compile`.

## Hook и pending-файл

В `.git/hooks/post-commit` установлен скрипт, который после каждого коммита запускает `scanner.py check` и при необходимости создаёт `docs/wiki/.state/pending`. При следующем старте Claude Code-сессии/`/wiki` будет видно, что вика-исходники поменялись снаружи и требуют перекомпиляции.

## См. также

- [compile_wiki.py](../../../compile_wiki.py) (не документируется как модуль: в `docs/wiki/` существуют только исходники pac1-py и sandbox-py)
- [Agent Team](agent-team.md)
- [PCDRED Pipeline](pcdred-pipeline.md)
