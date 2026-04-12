---
title: LLM-бэкенды
sources:
  - pac1-py/llm.py
  - pac1-py/settings.py
  - pac1-py/second_opinion.py
  - sandbox-py/agent.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - architecture
  - llm
  - backend
---

# LLM-бэкенды

BitGN-pac1 работает с тремя LLM-бэкендами и держит отдельный Anthropic-клиент для верификатора. Выбор основного бэкенда — `SETTINGS.llm_backend` (приходит из env-переменных `PRIMARY_LLM_BACKEND` / `LLM_BACKEND`, с дефолтом из профиля). Верификатор всегда Anthropic, независимо от основного бэкенда.

## Таблица бэкендов

| Бэкенд | Код в llm.py | Base URL / SDK | Structured output | Особенности |
|---|---|---|---|---|
| `nebius` | `_call_openai_compat` | `https://api.studio.nebius.com/v1/` (OpenAI SDK) | `response_format: json_schema, strict=False` | Основной dev-бэкенд. Qwen3-235B-Thinking. `reasoning_content` печатается в лог для трассировки |
| `openrouter` | `_call_openai_compat` | `https://openrouter.ai/api/v1` (OpenAI SDK) | `response_format: json_schema, strict=True` + `extra_body={"reasoning": {"effort": "high"}}` | Альтернативный OpenAI-compat. Требует `reasoning.effort=high`, иначе качество падает |
| `api` | `_call_api` | Anthropic SDK `messages.parse` | `output_format=NextStep` | Финальный профиль. Sonnet 4.6 primary + Haiku 4.5 verifier. **Prompt caching**, adaptive thinking (кроме Haiku). Ретраи на 429/5xx с экспоненциальным backoff |

## Prompt caching в Anthropic

Ключевой приём для финального профиля. `strategy.decide_strategy` возвращает `ExecutionStrategy` со split'ом на `system_prompt_static` и `system_prompt_dynamic`. `_call_api` формирует:

```python
system_blocks = [
    {"type": "text", "text": static_text, "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": dynamic_text},  # без кэша
]
```

- **Static** — base + task-addon + outcomes.md + reasoning.md + security.md. Одинаков на всех шагах одной задачи.
- **Dynamic** — target_hints, runtime tool surface, HINT env. Меняется и оплачивается как обычно.

На 20-шаговой задаче кэш экономит ≈80% input-токенов. Это особенно важно, потому что system-prompt ~8000 токенов плюс накопленный message history.

## Структурированный вывод через `NextStep`

`NextStep` — pydantic union с дискриминатором `tool`. JSON Schema выглядит так:

```json
{
  "properties": {
    "current_state": {"type": "string"},
    "plan_remaining_steps_brief": {"type": "array", ...},
    "task_completed": {"type": "boolean"},
    "function": {
      "anyOf": [
        {"$ref": "#/definitions/Req_Read"},
        {"$ref": "#/definitions/Req_Write"},
        ...
      ],
      "discriminator": {"propertyName": "tool"}
    }
  }
}
```

Все три OpenAI-compat провайдера получают эту схему в `response_format: json_schema`. Anthropic `messages.parse` сам строит свою внутреннюю схему из `output_format=NextStep`.

## Recovery для Qwen3-моделей

Qwen3-235B-Thinking в Nebius периодически эмитит non-canonical JSON. `llm._recover_nextstep` обрабатывает:

1. `{"name": "read", ...}` вместо `{"tool": "read", ...}`.
2. `{"tool": "read", "parameters": {"path": "..."}}` вместо flat-параметров.
3. Плоский tool-object без обёртки `function`.
4. Пустой `plan_remaining_steps_brief` при `task_completed=True`.
5. `outcome_code` вместо `outcome` в `ReportTaskCompletion`.
6. Отсутствующие required-поля `ReportTaskCompletion` (`completed_steps_laconic`, `message`, `outcome`).

Плюс в `agent_loop.run_agent_loop` — ретраи с `_FMT_CORRECTION` (3 попытки), которые просят модель эмитить ровно требуемую структуру.

## Usage-счётчики и цены

Модуль держит независимые usage-словари для каждого бэкенда:

- `_nebius_usage` / `_openrouter_usage`: `input_tokens`, `output_tokens`, `reasoning_tokens`, `calls`
- `_api_usage`: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `calls`

Цены живут в `main.py`:

- Nebius Qwen3-235B: `(0.20, 0.80)` USD/M токенов
- OpenRouter Qwen3.6: `(0.30, 1.20)` или `(0, 0)` для free-тира
- Anthropic Haiku: `(1, 5, 1.25, 0.1)` — четыре ставки (in/out/cache_write/cache_read)
- Anthropic Sonnet: `(3, 15, 3.75, 0.3)`
- Anthropic Opus: `(15, 75, 18.75, 1.5)`

Финальный расчёт делается в `_collect_usage()` и попадает в `run_history.json` как `api_usage`.

## Ретраи и backoff

Anthropic-бэкенд имеет **свой** retry-цикл (3 попытки, `1/2/4 + jitter` секунд на 429 и 5xx). OpenAI-compat путь ретраев в `llm.py` не имеет — его перекрывает 3-попыточный retry-цикл в `agent_loop.run_agent_loop`, который на парс-ошибках добавляет `_FMT_CORRECTION` message.

## Разница с sandbox-py

`sandbox-py/agent.py` содержит упрощённые версии обоих бэкендов (`_call_nebius`, `_call_api`) прямо в одном файле. Там:

- Только два бэкенда: Nebius и Anthropic.
- Нет prompt caching.
- Нет ретраев.
- Нет `_recover_nextstep` — на ошибке парса задача падает.
- `strict=False` для schema.

Это оправдано простотой sandbox — там задачи короткие и риск ошибки парса низкий.

## См. также

- [llm](../modules/pac1-py/llm.md)
- [settings](../modules/pac1-py/settings.md)
- [strategy](../modules/pac1-py/strategy.md)
- [second_opinion](../modules/pac1-py/second_opinion.md)
