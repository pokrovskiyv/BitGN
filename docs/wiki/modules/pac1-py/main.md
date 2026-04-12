---
title: main — точка входа бенчмарка
sources:
  - pac1-py/main.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - entrypoint
  - benchmark
---

# main

> Источник: `pac1-py/main.py`

## Назначение

CLI-оркестратор пробега против BitGN-бенчмарка. Отвечает за: загрузку переменных окружения (layered `.env` + `.env.final` при `RUN_PROFILE=final`), старт `StartRun` с `api_key`, параллельное исполнение трайлов, постепенное сохранение прогресса (`--resume`), сбор усещания токенов/стоимости и автогенерацию eval-отчёта в `docs/eval/` плюс запись истории в `docs/run_history.json`.

## Интерфейс

| Функция | Назначение |
|---|---|
| `main()` | Парсинг аргументов, установка соединения с harness, цикл по трайлам, финальная сводка |
| `_apply_split(tasks, split)` | Локальное разбиение на train/holdout (80/20) — зеркало `BitgnBenchmarkAdapter.get_tasks` |
| `_run_single_task(client, trial_id, allowed_task_ids, completed)` | Один трайл: `start_trial → run_agent → end_trial` |
| `_append_run_history(task_data, scores, …)` | Добавляет запись в `docs/run_history.json`, собирает `api_usage` и `verifier_usage`, затем запускает `compile_wiki.py` как subprocess |
| `_generate_eval_report(task_data, scores)` | Сравнивает текущий пробег с последним того же split-значения и пишет `docs/eval/run-YYYY-MM-DD-HH.md` |
| `_collect_usage()` / `_collect_verifier_usage()` | Снимок usage + цена (таблицы `_RATES_NEBIUS`, `_RATES_OPENROUTER`, `_RATES_ANTHROPIC`) |
| `_save_task_cache(entry)` / `_save_progress(scores, task_data)` / `_load_progress()` | Промежуточное сохранение `docs/task_cache.json` и `pac1-py/.run_progress.json` |
| `_task_sort_key(task_id)` | Сортировка task id по числовому суффиксу |

## CLI-флаги

- `--resume` — продолжить с того места, где упали (использует `.run_progress.json`).
- `--parallel=N` (или `--parallel N`) — N параллельных воркеров через `ThreadPoolExecutor`.
- `--split=all|train|holdout` — исполнить только соответствующий срез.
- Без префикса `--` — явный task-filter (например, `make task TASKS='t01 t03'` маппится на `python main.py t01 t03`).

## Последовательность пробега

1. `load_dotenv()` → `.env`, затем (если `RUN_PROFILE=final`) `.env.final` или fallback `.env.final.example` с `override=True`.
2. `make_harness_client(BITGN_URL)` и `client.status(StatusRequest())`.
3. `GetBenchmarkRequest(benchmark_id=BENCHMARK_ID)` — получаем список задач.
4. `_apply_split` + пересечение с `task_filter` → `allowed_task_ids`.
5. `StartRunRequest(benchmark_id, name, api_key=BITGN_API_KEY)` — всегда через `api_key`, не через HTTP-заголовок.
6. Цикл по `run.trial_ids`:
   - Параллельный режим использует `ThreadPoolExecutor` + `as_completed`.
   - Каждый трайл проходит через `_run_single_task`, который вызывает `run_agent(...)` из `agent.py`.
   - После каждого трайла сохраняется `task_cache.json` и `.run_progress.json`.
7. **В любом случае** (успех, исключение, Ctrl-C) — `SubmitRunRequest(run_id, force=True)`. `force=True` заставляет сервер оценить даже незавершённые трайлы.
8. `_append_run_history` пишет в `run_history.json`, собирает usage и **автоматически запускает** `python compile_wiki.py` как subprocess — так обновляется Karpathy-style knowledge wiki в `docs/wiki/`.
9. `_generate_eval_report` сравнивает с последним записью того же split и пишет markdown-отчёт в `docs/eval/`.
10. Удаляет `.run_progress.json` и печатает финальную таблицу результатов.

## Тарифная таблица

Тарифы живут прямо в модуле (константы `_RATES_*`). В `api`-бэкенде считается `input + output + cache_creation + cache_read`, четыре ставки. В Nebius/OpenRouter — только `input + output`.

## Зависимости

**Импорты:** `bitgn.harness_pb2.*`, `connectrpc.errors.ConnectError`, `dotenv.load_dotenv`, `agent.run_agent`, `bitgn_client.*`, `llm.LLM_BACKEND`, `second_opinion.VERIFIER_MODEL`, `settings.SETTINGS`.

**Импортируют:** Makefile вызывает `uv run python main.py`.

## См. также

- [run_history / eval report pipeline](../../architecture/knowledge-wiki.md)
- [settings](settings.md)
- [bitgn_client](bitgn_client.md)
