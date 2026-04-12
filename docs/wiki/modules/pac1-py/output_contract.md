---
title: output_contract — извлечение и проверка формата ответа
sources:
  - pac1-py/output_contract.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - verification
  - format
---

# output_contract

> Источник: `pac1-py/output_contract.py`

## Назначение

Извлекает «форматный контракт» из текста задачи и валидирует, что финальное completion-сообщение этому контракту удовлетворяет. Грейдер BitGN часто проверяет дословный формат («return only the email», «one per line, sorted alphabetically», «YYYY-MM-DD»), и мелкое нарушение формата превращает правильный ответ в ноль.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `AnswerContract` | `@dataclass(frozen=True)` | 7 булевых флагов формата |
| `extract_answer_contract(task_text: str) -> AnswerContract` | Функция | Regex-парсинг |
| `check_answer_contract(task_text: str, message: str) -> list[str]` | Функция | Возвращает список нарушений (пуст → OK) |

Поля `AnswerContract`:

- `raw_only` — ответ должен быть сырой величиной, без префикса «The answer is…»
- `one_per_line` — несколько пунктов в ответе должны быть на отдельных строках
- `sorted_alphabetically` — список должен быть отсортирован
- `expect_number` — только цифры
- `expect_email` — одна email-строка по паттерну RFC-подобному
- `expect_date_iso` — только `YYYY-MM-DD`
- `requires_exact_count` — задача спрашивает exact count (нужно `count_only=True` search)

## Регулярки

Несколько тонких моментов:

- `_RAW_ONLY_RE` ловит «return/answer/reply/respond only», «plain/raw text only», «names/address/email/date only».
- `_NUMBER_ONLY_RE` ловит «digits only», «as an integer», «plain integer», «numeric only» и т. п.
- `_EMAIL_ONLY_RE` разрешает «return only the email», «reply just the address», «email/address only».
- `_DATE_ISO_RE` — паттерны «YYYY-MM-DD», «ISO 8601», «ISO date format».
- `_COUNTING_RE` — «how many», «count», «exact count» (включает вопросы типа «how many blacklisted accounts?»).
- `_PREFIX_RE` — большой perl-подобный список forbidden-префиксов: «the answer is», «answer:», «result:», «email:», «the name is», «the accounts are» и т. п. Это отлавливает классическую ошибку, когда агент пишет «The email address is user@example.com» вместо `user@example.com`.
- `_EMAIL_RE` / `_DATE_ISO_VALUE_RE` — строгие проверки итоговой строки.

## Логика `check_answer_contract`

Идёт поочерёдно:

1. Пустое сообщение → `["completion message is empty"]`.
2. Если `raw_only` — не должно быть префикса (`_PREFIX_RE`), не должно начинаться с ` ``` `, `-`, `*`.
3. `expect_number` → `re.fullmatch(r"\d+", text)`.
4. `expect_email` → `_EMAIL_RE.fullmatch(text)`.
5. `expect_date_iso` → `_DATE_ISO_VALUE_RE.fullmatch(text)`.
6. `one_per_line` — многолинейность + отсутствие bullet-маркеров, «key: value» строк, и не одна-линия-с-запятыми.
7. `sorted_alphabetically` — если строк больше одной, нормализованный (`casefold`) список должен совпадать с `sorted()`.

## Где используется

В `verify.pre_completion_gate` при `OUTCOME_OK`: если `check_answer_contract` вернул не пустой список, гейт отклоняет отправку с сообщением «Answer format requirements not met: ...». Агент получает шанс переписать completion-message в правильный формат.

Также используется в `synthetic_gauntlet.py` как часть локального пре-финал prechek'а.

## Зависимости

**Импорты:** только `re`, `dataclasses`.

**Импортируют:** `verify`, `synthetic_gauntlet`.

## См. также

- [verify](verify.md) — `pre_completion_gate`
- [synthetic_gauntlet](synthetic_gauntlet.md)
