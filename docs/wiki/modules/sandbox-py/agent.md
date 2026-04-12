---
title: sandbox agent — минималистичный агент mini-окружения
sources:
  - sandbox-py/agent.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - sandbox-py
  - agent
---

# agent (sandbox-py)

> Источник: `sandbox-py/agent.py`

## Назначение

Упрощённый агент для BitGN-окружения `mini` (Obsidian-подобные заметки). Это не «порезанный pac1», а параллельная реализация с другим рантаймом (`MiniRuntimeClientSync` поверх `mini_pb2`) и урезанным набором инструментов. Весь цикл — один файл, без PCDRED-плагинов, без классификации, без стратегий.

## Интерфейс — инструменты

| Tool | Pydantic-модель | Поля |
|---|---|---|
| `tree` | `Req_Tree` | `path` |
| `search` | `Req_Search` | `pattern`, `count` (1..10, default 5), `path` |
| `list` | `Req_List` | `path` |
| `read` | `Req_Read` | `path` |
| `write` | `Req_Write` | `path`, `content` |
| `delete` | `Req_Delete` | `path` |
| `report_completion` | `ReportTaskCompletion` | `completed_steps_laconic`, `answer`, `grounding_refs`, `code: Literal["completed", "failed"]` |

`NextStep` — union над всеми шестью + `ReportTaskCompletion`.

## Отличия от pac1-py

| Аспект | pac1-py | sandbox-py |
|---|---|---|
| Proto-рантайм | `PcmRuntimeClientSync` / `pcm_pb2` | `MiniRuntimeClientSync` / `mini_pb2` |
| Количество инструментов | 11 | 7 |
| Форматирование вывода | Unix-стиль (`cat`, `rg`, `tree` ASCII) | Raw JSON (`MessageToDict`) |
| Классификация | `classify.py` + 7 семейств | Нет |
| Стратегия | `strategy.py` + таблица | Хардкод: 30 шагов |
| DEFEND | `defend.py` + 30+ паттернов + Unicode + encoded | Нет |
| VERIFY | `verify.py` + tracker/gate/stagnation | Нет |
| Системный промпт | многослойный, из fragments | 7 строк inline |
| A-Evolve | Да (`bitgn_agent.py`) | Нет |

## Цикл `run_agent`

```python
def run_agent(model: str, harness_url: str, task_text: str):
    vm = MiniRuntimeClientSync(harness_url)
    messages = [{"role": "user", "content": task_text}]
    for i in range(30):
        job = call_llm(system_prompt, messages, model)
        messages.append({"role": "assistant", "content": job.model_dump_json()})
        result = dispatch(vm, job.function)
        txt = json.dumps(MessageToDict(result), indent=2)
        if isinstance(job.function, ReportTaskCompletion):
            # печатает summary, answer, refs и break
            break
        messages.append({"role": "user", "content": txt})
```

Никаких гейтов, никаких трекеров, никакой верификации — полное доверие LLM. Это сделано сознательно: sandbox-py служит baseline'ом и эталоном «насколько pac1-py обходит простую реализацию».

## LLM-бэкенды

Два бэкенда, выбор через `LLM_BACKEND`:

- `_call_nebius` — OpenAI-compat, `response_format: json_schema` со схемой `NextStep`, `strict=False` (mini-модель Qwen3 не всегда проходит строгую проверку).
- `_call_api` — Anthropic SDK `messages.parse` с `output_format=NextStep` и `thinking={"type": "adaptive"}`.

`_extract_json` — такой же защитный хелпер, как в pac1-py, на случай markdown-fences или preamble перед JSON.

## Системный промпт

Полностью inline в модуле (~7 строк):

```
You are a personal business assistant, helpful and precise.
- always start by discovering available information by running root outline.
- always read `AGENTS.md` at the start
- always reference (ground) in final response all files that contributed to the answer
- Clearly report when tasks are done
```

Это единственная инструкция, которую видит агент. Никакого DEFEND, никакой инструкционной иерархии.

## Зависимости

**Импорты:** `pydantic`, `annotated_types`, `bitgn.vm.mini_connect.MiniRuntimeClientSync`, `bitgn.vm.mini_pb2.*`, `google.protobuf.json_format.MessageToDict`, `connectrpc.errors.ConnectError`. `openai`/`anthropic` — лениво.

**Импортируют:** `main`.

## См. также

- [sandbox main](main.md)
- [pac1-py agent](../pac1-py/agent.md) — для сравнения архитектуры
- [Domain Plugin Architecture](../../architecture/domain-plugin-architecture.md) — про возможность унификации
