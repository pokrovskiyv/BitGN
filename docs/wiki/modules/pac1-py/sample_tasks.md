---
title: sample_tasks — reconnaissance по бенчмарку
sources:
  - pac1-py/sample_tasks.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - cli
  - recon
---

# sample_tasks

> Источник: `pac1-py/sample_tasks.py`

## Назначение

CLI-утилита для предфинальной разведки: вытащить список task_id и (опционально) инструкции задач без запуска агентского цикла и без единого LLM-вызова. Используется в день перед соревнованием, чтобы одним глазом посмотреть на blind task-set до прогона боевого бенчмарка.

## Интерфейс

| Функция | Назначение |
|---|---|
| `main() -> int` | CLI |
| `_render_quick(tasks) -> list[str]` | Быстрый режим: метаданные с proto (task_id, instruction/description/category/tags, если доступны) |
| `_render_live(tasks, host, benchmark_id, limit) -> list[str]` | «Live»-режим: для каждой задачи вызывается `StartPlaygroundRequest` + `EndTrialRequest`, чтобы забрать полный текст `trial.instruction` и `trial.harness_url` |

## CLI-флаги

- `--live` — вытаскивать полные инструкции через start_playground/end_trial. **Никаких LLM-вызовов**, но создаются реальные трайлы.
- `--limit N` — обрезать live-режим первыми N задачами.
- `--out path.md` — записать результат в файл (иначе в stdout).

## Безопасность

Docstring содержит явное предупреждение: `--live` создаёт реальные трайлы, и на некоторых бенчмарках каждый `start_playground` может считаться попыткой. **Перед использованием на финальном blind-бенчмарке** нужно вручную убедиться, что one-attempt-per-task не enforced. На практическом `bitgn/pac1-dev` эта операция безопасна.

## Layered `.env`

Модуль повторяет layered-загрузку `.env` из `main.py`: сначала обычный `.env`, потом (если `RUN_PROFILE=final`) — `.env.final` или fallback `.env.final.example` с `override=True`. Без этого dev-значения перетёрли бы final-профиль.

## `end_trial` в любых условиях

`_render_live` всегда вызывает `end_trial`, даже если формирование отчётной строки упало — иначе трайлы «зависли» бы в RUNNING-состоянии и утекли ресурсами бенчмарка.

## Зависимости

**Импорты:** `bitgn.harness_pb2.*`, `connectrpc.errors.ConnectError`, `bitgn_client.make_harness_client`, `settings.SETTINGS`, `dotenv.load_dotenv`.

**Импортируют:** используется только как CLI.

## См. также

- [main](main.md) — полноценный прогон агента
- [settings](settings.md) — откуда приходит `benchmark_host` / `benchmark_id`
- [bitgn_client](bitgn_client.md)
