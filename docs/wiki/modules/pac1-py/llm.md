---
title: llm — LLM-бэкенды и structured output
sources:
  - pac1-py/llm.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - llm
  - backend
---

# llm

> Источник: `pac1-py/llm.py`

## Назначение

Слой абстракции над тремя LLM-бэкендами: OpenAI-совместимый Nebius (основной dev-бэкенд), OpenRouter (альтернативный) и Anthropic SDK (`api` — финальный профиль). Все три обязаны отдавать структурированный `NextStep`-объект. Модуль инкапсулирует:

- Выбор бэкенда через `SETTINGS.llm_backend`.
- Сборку system-сообщения из статической и динамической частей (`strategy.ExecutionStrategy`).
- Prompt caching на стороне Anthropic (`cache_control: ephemeral` на статическом блоке).
- Ретраи на 429/5xx с экспоненциальным backoff.
- Подсчёт токенов и стоимости (usage-dict для каждого бэкенда).
- Восстановление повреждённого JSON через `_recover_nextstep`.

## Интерфейс

| Функция | Описание |
|---|---|
| `call_llm(system_static, system_dynamic, messages, model, nextstep_type)` | Главная точка входа — роутит в соответствующий бэкенд по `LLM_BACKEND` |
| `_call_openai_compat(...)` | Общий путь для Nebius и OpenRouter: `response_format: json_schema`, для OpenRouter — `extra_body={"reasoning": {"effort": "high"}}` |
| `_call_api(...)` | Anthropic SDK через `messages.parse()` с `output_format=NextStep`, adaptive thinking (кроме Haiku), ретраи на 429/5xx |
| `get_nebius_usage()` / `get_openrouter_usage()` / `get_api_usage()` | Снимок usage-счётчиков соответствующего бэкенда |
| `get_usage_snapshot()` | Снимок usage активного бэкенда (для per-task delta в `main.py`) |
| `_extract_json(text)` | Аккуратно вытаскивает JSON-объект из текста, даже если он обёрнут в markdown-fences или содержит преамбулу |
| `_recover_nextstep(raw_json, nextstep_type)` | Пытается собрать валидный `NextStep` из «кривых» вариантов, которые любят возвращать Qwen3-модели |

## Восстановление структуры (`_recover_nextstep`)

Qwen3 периодически отдаёт один из нескольких неканонических форматов:

1. **«Flat tool object»:** `{"tool": "read", "path": "..."}` — модель забыла обёртку `function`. Код оборачивает такой объект в полноценный `NextStep` с автозаполненными `current_state`, `plan_remaining_steps_brief`, `task_completed`.
2. **`name` вместо `tool`:** `{"name": "read", ...}` — перенаименование поля. Код поднимает `name` на уровень `tool` (и в корне, и во вложенном `function`).
3. **Обёртка `parameters`:** `{"tool": "read", "parameters": {...}}` — параметры лежат внутри ключа `parameters`. Код распаковывает их в родительский объект.
4. **Пустой `plan_remaining_steps_brief`:** `[]` — pydantic-валидация требует `MinLen(1)`. Код подставляет `["(continue)"]`.
5. **`outcome_code` вместо `outcome`:** типовая ошибка в полях `ReportTaskCompletion`. Код перенаименовывает.
6. **Отсутствующие обязательные поля ReportTaskCompletion** (`completed_steps_laconic`, `message`, `outcome`) заполняются заглушками `"(auto)"`, `"Task completed"`, `"OUTCOME_OK"`.

Все эти починки нужны, чтобы одна неудачная сериализация модели не уронила целую задачу из бюджета 100+ шагов.

## Prompt caching в Anthropic-бэкенде

`_call_api` формирует `system`-блок из двух text-частей:

```python
system_blocks = [
    {"type": "text", "text": static_text, "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": dynamic_text},  # без кэша
]
```

Это экономит ≈80 % входных токенов при повторных вызовах внутри одной задачи, потому что статический промпт (base + task-type addon + outcomes + reasoning + security) одинаков на всех шагах, а динамический (target-подсказки, tool surface, env-hints) меняется и оплачивается полностью.

## Ретраи

`_call_api` делает до 3 попыток с задержками `1s, 2s, 4s + jitter` на 429 и любой 5xx. Остальные ошибки Anthropic немедленно превращаются в `RuntimeError`. OpenAI-compat путь не имеет собственных ретраев на уровне модуля — их обрабатывает ретрай-цикл в `agent_loop.run_agent_loop` (3 попытки с `_FMT_CORRECTION`).

## Зависимости

**Импорты:** `pydantic.BaseModel`, `pydantic.ValidationError`, `settings.SETTINGS`. `openai` / `anthropic` импортируются лениво в момент вызова.

**Импортируют:** `agent_loop`, `main`, `bitgn_benchmark` косвенно через `main`.

## См. также

- [LLM Backends](../../architecture/llm-backends.md) — как три бэкенда сравниваются
- [strategy](strategy.md) — откуда берутся `system_static`/`system_dynamic`
- [settings](settings.md) — как выбирается активный бэкенд
