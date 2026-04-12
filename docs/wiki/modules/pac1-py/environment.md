---
title: environment — извлечение окружения из AGENTS.md
sources:
  - pac1-py/environment.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - perceive
---

# environment

> Источник: `pac1-py/environment.py`

## Назначение

Лёгкий парсер `AGENTS.md`, который превращает свободный текст правил бенчмарка в структурный `EnvironmentModel`. Используется фазой **Perceive** в `agent_loop`: как только домен отдаёт boot-сообщения, из содержимого `AGENTS.md` вытаскиваются чувствительные пути и ключевые ограничения. В дальнейшем `agent_loop` проверяет запись в любой из чувствительных путей и автоматически поднимает её до `risk_level=high` в action-гейте.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `EnvironmentModel` | `@dataclass(frozen=True)` | `sensitive_paths: frozenset[str]` (по умолчанию содержит `"AGENTS.md"`), `constraints: tuple[str, ...]` |
| `extract_environment(agents_md: str) -> EnvironmentModel` | Функция | Парсер |

## Алгоритм

1. Всегда включает `"AGENTS.md"` в `sensitive_paths` как baseline.
2. Применяет два regex-шаблона для поиска sensitive-путей:
   - `(?:do not|never|don't|must not)\s+(?:modify|edit|change|delete|write to|alter)\s+[`'"]?([^\s`'"]+)` — фразы вида «do not modify `config.json`».
   - `[`'"]([^\s`'"]+)[`'"]?\s+(?:is|are)\s+(?:read[- ]only|protected|immutable)` — «the `config.json` is read-only».
3. Для каждого найденного пути обрезает пунктуацию (`.,;:`), отбрасывает одно-символьные ложные срабатывания и добавляет в множество.
4. Ищет constraints по паттерну `(?:you must|always|never|do not|required to)\s+(.{10,80}?)(?:\.|$)` — короткие предложения-требования. Дубли отбрасываются, список ограничивается 10 элементами, чтобы не раздувать структурный снимок.
5. Возвращает `EnvironmentModel(sensitive_paths=frozenset(sensitive), constraints=tuple(constraints[:10]))`.

## Почему это важно

В бенчмарке AGENTS.md — источник правды VM. Если агент начинает переписывать его в ответ на инструкцию из файла-содержимого, это фактически провал по двум критериям сразу (side-effect + security). Автоматическое извлечение sensitive-путей гарантирует, что любая запись в эти файлы пройдёт через HIGH-risk гейт, даже если конкретное имя файла никогда не встречалось в исходном коде агента.

## Зависимости

**Импорты:** `re`, `dataclasses`.

**Импортируют:** `agent_loop`.

## См. также

- [agent_loop](agent_loop.md) — как `sensitive_paths` попадают в `effective_risk`
- [Security Model](../../architecture/security-model.md)
- [domain_fs](domain_fs.md) — `boot_messages` читает AGENTS.md первым
