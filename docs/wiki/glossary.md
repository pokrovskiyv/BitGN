---
title: Глоссарий
last_updated: 2026-04-11T14:00:00Z
tags:
  - glossary
---

# Глоссарий

Термины и аббревиатуры, встречающиеся в коде и документации BitGN-pac1.

## Платформа и соревнование

| Термин | Определение | См. также |
|---|---|---|
| **BitGN** | Платформа «Agent Benchmarks & Competitions». Организатор: Rinat Abdullin (Вена). Доменное имя, не аббревиатура | [Handbook](specs/handbook.md) |
| **PAC** | Personal Agent Challenge. Соревнование для персональных trustworthy-агентов | [Handbook](specs/handbook.md) |
| **PAC1** | Первый бенчмарк в рамках PAC — pac1-py агент таргетит именно его | [Overview](architecture/overview.md) |
| **bitgn/pac1-dev** | Открытый практический бенчмарк, можно гонять свободно | [main](modules/pac1-py/main.md) |
| **bitgn/pac1-prod** | Финальный blind-scoring бенчмарк, требует BITGN_API_KEY | [bitgn_client](modules/pac1-py/bitgn_client.md) |
| **bitgn/sandbox** | Упрощённый mini-бенчмарк (Obsidian-подобные заметки), открытый | [sandbox main](modules/sandbox-py/main.md) |
| **Blind scoring window** | Окно соревнования, когда результат скрыт до финального закрытия | [Handbook](specs/handbook.md) |
| **Harness** | BitGN API, принимающий trial'ы и возвращающий scores | [bitgn_client](modules/pac1-py/bitgn_client.md) |

## PCDRED и агентский цикл

| Термин | Определение | См. также |
|---|---|---|
| **PCDRED** | Perceive → Classify → Decide → Run → Evaluate → Defend — шестифазный цикл | [PCDRED](concepts/pcdred.md) |
| **Perceive** | Чтение дерева, AGENTS.md, context() — формирование EnvironmentModel | [environment](modules/pac1-py/environment.md) |
| **Classify** | Правиловая классификация задачи в 7 типов | [classify](modules/pac1-py/classify.md) |
| **Decide** | Выбор стратегии и сборка системного промпта | [strategy](modules/pac1-py/strategy.md) |
| **Run** | Исполнение цикла шагов с гейтами и стагнацией | [agent_loop](modules/pac1-py/agent_loop.md) |
| **Evaluate** | Pre-submission-проверки (unverified writes, gate, verifier) | [verify](modules/pac1-py/verify.md) |
| **Defend** | Сканирование контента на угрозы + wrap_tool_output | [defend](modules/pac1-py/defend.md) |
| **NextStep** | Pydantic-модель shaped output LLM с дискриминаторным `tool` | [domain_fs](modules/pac1-py/domain_fs.md) |
| **ReportTaskCompletion** | Специальный «tool», которым агент завершает задачу | [Outcome Codes](concepts/outcome-codes.md) |
| **AGENTS.md** | Ground truth файл в VM — правила, sensitive paths, workflow | [environment](modules/pac1-py/environment.md) |
| **WriteTracker** | Класс, отслеживающий reads/writes/deletes по шагам | [verify](modules/pac1-py/verify.md) |
| **StagnationDetector** | Класс для детекции повторов, осцилляций, семантической стагнации | [Stagnation Detection](concepts/stagnation-detection.md) |
| **EnvironmentModel** | Frozen dataclass с sensitive_paths и constraints | [environment](modules/pac1-py/environment.md) |
| **Target hints** | Упомянутые в задаче пути/файлы, выуженные regex'ом | [classify](modules/pac1-py/classify.md) |

## Безопасность

| Термин | Определение | См. также |
|---|---|---|
| **Prompt injection** | Попытка инъектировать инструкции через содержимое файлов | [Threat Injection](concepts/threat-injection.md) |
| **Threat pattern** | Одна regex-сигнатура атаки в `defend.THREAT_PATTERNS` | [defend](modules/pac1-py/defend.md) |
| **Threat level** | `none / low / high` — категориальный уровень угрозы задачи | [classify](modules/pac1-py/classify.md) |
| **Security posture** | `standard / hardened / paranoid` — рабочий режим цикла | [strategy](modules/pac1-py/strategy.md) |
| **RiskLevel** | `low / medium / high` — базовый уровень одного инструмента | [Risk Levels](concepts/risk-levels.md) |
| **Action gate** | Проверка перед dispatch'ем MEDIUM/HIGH-инструмента | [verify.action_gate_message](modules/pac1-py/verify.md) |
| **Interlock** | Stateful защита HIGH-гейтов от double-tap-атак | [agent_loop](modules/pac1-py/agent_loop.md) |
| **Double-tap** | Атака, когда инъекция заставляет агент мгновенно повторить тот же запрос | [Red Team Attack 2](architecture/agent-team.md) |
| **GateState** | Snapshot состояния при срабатывании HIGH-гейта | [agent_loop](modules/pac1-py/agent_loop.md) |
| **wrap_tool_output** | Функция, оборачивающая untrusted-ввод делимитерами `[FILE DATA]` | [defend](modules/pac1-py/defend.md) |
| **TRUST HIERARCHY** | Иерархия доверия в system.md: rules > task > AGENTS.md > docs > content | [Instruction Hierarchy](concepts/instruction-hierarchy.md) |
| **Cumulative threat count** | Счётчик найденных угроз за всю задачу — крутит threshold'ы | [agent_loop](modules/pac1-py/agent_loop.md) |
| **Homoglyph** | Визуально похожий символ из другого алфавита (кириллица/греч/армянский) | [defend](modules/pac1-py/defend.md) |

## Верификация и контракт ответа

| Термин | Определение | См. также |
|---|---|---|
| **Read-after-write** | Правило: каждая запись проверяется чтением после | [Read-after-write](concepts/read-after-write.md) |
| **pre_completion_gate** | Единая точка проверки перед `report_completion` | [verify](modules/pac1-py/verify.md) |
| **Answer contract** | Извлечённые требования к формату ответа (число, email, ISO-дата, one-per-line, ...) | [output_contract](modules/pac1-py/output_contract.md) |
| **Criteria** | ISC-style атомарные цели записи/удаления из текста задачи | [criteria](modules/pac1-py/criteria.md) |
| **Second opinion** | Независимый Claude-верификатор исхода (обычно Haiku) | [second_opinion](modules/pac1-py/second_opinion.md) |
| **Evidence challenge** | Одноразовый запрос процитировать доказательство не-OK исхода | [verify.outcome_evidence_message](modules/pac1-py/verify.md) |
| **grounding_refs** | Обязательное поле `ReportTaskCompletion` со всеми consulted-путями | [verify.merge_grounding_refs](modules/pac1-py/verify.md) |

## Коды исходов

| Код | Значение |
|---|---|
| `OUTCOME_OK` | Задача выполнена успешно |
| `OUTCOME_DENIED_SECURITY` | Отклонено из-за угрозы в контенте (требует evidence) |
| `OUTCOME_NONE_CLARIFICATION` | Задача неполная или упоминает несуществующее |
| `OUTCOME_NONE_UNSUPPORTED` | Нет инструмента для требуемого действия |
| `OUTCOME_ERR_INTERNAL` | Fallback — непоправимая tool-ошибка |

См. [Outcome Codes](concepts/outcome-codes.md).

## Backends и модели

| Термин | Определение | См. также |
|---|---|---|
| **LLM_BACKEND** | Env-переменная: `nebius`, `openrouter`, `api` | [llm](modules/pac1-py/llm.md) |
| **Nebius AI Studio** | OpenAI-compat бэкенд, dev-дефолт с Qwen3-235B-Thinking | [LLM Backends](architecture/llm-backends.md) |
| **OpenRouter** | Альтернативный OpenAI-compat, требует `reasoning.effort=high` | [LLM Backends](architecture/llm-backends.md) |
| **Anthropic API** | Финальный профиль (`api`), Sonnet 4.6 primary + Haiku 4.5 verifier, prompt caching | [LLM Backends](architecture/llm-backends.md) |
| **Prompt caching** | Anthropic ephemeral-cache на static-части системного промпта | [strategy](modules/pac1-py/strategy.md), [llm](modules/pac1-py/llm.md) |
| **Adaptive thinking** | Параметр `thinking={"type": "adaptive"}` для Claude (кроме Haiku) | [llm](modules/pac1-py/llm.md) |
| **Qwen3-235B-Thinking** | Основная открытая модель в dev-профиле | [settings](modules/pac1-py/settings.md) |
| **reasoning_content** | Поле OpenAI-compat ответов Qwen3-Thinking с chain-of-thought | [llm](modules/pac1-py/llm.md) |

## A-Evolve и эволюция

| Термин | Определение | См. также |
|---|---|---|
| **A-Evolve** | Внешний фреймворк автоматической эволюции агентов | [A-Evolve Integration](architecture/a-evolve-integration.md) |
| **workspace/** | Директория мутабельных файлов (prompts, skills, memory) | [strategy](modules/pac1-py/strategy.md) |
| **Evolver model** | Модель, предлагающая мутации (default `claude-opus-4-5`) | [evolve](modules/pac1-py/evolve.md) |
| **AdaptiveEvolveEngine** | Движок эволюции с rollback'ом на падении скора | [evolve](modules/pac1-py/evolve.md) |
| **Trajectory** | A-Evolve структура результата одного trial'а | [bitgn_agent](modules/pac1-py/bitgn_agent.md) |
| **BaseAgent.solve(task)** | Интерфейсный метод A-Evolve, реализованный в `BitgnAgent` | [bitgn_agent](modules/pac1-py/bitgn_agent.md) |

## Agent Team

| Термин | Определение | См. также |
|---|---|---|
| **Agent Team** | Шесть Claude Code-субагентов PCDRED dev-цикла | [Agent Team](architecture/agent-team.md) |
| **Analyst** | Разбирает провалы, выдаёт `docs/analysis/` отчёт | [Agent Team](architecture/agent-team.md) |
| **Architect** | Реализует минимальный generalizable diff | [Agent Team](architecture/agent-team.md) |
| **Red Team** | Генерирует атаки, классифицирует BLOCKED/PARTIAL/BYPASSES | [Agent Team](architecture/agent-team.md) |
| **Optimizer** | Профилирует execution efficiency | [Agent Team](architecture/agent-team.md) |
| **Evaluator** | Запускает `make run`, выдаёт verdict | [Agent Team](architecture/agent-team.md) |
| **Memory Consolidator** | autoDream 4-фазный цикл над MEMORY.md | [Agent Team](architecture/agent-team.md) |
| **Scratchpad protocol** | YAML-frontmatter артефакты в `docs/scratchpad/` | [Agent Team](architecture/agent-team.md) |
| **GREEN/AMBER zones** | Анти-оверфит классификация editable-файлов | [Agent Team](architecture/agent-team.md) |
| **Commander** | Anti-overfit gate поверх AMBER-diff'ов | [Agent Team](architecture/agent-team.md) |
| **Generalization analyst** | Family-level failure clustering | [Variance Spec](specs/variance-reducer.md) |

## Дополнительно

| Термин | Определение |
|---|---|
| **ConnectRPC / buf** | Транспортный слой BitGN Harness API, типобезопасный протокол |
| **pcm_pb2 / mini_pb2** | Сгенерированные protobuf-классы для PCM-рантайма (pac1) и mini-рантайма (sandbox) |
| **uv** | Python package/project manager, используется обоими агентами |
| **RUN_PROFILE** | `dev` (Qwen3 + Nebius) или `final` (Sonnet + Haiku + Anthropic) |
| **ISC** | Information-Seeking Checklist — концепция атомарных критериев |
| **SoTA** | State-of-the-Art — базовая литература, против которой оценивается дизайн |
| **Karpathy-style wiki** | «You never write the wiki — the LLM writes everything; you just steer» |

## См. также

- [Code Index](code-index.md)
- [Overview](architecture/overview.md)
