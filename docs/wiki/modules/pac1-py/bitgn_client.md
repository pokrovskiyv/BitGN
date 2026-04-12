---
title: bitgn_client — фабрики клиентов + API-ключ
sources:
  - pac1-py/bitgn_client.py
last_updated: 2026-04-11T14:00:00Z
tags:
  - module
  - pac1-py
  - auth
  - client
---

# bitgn_client

> Источник: `pac1-py/bitgn_client.py`

## Назначение

Фабрики для двух BitGN-клиентов (`HarnessServiceClientSync` и `PcmRuntimeClientSync`) плюс единственная точка загрузки `BITGN_API_KEY`. Ключ загружается один раз при импорте и передаётся в `StartRunRequest(api_key=...)` как поле тела запроса, а не как HTTP-заголовок — это требование BitGN Run API.

## Интерфейс

| Символ | Тип | Описание |
|---|---|---|
| `BITGN_API_KEY` | `str` | Константа модуля, прочитана из `os.getenv("BITGN_API_KEY", "").strip()` |
| `make_harness_client(host: str) -> HarnessServiceClientSync` | Функция | Плоская обёртка над `HarnessServiceClientSync(host)`. Без auth-interceptor — BITGN_API_KEY идёт отдельным полем |
| `make_vm_client(harness_url: str) -> PcmRuntimeClientSync` | Функция | Плоская обёртка над `PcmRuntimeClientSync(harness_url)`. `harness_url` уже scoped на конкретный трайл сервером |
| `_announce_once()` | Приватная | Одноразовый баннер: сообщает, загружен ли ключ, и предупреждает, если `RUN_PROFILE=final` без `BITGN_API_KEY` |

## Почему такая обёртка

Фабрики существуют ради **одной точки изменений**. Если в будущем аутентификация снова переедет на транспортный слой (например, HTTP-заголовок), поправка будет только здесь — все остальные модули (`main`, `bitgn_agent`, `bitgn_benchmark`, `sample_tasks`, `domain_fs`) пользуются фабриками и ничего больше знать не должны.

## Поведение при отсутствующем ключе

При первом вызове любой фабрики печатается один из трёх сигналов:

1. `[bitgn-auth] BITGN_API_KEY loaded (len=..., passed via StartRunRequest)` — ключ найден.
2. `[bitgn-auth] WARNING: BITGN_API_KEY not set but RUN_PROFILE=final — StartRun will fail on authenticated benchmarks` — предупреждение, StartRun на `bitgn/pac1-prod` точно упадёт.
3. `[bitgn-auth] BITGN_API_KEY not set (dev mode)` — нормально для локального dev-бенчмарка.

## Зависимости

**Импорты:** `os`, `bitgn.harness_connect.HarnessServiceClientSync`, `bitgn.vm.pcm_connect.PcmRuntimeClientSync`.

**Импортируют:** `main`, `bitgn_agent`, `bitgn_benchmark`, `domain_fs`, `sample_tasks`.

## См. также

- [main](main.md) — здесь ключ попадает в `StartRunRequest`
- [domain_fs](domain_fs.md) — здесь `make_vm_client` создаёт VM-клиент на трайл
