---
title: hints — обогащение write-гейтов контекстными подсказками
sources:
  - pac1-py/hints.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - hints
---

# hints

> Источник: `pac1-py/hints.py`

## Назначение

Маленький вспомогательный модуль. Когда action-gate сообщает агенту «ты собираешься `write path/to/file.json`», модуль добавляет контекстные подсказки: какой формат преобладает в целевой папке, существует ли там `README.MD` (который надо прочесть), и правильно ли сохраняется stem-имя при переносе из inbox в cards.

## Интерфейс

| Функция | Описание |
|---|---|
| `folder_format_hint(client, domain, write_path, tracker) -> str` | Возвращает сводную строку подсказок (может быть пустой) |

## Алгоритм

1. `folder = os.path.dirname(write_path)` — целевая папка.
2. Через `domain.dispatch(client, Req_List(tool="list", path=folder))` получаем список файлов (не подпапок).
3. Если среди имён есть `README.MD` (любой регистр) — подсказка «Hint: `{folder}/README.MD` exists — read it for the required file format».
4. Из остальных имён собираем `Counter` расширений; самое частое — подсказка «Hint: existing files in `{folder}/` use `{.ext}` format».
5. Если путь содержит «cards» и в `tracker._reads` есть inbox-файл — ищем последний прочитанный inbox-стем и, если имя целевого файла не `{stem}.md`, добавляем подсказку «inbox stem is `{stem}` — card filename MUST be `{stem}.md`».

Все исключения проглатываются — модуль advisory, никогда не ломает основной цикл.

## Где используется

В `agent_loop.run_agent_loop` внутри MEDIUM/HIGH action-gate для `tool_name == "write"`:

```python
if effective_risk != "low" and not domain.is_completion(cmd):
    gate_msg = action_gate_message(...)
    if tool_name == "write":
        hint = folder_format_hint(client, domain, cmd_path, tracker)
        if hint:
            gate_msg += f"\n{hint}"
```

Это минимально-вторгающийся способ передать агенту «проверяй формат README перед тем как записывать» без необходимости зашивать такие правила в системный промпт.

## Зависимости

**Импорты:** `os`, `collections.Counter`, **`domain_fs.Req_List`** (ленивый импорт внутри функции).

**Импортируют:** `agent_loop`.

## См. также

- [verify.action_gate_message](verify.md)
- [domain_fs](domain_fs.md)
