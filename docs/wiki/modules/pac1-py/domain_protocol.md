---
title: domain_protocol — интерфейс доменного плагина
sources:
  - pac1-py/domain_protocol.py
  - docs/superpowers/specs/2026-03-30-domain-plugin-architecture.md
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - plugin
  - protocol
---

# domain_protocol

> Источник: `pac1-py/domain_protocol.py`

## Назначение

Описывает контракт, которому должен соответствовать любой «домен» (файловая система, мессенджер, календарь, браузер…), чтобы встраиваться в обобщённый [agent_loop](agent_loop.md). Используется `typing.Protocol` со structural-subtyping: никакого наследования от общего базового класса, что совместимо с правилом «flat project, `package = false`». Все `frozen dataclass`-ы, все union-типы — `Literal`.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `RiskLevel` | `Literal["low", "medium", "high"]` | Уровень риска одного инструмента |
| `ToolHandler` | `@dataclass(frozen=True)` | `model: type[BaseModel]`, `execute: Callable[[Any, BaseModel], Any]`, `format: Callable[[BaseModel, Any], str]`, `risk_level: RiskLevel = "low"` |
| `ThreatPattern` | `@dataclass(frozen=True)` | Регулярка-правило угрозы: `category`, `pattern`, `severity: Literal["advisory", "blocking"] = "advisory"` |
| `ThreatProfile` | `@dataclass(frozen=True)` | Полная поверхность угроз домена: `domain_name`, `patterns`, `protected_resources`, `scan_encoded`, `scan_unicode` |
| `TaskTypeRule` | `@dataclass(frozen=True)` | Правило классификации: `task_type`, `pattern`, `priority`, `estimated_steps` |
| `StrategyEntry` | `@dataclass(frozen=True)` | Строка таблицы стратегий: `task_type`, `max_steps`, `security_posture`, `pre_submit_verify`, `prompt_fragment_path` |
| `LoopMode` | `@dataclass(frozen=True)` | `kind: Literal["batch", "reactive"]`, `max_steps`, `poll_interval_ms` |
| `DomainProtocol` | `@runtime_checkable Protocol` | Полный контракт домена |

## Контракт `DomainProtocol`

Атрибуты, которые домен обязан выставить:

- `name: str`
- `nextstep_type: type[BaseModel]` — pydantic-тип для structured output LLM
- `tool_registry: dict[str, ToolHandler]`
- `threat_profile: ThreatProfile | None`
- `classification_rules: tuple[TaskTypeRule, ...]`
- `strategy_entries: tuple[StrategyEntry, ...]`
- `loop_mode: LoopMode`

Методы:

- `create_client(harness_url: str) -> Any` — сделать VM-клиент
- `boot_messages(client) -> list[dict]` — стартовая последовательность сообщений
- `dispatch(client, cmd) -> Any` — исполнить одну команду
- `format_result(cmd, result) -> str` — отформатировать результат в текст
- `expand_search_result(client, cmd, result, txt) -> str` — доп. постобработка (например, auto-retry search по токенам)
- `is_completion(cmd) -> bool` / `completion_outcome(cmd) -> str | None`
- `wrap_output(content) -> str` — обернуть результат делимитерами «FILE DATA»
- `poll_events(client) -> list[dict] | None` — для реактивных доменов (мессенджер), в batch-домене возвращает `None`

## Почему именно Protocol, а не ABC

Flat-project запрет на shared base module делает структурную типизацию единственным работающим вариантом. Каждый агент (pac1-py, sandbox-py) может объявить свой домен независимо, и `@runtime_checkable` гарантирует, что `isinstance(domain, DomainProtocol)` проверит наличие всех атрибутов без импорта общего родителя. Подробная мотивация — в спецификации [Domain Plugin](../../specs/domain-plugin.md).

## Зависимости

**Импорты:** стандартные `typing`, `dataclasses`, `pydantic.BaseModel`.

**Импортируют:** `agent_loop`, `domain_fs`.

## См. также

- [Domain Plugin Architecture](../../architecture/domain-plugin-architecture.md)
- [domain_fs](domain_fs.md) — конкретная реализация для PAC1
- [Risk Levels](../../concepts/risk-levels.md) — как `risk_level` превращается в гейты
