---
title: second_opinion — независимый верификатор исходов
sources:
  - pac1-py/second_opinion.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - verifier
  - pcdred
---

# second_opinion

> Источник: `pac1-py/second_opinion.py`

## Назначение

Один-шотовый LLM-верификатор исхода: перед тем как агент отправит `report_completion`, модуль спрашивает отдельную модель (по умолчанию Haiku), согласна ли она с предложенным `outcome`. Работает на собственном Anthropic-клиенте независимо от основного LLM-бэкенда — то есть Qwen3-агент может использовать Claude-верификатор.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `VerifierVerdict` | `BaseModel` | `agree: bool`, `reasoning: str`, `suggested_outcome: str | None` |
| `VERIFIER_MODEL` | `str` | Из `SETTINGS.verifier_model` (по умолчанию `claude-haiku-4-5`) |
| `VERIFIER_POLICY` | `str` | `"off"`, `"always"`, `"adaptive"` |
| `get_verifier_usage()` | Функция | Снимок счётчиков токенов |
| `needs_second_opinion(classification, outcome, task_text) -> bool` | Функция | Решает, вызывать ли верификатор |
| `get_second_opinion(task_text, outcome, completion_message, recent_evidence, available_tools, _primary_model) -> VerifierVerdict` | Функция | Исполняет вызов |

## Политика `needs_second_opinion`

Триггеры (порядок не важен, any-match):

- `VERIFIER_POLICY == "off"` → никогда.
- `VERIFIER_POLICY == "always"` → всегда.
- `outcome != "OUTCOME_OK"` — любой не-OK исход требует проверки.
- `threat_level != "none"` — любая угроза в задаче.
- `requires_delete` — удаление всегда проверяется.
- `task_type` в `{communication, inbox_processing, multi_step}` — сложные семейства.
- Слова `inbox / queue / pending items / incoming queue` в тексте задачи.

Триггеры намеренно **общие**, не привязаны к конкретным task-id и не содержат хардкода на уровне ключевых слов бенчмарка, чтобы перенестись на blind-задачи финала.

## Анатомия вызова

1. `_load_verifier_prompt()` читает `workspace/prompts/fragments/verifier.md` (свежо, без кэша).
2. Собирается `user_content`: инструкция задачи, runtime tool surface, предложенный исход, completion_message, блок «recent tool outputs» (последние 6 evidence-блоков из истории).
3. `client.messages.parse(output_format=VerifierVerdict, ...)` с retry на 429/5xx (1/2/4s + jitter).
4. При любой ошибке (retries exhausted, parse fail, общая Exception) возвращается «нейтральное» согласие (`agree=True, reasoning="verifier unavailable (...)"`). Это намеренно: сломанный верификатор не должен переопределять решение агента, который уже прошёл `pre_completion_gate` и evidence-challenge.

## Поведение в `agent_loop`

Если верификатор возвращает `agree=False`, `agent_loop` ставит `verifier_new_evidence_required = True` и запоминает `len(tracker._consulted)`. Повторный `report_completion` будет заблокирован, пока не появится хотя бы один новый путь. Это заставляет агента **собрать дополнительные доказательства**, а не просто «упереться рогом» в прежнее решение.

## Зависимости

**Импорты:** `pydantic.BaseModel`, `classify.TaskClassification`, `settings.SETTINGS`. `anthropic` импортируется лениво.

**Импортируют:** `agent_loop`, `main` (для usage), `synthetic_gauntlet`.

## См. также

- [verifier.md](../../concepts/outcome-codes.md) — правила верификатора
- [agent_loop](agent_loop.md) — как вердикт используется
- [settings](settings.md)
