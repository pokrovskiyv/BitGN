---
title: Детекция стагнации
sources:
  - pac1-py/verify.py
  - pac1-py/agent_loop.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - concept
  - verification
---

# Детекция стагнации

## Определение

Стагнация — состояние, в котором агент повторяет одни и те же действия без прогресса. Это не ошибка и не угроза: цикл продолжает исполняться, но без интервенции агент бы вхолостую доехал до `max_steps`. `StagnationDetector` обнаруживает три класса стагнации и инжектит в историю короткие nudge-сообщения.

## Три класса сигналов

### 1. Exact repeat (порог 2)

`is_stagnant()` — последние два элемента `history` совпадают. Например:

```
list /inbox
read /inbox/a.md
read /inbox/a.md     ← stagnation detected
```

Порог намеренно **2**, а не 3 — один лишний повтор это уже трата одного шага из дефицитного бюджета.

Сообщение: «WARNING: You just repeated the same tool call. Try a different tool or different arguments.»

### 2. Oscillation (ABAB, порог 4)

`is_oscillating()` — последние 4 элемента образуют паттерн `A B A B`:

```
read /file.json
search "token"
read /file.json
search "token"       ← oscillation detected
```

Сообщение: «WARNING: You are alternating between the same two operations without progress. Step back and try a completely different approach.»

### 3. Семантическая стагнация

Три подкласса, каждый срабатывает **один раз за задачу** через `fired_signals: set[str]` — чтобы не спамить:

- **`not_found_streak`** (≥3 consecutive not_found error'ов) — агент гадает пути вместо использования `tree/list`. Сообщение: «3 consecutive not_found errors. Stop guessing paths — use `tree` or `list` to see what actually exists».
- **`zero_match_streak`** (≥3 подряд пустых search/find результатов) — агент использует grep-подобный поиск там, где нужен `list` или `tree`. Сообщение: «3 consecutive search/find calls returned 0 matches. Switch to `list` or `tree`».
- **`no_new_evidence`** (окно `_EVIDENCE_WINDOW=4` подряд с `new_path_count == 0`) — агент зациклился на уже прочитанных данных. Сообщение: «The last 4 tool calls consulted zero new paths. Try a different file or different question — or report completion with the evidence you already have».

## Связь с WriteTracker

`record_result(tool_name, success, is_empty, new_path_count)` использует данные, собранные из `WriteTracker`:

- `new_path_count = len(tracker._consulted) - prior_consulted_count` — сколько новых путей добавилось после этого вызова.
- `success` вычисляется из `result is not None` + отсутствия «not_found» в тексте.
- `is_empty` — только для `search/find`: пустой ли `matches`/`entries`.

Это делает детектор **поведенческим** — никаких task-type ветвлений, никакого хардкода task-id. Сигналы генерализуются на любые неизвестные семейства задач.

## Связь с верификатором

Особый случай: `verifier_new_evidence_required = True` (после того как second_opinion вернул `agree=False`) сбрасывается, как только появляется новый consulted-путь:

```python
if verifier_new_evidence_required and new_path_count > 0:
    verifier_new_evidence_required = False
```

Это значит: не-agree вердикт требует от агента **добыть новые доказательства**, и система отслеживает этот прогресс через тот же счётчик, что использует стагнация-детект.

## Почему 2 / 3 / 4

- **2** для exact repeat — агрессивно, чтобы не тратить шаги.
- **3** для not_found/zero_match — два подряд ещё могут быть ошибкой выбора имени, три — это уже стратегическая проблема.
- **4** для no_new_evidence — окно должно быть достаточно большим, чтобы не срабатывать при медленном но реальном прогрессе.

## См. также

- [verify.StagnationDetector](../modules/pac1-py/verify.md)
- [Read-after-write](read-after-write.md)
- [PCDRED Pipeline](../architecture/pcdred-pipeline.md)
