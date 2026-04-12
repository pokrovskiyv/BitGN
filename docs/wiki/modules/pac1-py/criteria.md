---
title: criteria — ISC-style извлечение критериев
sources:
  - pac1-py/criteria.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - verification
  - criteria
---

# criteria

> Источник: `pac1-py/criteria.py`

## Назначение

Извлекает из текста задачи атомарные **проверяемые критерии** вида «write to path X» / «delete file Y» и умеет сверить их со состоянием [WriteTracker](verify.md). Это ISC-подобное упрощение: мы не парсим задачу до уровня логики, а ищем конкретные цели-действия, которые можно проверить сразу после исполнения.

## Интерфейс

| Функция | Описание |
|---|---|
| `extract_criteria(task_text: str) -> list[tuple[str, str]]` | Возвращает пары `("write", path)` или `("delete", path)` |
| `check_criteria(criteria, tracker: WriteTracker) -> list[str]` | Возвращает описания невыполненных критериев |

## Регулярки

- `_WRITE_RE` ловит «create/write/add/save/store/move/copy/place/put» + опциональные квалификаторы («a new file called», «into», «at», «under») + захват пути с расширением (`[/\w][\w./-]+\.\w+`).
- `_DELETE_RE` — «delete/remove/erase» + опциональный артикль + путь.

Оба регэкса требуют **расширение файла** в захватываемом пути — это намеренно фильтрует ложные срабатывания на абстрактные фразы типа «delete the previous record».

## `check_criteria`

Для каждого критерия проверка:

- `kind == "write"` — путь должен быть суффиксом какого-то `tracker._writes`.
- `kind == "delete"` — путь должен быть суффиксом какого-то `tracker.deleted_paths()`.

Суффикс-матчинг нужен, потому что regex извлекает относительный путь («accounts/acct_009.json»), а трекер знает абсолютный (`/accounts/acct_009.json`).

## Где используется

В `agent_loop.run_agent_loop` при приёме `OUTCOME_OK`:

```python
task_criteria = extract_criteria(task_text)
...
if task_criteria and outcome == "OUTCOME_OK":
    unmet = check_criteria(task_criteria, tracker)
    if unmet:
        hold = f"HOLD: Unmet criteria: {'; '.join(unmet)}..."
```

Это дополнительный слой защиты поверх `pre_completion_gate` — специфически для явно упомянутых в задаче путей.

## Зависимости

**Импорты:** `re`, `verify.WriteTracker`.

**Импортируют:** `agent_loop`.

## См. также

- [verify](verify.md)
- [Read-after-write](../../concepts/read-after-write.md)
