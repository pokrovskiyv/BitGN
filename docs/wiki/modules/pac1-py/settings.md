---
title: settings — централизованный рантайм-конфиг
sources:
  - pac1-py/settings.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - config
---

# settings

> Источник: `pac1-py/settings.py`

## Назначение

Единая точка правды для рантайм-параметров: какой LLM-бэкенд использовать, какая модель-primary, какая модель-верификатор, какой policy у верификатора, сколько параллельных воркеров запускать, какой бенчмарк-хост и benchmark_id. Нужен, чтобы `main.py`, `bitgn_agent.py`, `second_opinion.py` и `llm.py` не расходились в трактовке env-переменных и чтобы можно было чисто переключать «dev» и «final» профили.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `RuntimeSettings` | `@dataclass(frozen=True)` | Все поля конфига |
| `SETTINGS` | `RuntimeSettings` | Singleton-инстанс, инициализируется при импорте модуля |
| `_env_first(*names, default)` | Возвращает первое непустое значение из перечисленных env-переменных |
| `_env_int(name, default)` | Парсинг целого с fallback'ом |

Поля `RuntimeSettings`:

- `run_profile` — `"dev"` или `"final"`
- `benchmark_host`
- `benchmark_id`
- `llm_backend` — `"nebius"`, `"openrouter"`, `"api"`
- `primary_model`
- `verifier_model`
- `verifier_policy` — `"off"`, `"always"`, `"adaptive"`
- `parallel_workers`

## Профили

Два встроенных профиля в `_PROFILE_DEFAULTS`:

**dev:**
- `llm_backend=nebius`
- `primary_model=Qwen/Qwen3-235B-A22B-Thinking-2507`
- `verifier_model=claude-haiku-4-5`
- `verifier_policy=adaptive`
- `parallel_workers=1`

**final:**
- `llm_backend=api`
- `primary_model=claude-sonnet-4-6`
- `verifier_model=claude-haiku-4-5`
- `verifier_policy=adaptive`
- `parallel_workers=4`

Профиль выбирается по `RUN_PROFILE` env-переменной; неизвестные значения fallback-ятся на `dev`.

## Иерархия env-переменных

Для максимальной совместимости с уже существующими `.env`-ами и старым upstream-сэмплом, `_env_first` принимает несколько имён в порядке предпочтения:

| Поле | Переменные (в порядке приоритета) |
|---|---|
| `benchmark_host` | `BITGN_HOST`, `BENCHMARK_HOST`, default `https://api.bitgn.com` |
| `benchmark_id` | `BENCH_ID`, `BENCHMARK_ID`, default `bitgn/pac1-dev` |
| `llm_backend` | `PRIMARY_LLM_BACKEND`, `LLM_BACKEND`, default профиля |
| `primary_model` | `PRIMARY_MODEL_ID`, `MODEL_ID`, default профиля |
| `verifier_model` | `VERIFIER_MODEL_ID`, `VERIFIER_MODEL`, default профиля |
| `verifier_policy` | `VERIFIER_POLICY`, default профиля |
| `parallel_workers` | `PARALLEL`, default профиля |

`verifier_policy` нормализуется через `.lower()` — регистр не имеет значения.

## Почему frozen dataclass

`SETTINGS` — immutable: никто в рантайме не должен менять активный бэкенд или модель. Любая «переключалка» должна проходить через перезапуск процесса с новыми env-значениями. Это дисциплина из `feedback_journal_discipline`: при любых сбоях важно точно знать, с какой моделью был зафиксирован результат.

## Зависимости

**Импорты:** только `os`, `dataclasses`.

**Импортируют:** `llm`, `main`, `bitgn_agent`, `second_opinion`, `sample_tasks`.

## См. также

- [LLM Backends](../../architecture/llm-backends.md)
- [main](main.md) — как settings комбинируется с `.env.final`
- [second_opinion](second_opinion.md)
