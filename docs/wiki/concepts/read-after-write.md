---
title: Read-after-write
sources:
  - pac1-py/verify.py
  - pac1-py/agent_loop.py
  - pac1-py/criteria.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - concept
  - verification
---

# Read-after-write

## Определение

Обязательное правило pac1-py: **после каждой записи в файл агент должен прочитать ровно тот же путь** перед тем, как сообщать о завершении задачи. Без этого нет гарантии, что запись действительно успела или попала в нужное место. Правило энфорсится не подсказкой в промпте, а проверкой в коде.

## Механика

### WriteTracker с пошаговыми счётчиками

Вся логика строится на [WriteTracker](../modules/pac1-py/verify.md) с `_writes: dict[path, step]` и `_reads: dict[path, step]`. Счётчик `_step` увеличивается на каждую операцию, и `unverified_writes()` возвращает пути, для которых `_reads[p] < _writes[p]` — то есть читали, но **до** записи, а не после.

Пример:

```
step 1: read  path=A          _reads[A] = 1
step 2: write path=A          _writes[A] = 2
step 3: report_completion

_reads[A]  == 1
_writes[A] == 2
_reads[A] < _writes[A]  →  A в списке unverified_writes
```

Агент обязан сделать `read A` **после** `write A`:

```
step 1: read  path=A          _reads[A] = 1
step 2: write path=A          _writes[A] = 2
step 3: read  path=A          _reads[A] = 3
step 4: report_completion     → unverified_writes() == []
```

### Pre-submission gate

В `agent_loop.run_agent_loop` перед dispatch'ем `report_completion`:

```python
unverified = tracker.unverified_writes()
if strategy.pre_submit_verification and unverified:
    hold = f"HOLD: You wrote to [{...}] but never re-read. Verify first."
    messages.append({"role": "user", "content": hold})
    continue
```

`strategy.pre_submit_verification` включён для всех классов кроме `security_test` — там приоритет отдаётся быстрому отказу.

## Usecase: write → read → delete

Для задач с удалением (например, «обработай inbox-файл и удали его») правило ширится: после записи в outbox нужно прочитать outbox, и только **после** этого удалять inbox-файл. Это фиксируется в фрагменте [inbox_processing.md](../../pac1-py/workspace/prompts/fragments/inbox_processing.md) как «strict ordering»:

```
read inbox item → read workflow → write outbox reply/finance record →
read-back to verify write succeeded → delete inbox file → report_completion
```

## Criteria gate поверх read-after-write

[criteria.extract_criteria](../modules/pac1-py/criteria.md) вытаскивает из текста задачи явные цели-записи и цели-удаления («create file at path X», «delete Y»). В `agent_loop` для `OUTCOME_OK` идёт дополнительная проверка:

```python
if task_criteria and outcome == "OUTCOME_OK":
    unmet = check_criteria(task_criteria, tracker)
    if unmet:
        hold = f"HOLD: Unmet criteria: {'; '.join(unmet)}..."
```

Здесь речь уже не про read-after-write (которое контролирует правильность одной записи), а про то, что **все запрошенные** записи/удаления действительно произошли. Два разных слоя одной дисциплины.

## Форматтер дополнительно подсказывает

Формат вывода `write` в [domain_fs](../modules/pac1-py/domain_fs.md) намеренно содержит текстовый hint:

```
tee path/to/file
written: path/to/file (OK, now read to verify)
```

«now read to verify» — это не декоративная строка; она показывает агенту, что после записи ожидается именно read-шаг. Плюс на medium/high write-гейте может появиться подсказка от [hints.folder_format_hint](../modules/pac1-py/hints.md) про формат и stem-имя.

## См. также

- [verify.WriteTracker](../modules/pac1-py/verify.md)
- [criteria](../modules/pac1-py/criteria.md)
- [Outcome Codes](outcome-codes.md)
