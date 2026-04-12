---
title: sandbox main — точка входа sandbox-бенчмарка
sources:
  - sandbox-py/main.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - sandbox-py
  - entrypoint
---

# main (sandbox-py)

> Источник: `sandbox-py/main.py`

## Назначение

Простейший runner для `bitgn/sandbox` бенчмарка. Никаких параллельных воркеров, никакого resume-протокола, никакого eval-отчёта — только серийный обход трайлов и финальная таблица результатов.

## Интерфейс

| Функция | Описание |
|---|---|
| `main()` | Парсинг task-фильтров из argv, цикл по трайлам, финальная таблица |

## CLI

Единственный вид аргументов — список task_id:

```bash
uv run python main.py t01 t03
```

Без аргументов — исполняются все задачи бенчмарка.

## Переменные окружения

- `BENCHMARK_HOST` — default `https://api.bitgn.com`.
- `MODEL_ID` — default `Qwen/Qwen3-235B-A22B-Thinking-2507`.

Никаких layered-`.env`, никакого `RUN_PROFILE`, никакого API-key-флоу. Бенчмарк `bitgn/sandbox` открытый, API-ключ не нужен.

## Последовательность

1. `HarnessServiceClientSync(BITGN_URL)` → `client.status(StatusRequest())`.
2. `client.get_benchmark(GetBenchmarkRequest(benchmark_id="bitgn/sandbox"))` — `benchmark_id` **захардкожен**, в отличие от pac1-py, который берёт его из `settings.SETTINGS.benchmark_id`.
3. Для каждой задачи (с фильтром по `argv[1:]`):
   - `client.start_playground(StartPlaygroundRequest(...))` — без `StartRun`, чистый playground-режим.
   - `run_agent(MODEL_ID, trial.harness_url, trial.instruction)` — прогон агента из `agent.py`.
   - `client.end_trial(EndTrialRequest(trial_id=trial.trial_id))` — результат со `score` и `score_detail`.
4. Финальный вывод — список `task_id: score` + mean-процент.

## Зависимости

**Импорты:** `bitgn.harness_connect.HarnessServiceClientSync`, `bitgn.harness_pb2.*`, `connectrpc.errors.ConnectError`, `agent.run_agent`.

**Импортируют:** вызывается только из CLI.

## См. также

- [sandbox agent](agent.md)
- [pac1-py main](../pac1-py/main.md) — для сравнения полного pipeline
