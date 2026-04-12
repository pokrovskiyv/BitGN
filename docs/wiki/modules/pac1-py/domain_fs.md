---
title: domain_fs — файловый домен PAC1
sources:
  - pac1-py/domain_fs.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - domain
  - filesystem
---

# domain_fs

> Источник: `pac1-py/domain_fs.py`

## Назначение

Реализует `DomainProtocol` для PAC1-бенчмарка — типизированной файловой CRM поверх рантайма PCM. Содержит: Pydantic-модели инструментов, реестр диспетчеров, Unix-подобные форматтеры результатов и стартовую последовательность boot-команд. Этот файл — единственное место, где агент знает про конкретные имена proto-сообщений (`WriteRequest`, `ReadRequest` и т. п.).

## Интерфейс — инструменты

Все инструменты объявлены как подклассы `pydantic.BaseModel` с дискриминаторным полем `tool: Literal[...]`:

| Tool | Pydantic-модель | RiskLevel | Поля |
|---|---|---|---|
| `report_completion` | `ReportTaskCompletion` | — | `completed_steps_laconic`, `message`, `grounding_refs`, `outcome` |
| `tree` | `Req_Tree` | low | `level`, `root` |
| `find` | `Req_Find` | low | `name`, `root`, `kind`, `limit` |
| `search` | `Req_Search` | low | `pattern`, `query` (alias), `limit`, `count_only`, `root`, `path` (alias) |
| `list` | `Req_List` | low | `path` |
| `read` | `Req_Read` | low | `path`, `number`, `start_line`, `end_line` |
| `context` | `Req_Context` | low | — |
| `write` | `Req_Write` | **medium** | `path`, `content`, `start_line`, `end_line` |
| `delete` | `Req_Delete` | **high** | `path` |
| `mkdir` | `Req_MkDir` | medium | `path` |
| `move` | `Req_Move` | **high** | `from_name`, `to_name` |

`NextStep` — union-type c discriminator-полем `tool`. Именно эта модель уходит в `response_format: json_schema` при вызове LLM.

У `Req_Search` есть `model_post_init`, который прозрачно маппит `query → pattern` и `path → root` — это нужно потому, что Qwen3 в реальных запусках часто использует альтернативные имена параметров.

## Выходной формат — Unix-style

Форматтеры возвращают псевдо-команды Unix, чтобы LLM ориентировался в знакомом синтаксисе:

| Инструмент | Команда-заголовок |
|---|---|
| `tree` | `tree -L {level} {root}` |
| `list` | `ls {path}` + `# N entries` |
| `read` | `cat {path}` или `cat -n {path}` или `sed -n '{s},{e}p' {path}` |
| `search` | `rg -n --no-heading -e {pattern} {root}` (или `rg -c`, если `count_only`) |
| `write` | `tee {path}` + `written: {path} (OK, now read to verify)` |
| `delete` | `rm {path}` + `deleted: {path}` |
| default | `json.dumps(MessageToDict(result))` |

Это сделано намеренно: Karpathy-style, «LLM хорошо знает unix-paradigm, кормим его на знакомом языке». sandbox-py этого НЕ делает (там сырой JSON).

## Reading the class

`FilesystemDomain` — главный экспорт:

- `name = "filesystem"`, `nextstep_type = NextStep`, `tool_registry = TOOL_REGISTRY`.
- `threat_profile = None` — defend.py пока использует свои модуль-уровневые паттерны, не из домена.
- `classification_rules = ()`, `strategy_entries = ()` — аналогично: пока хранятся в `classify.py` и `strategy.py`, домен их не контрибутит.
- `loop_mode = LoopMode(kind="batch", max_steps=25)` — batch-режим, максимум 25 шагов по умолчанию (конкретный бюджет задаёт `strategy.decide_strategy`).
- `create_client(harness_url)` использует `bitgn_client.make_vm_client` (плоский `PcmRuntimeClientSync`).
- `boot_messages` выполняет три команды подряд: `tree(level=2)`, `read("AGENTS.md")`, `context()` — и каждый результат проходит через `scan_content` и `wrap_tool_output`. Boot-предупреждения сразу вписываются в первое user-сообщение.
- `dispatch` ищет `handler` в `tool_registry` и падает с `ValueError` на неизвестном инструменте.
- `expand_search_result` — полезный трюк: при нуле совпадений и ≥2 токенах в pattern домен автоматически ретраит `search` пер-токен и приклеивает результаты.

## `OUTCOME_BY_NAME`

Плоская таблица маппинга строковых имён на `Outcome`-enum из `pcm_pb2`:

```
OUTCOME_OK, OUTCOME_DENIED_SECURITY, OUTCOME_NONE_CLARIFICATION,
OUTCOME_NONE_UNSUPPORTED, OUTCOME_ERR_INTERNAL
```

Используется только в `_exec_answer`, который упаковывает `ReportTaskCompletion` в `AnswerRequest` для рантайма.

## Зависимости

**Импорты:** `bitgn.vm.pcm_connect`, `bitgn.vm.pcm_pb2`, `pydantic`, `annotated_types`, `domain_protocol.LoopMode/ToolHandler`, `bitgn_client.make_vm_client`, `defend.scan_content`, `defend.wrap_tool_output`.

**Импортируют:** `agent.py`, `hints.py`.

## См. также

- [domain_protocol](domain_protocol.md) — контракт, которому соответствует `FilesystemDomain`
- [Domain Plugin Architecture](../../architecture/domain-plugin-architecture.md)
- [defend](defend.md)
