# Hands-On AI Engineering → практический план dev/operator tooling

**Дата:** 2026-06-10  
**Источник паттернов:** [Sumanth077/Hands-On-AI-Engineering](https://github.com/Sumanth077/Hands-On-AI-Engineering) (каталог ~54 изолированных демо; **не** runtime BirdLense)  
**Статус:** planning only — без изменений application-кода  
**Связанные планы:** `refactoring_consortium_plan.md` (CV/config/perf — **другой scope**)

---

## Принципы (обязательны)

### 1. Не вмешательство ради вмешательства

Каждая рекомендация ниже имеет **зачем** и **когда НЕ делать**. Если нет измеримой боли (context bloat, повторяющиеся runbook-вопросы, пропуск OpenAPI в ревью) — шаг **пропускаем**.

### 2. Без обязательной зависимости от облачных LLM

| Слой | Политика |
|------|----------|
| **Hub inference** (YOLO/OpenVINO, processor, go2rtc) | **Не трогаем** — detect-first, on-prem |
| **Prod runtime** | LLM **не** входит в контейнер по умолчанию |
| **Dev/operator tooling** | LLM **optional**: Cursor (провайдер пользователя), OpenCode (local/Ollama или выбранный provider), `webfetch` без API key |
| **Запрещено как default** | Hard-require OpenAI/Gemini/Orq.ai в prod, cloud embeddings, vector DB в stack |

### 3. Фокус: OpenCode + Cursor, не новые приложения

Усиливаем существующий workflow (агенты, MCP, rules, `make ci-local`). **Не** добавляем Streamlit/Gradio-демо и отдельные chat-apps в `app/ui/`.

---

## 1. Резюме

**Делаем:**

- Формализуем **OpenCode-агентов** (`birdlense-reviewer`, `birdlense-ci`) и **разделение труда** OpenCode ↔ Cursor.
- Приводим **MCP hygiene**: repo filesystem + Hub MCP server (`birdlense_mcp.py`) как read-only consumer для dev; токен в prod.
- Добавляем **Cursor rules** только там, где повторяются ошибки (OpenAPI, security, ci-local gate).
- **Phase B (опционально):** grounded Q&A по MkDocs/runbooks через `webfetch` / локальные `.md` — dev-only или operator opt-in.
- **Phase C (только после доказанной ценности B):** routing запросов оператора к существующим REST/SQLite views — без новой vector DB.

**Сознательно не делаем:**

- Streamlit-демо, Chroma/Qdrant, cloud OCR/audio/video RAG, fine-tuning folder из репо-источника.
- LLM в processor pipeline, замену YOLO/OpenVINO, fusion/safeguards (#622) под видом «AI».
- Обязательный cloud LLM в prod или новый микросервис «operator chat» до Phase 3 consortium (#627).

---

## 2. Принципы отбора

| Решение | Критерий | Примеры |
|---------|----------|---------|
| **Принять** | Уже есть точка интеграции; нулевой/низкий prod footprint; усиливает OpenCode/Cursor | SOUL для `@birdlense-reviewer`, Hub MCP как client target, `make ci-local` hook |
| **Отложить** | Идея полезна, но нет baseline или зависит от Phase 3 operator UI | Multi-domain router в React, clip Q&A с timestamps |
| **Отвергнуть** | Дублирует Hub, требует cloud/vector DB, или отдельное demo-app | Streamlit agents, ChromaDB, Gemini video, Telegram approval bots |

---

## 3. Практический план по фазам

> Все фазы — **dev tooling / optional operator**. Prod Hub работает без LLM.

### Phase A — 1–2 недели, низкий риск

**Зачем:** меньше ошибок в PR, меньше context bloat при работе с OpenAPI ~5.8k строк.  
**Когда НЕ делать:** если `@birdlense-reviewer` и `make ci-local` уже стабильно ловят regressions — только документировать текущее, без новых файлов.

| Шаг | Действие | Файлы / команды |
|-----|----------|-----------------|
| A.1 | Расширить **birdlense-reviewer SOUL**: чеклист OpenAPI sync, запрет логирования секретов, processor/web rules, regression matrix из consortium | `.opencode/agents/birdlense-reviewer.md` |
| A.2 | Зафиксировать **birdlense-ci** сценарии: full vs fast gate | `.opencode/agents/birdlense-ci.md`, `AGENTS.md` |
| A.3 | **MCP hygiene в OpenCode**: оставить `birdlense-repo` + `sequential-thinking`; GitHub MCP — только в `~/.config/opencode/opencode.json` (секреты не в repo) | `opencode.json`, `.cursor/rules/opencode.mdc` |
| A.4 | **Cursor rule** (1 файл max): когда звать OpenCode vs править в чате | дополнение `.cursor/rules/opencode.mdc` при необходимости |
| A.5 | Документировать **подключение Hub MCP** для dev: `python app/web/birdlense_mcp.py --check`; в stack — `mcp.enabled` + `MCP_TOKEN` | `birdlense_mcp.py`, `docs/contributor/security.md` |
| A.6 | Smoke: `opencode mcp list`, `@birdlense-ci` → `make ci-local` на чистой ветке | — |

**Exit A:** reviewer выдаёт структурированное ревью с путями; ci-agent повторяет AGENTS.md; Hub MCP `--check` показывает tool count.

### Phase B — опционально, dev-only или operator opt-in

**Зачем:** «почему YOLO слепой?» / «что значит finalize p95?» — ответ с цитатой runbook, не из памяти модели.  
**Когда НЕ делать:** если операторы не задают doc-вопросы; MkDocs/runbooks актуальны в UI (#627); нет человека поддерживать prompt/runbook index.

| Шаг | Действие | Ограничения |
|-----|----------|-------------|
| B.1 | **Runbook Q&A в OpenCode**: `webfetch` + локальные `docs/runbooks/*.md`, `docs/ru/*.md` (pattern: Documentation QnA Agent) | Без нового Python-сервиса в `app/web/` |
| B.2 | Опционально: MCP **Fetch** только в user-level OpenCode config для опубликованного MkDocs site | Не default в `opencode.json` repo |
| B.3 | Operator opt-in: тот же паттерн через Cursor + `@docs` / lean-ctx read — **не** новая панель в React | Требует явного ADR «LLM optional» |

**Exit B:** 5 типовых вопросов (YOLO blind, deploy, MCP token, config drift, OOM 137) получают grounded ответ с путём к `.md` за <2 мин без галлюцинаций по метрикам.

**Delivered (#631):** `.opencode/agents/birdlense-runbook-qa.md`, `.opencode/prompts/runbook-qa.md`, `docs/contributor/hub-mcp-dev.md` § Runbook Q&A.

### Phase C — только если Phase B доказала ценность

**Зачем:** один entry point для оператора: «orphan count + openvino device» → правильный API/SQLite, не monolithic prompt.  
**Когда НЕ делать:** Phase 3 consortium (#627 system card) не закрыт; нет метрик «сколько запросов / сколько fallback»; предлагают Chroma/cloud embed.

| Шаг | Действие | Ограничения |
|-----|----------|-------------|
| C.1 | **Structured router** (pattern: RAG + DB routing): domains → visits/videos · health/config · funnel/perf | Router = выбор MCP tool group / OpenAPI tag, не новая DB |
| C.2 | **Grade-before-answer** (pattern: agentic RAG): ответ только если источник — `recording_session_summary`, health API, `openapi.yaml` | Max 2–3 rewrite iter; log routing reason |
| C.3 | Fallback chain: Hub MCP tools → local runbooks → «не знаю» | **NO** DuckDuckGo, **NO** vector DB by default |

**Exit C:** 10 production-like вопросов; ≥80% с корректным source; zero cloud embed в default profile.

**Delivered (#632, minimal):** MCP tool groups + `@birdlense-operator-router` (keyword rules), ADR `docs/strategy/adr-dev-only-operator-router.md`. Full semantic LLM router — **not** shipped; prod remains LLM-free.

---

## 4. OpenCode + Cursor — детальные рекомендации

### 4.1 birdlense-reviewer — формализация SOUL

**Зачем:** единый gate до merge — OpenAPI, UI contract, security, без дублирования Bugbot.  
**Когда НЕ делать:** для однострочных doc-fix; если заменяет `make ci-local` (агент **read-only**, CI остаётся source of truth).

Текущая база (`.opencode/agents/birdlense-reviewer.md`) — расширить до явного чеклиста:

| Область | Проверка |
|---------|----------|
| OpenAPI | Новые/изменённые routes → `openapi.yaml` + `npm run codegen:openapi` в UI |
| Security | Нет логов `FLASK_SECRET_KEY`, `PROCESSOR_SECRET`, `MCP_TOKEN`; MCP auth documented |
| Processor | Изменения в finalize/fusion → regression matrix строка (YOLO blind, anchor skip) |
| Config | Новые `processor.auto_*` → ADR + `deprecated_keys.py` (#616) |
| Output | Резюме + нумерованные findings с путями + «прогнать: `make ci-local` / contract-local» |

### 4.2 GitHub MCP / searchable tools (pattern Eagle Eye)

**Зачем:** при большом OpenAPI не грузить все tools в context — dynamic discovery (Haystack `SearchableToolset` / MCPToolset в репо-источнике).  
**Когда НЕ делать:** auto-post в GitHub без human approval; дублирование GitHub Actions; секреты в repo `opencode.json`.

**Практика BirdLense:**

- GitHub MCP: `opencode mcp add` или `~/.config/opencode/opencode.json` + env `GITHUB_TOKEN`.
- Human-in-the-loop: draft review в OpenCode/Cursor → человек мержит; не Telegram bot.
- SOUL/Eagle Eye pattern → **только** структура identity-файла агента, не runtime prod.

### 4.3 OpenCode vs Cursor — division of labor

Из `.cursor/rules/opencode.mdc` (зафиксировать как norm):

| Задача | Где |
|--------|-----|
| Мелкая правка, 1–2 файла, ясный diff | **Cursor** (этот чат) |
| Длинный refactor, PR context, multi-file explore | **OpenCode** `opencode run` / `@explore` |
| План без записи на диск | OpenCode **Plan** mode |
| CI gate, отчёт без правок | `@birdlense-ci` |
| Ревью без правок | `@birdlense-reviewer` |
| Параллель | Cursor правит; OpenCode — второй воркер (`opencode-mcp` в Cursor) |

**Permission model** (`opencode.json`): bash default `ask`; allow `make *`, `npm *`, `git status|diff|log|branch`; `git push` — ask. Не расширять `allow` на destructive команды без ADR.

### 4.4 Hub MCP server — как dev-агенты потребляют

`app/web/birdlense_mcp.py` — **MCP SERVER**: OpenAPI → FastMCP tools, HTTP к Hub API, auth `MCP_TOKEN` / `mcp.token`.

| Роль | Использование |
|------|----------------|
| Dev agent (OpenCode/Cursor) | Подключить streamable HTTP `/mcp` или stdio локально; read-only ops для диагностики visits/health/funnel |
| Prod | Optional `mcp.enabled=true`; **обязателен** token (`docs/contributor/security.md`) |
| Не путать | `birdlense-repo` filesystem MCP ≠ Hub API MCP |

Smoke: `python app/web/birdlense_mcp.py --check` — число tools; первые 8 имён в stdout.

### 4.5 CI-local hooks

| Hook | Когда |
|------|-------|
| `make ci-local` | Перед merge substantial changes; `@birdlense-ci` full report |
| `make test-web-contract-local` | Быстро после OpenAPI edit |
| `cd app/ui && npm run typecheck` | UI-only |
| `make verify-prod-env` | Перед deploy (не LLM scope, но reviewer должен напоминать) |

Reviewer **не заменяет** CI — только указывает, какой gate прогнать.

---

## 5. Что НЕ переносим из Hands-On-AI-Engineering

Явный stop-list (не backlog, не «может потом» без нового ADR):

- Streamlit/Gradio demo-apps как продуктовые surface
- ChromaDB, Qdrant, GraphRAG, cloud embeddings
- OpenAI/Gemini/Mistral/Orq.ai as **required** dependencies
- OCR (prescription/LaTeX), audio demos, multimodal Gemini video
- `fine_tuning/` (пустая папка в источнике) — weights pipeline отдельно (`best.pt`, OpenVINO export)
- Telegram/OpenClaw approval bots, scheduling/travel/finance agents
- YouTube/Whisper transcript pipeline — Hub уже имеет mp4 + session summary
- Замена detect-first CV или fusion logic (#622) LLM-слоем
- Новый vector DB «для operator chat»

---

## 6. Критерии готовности / stop conditions

**Phase A считается закрытой, когда:**

- [ ] `birdlense-reviewer.md` содержит полный чеклист (≥4 области выше)
- [ ] Документировано OpenCode ↔ Cursor split (opencode.mdc или этот файл)
- [ ] Hub MCP `--check` воспроизводим в contributor docs

**Эксперимент Phase B/C — закрыть (stop), если:**

- Нет ≥3 реальных operator/dev вопросов в месяц, которые B решает быстрее runbook
- Ответы без grounding >20% на golden set из 10 вопросов
- Появляется требование cloud API / vector DB «чтобы заработало»
- Phase 3 consortium (#627) даёт достаточный operator truth без LLM
- Поддержка runbook-index >2 ч/нед без owner

**Не считать провалом:** осознанный stop после Phase A — это **успех** принципа «не вмешательство ради вмешательства».

---

## 7. Связь с EPIC #601 / refactor plan

| Программа | Scope | Этот документ |
|-----------|-------|---------------|
| [#601](https://github.com/Gfermoto/BirdLense-Hub/issues/601) consortium Phases 0–3 | finalize perf, funnel UI, config drift, operator system card | **Параллельная lane** «dev/operator intelligence» — не блокирует #614–#627 |
| [#622](https://github.com/Gfermoto/BirdLense-Hub/issues/622) linear fusion trim | processor safeguards, fusion_drop metrics | **Не смешивать** — LLM не меняет fusion |
| CV recovery #606–#613, storage #602–#605 | CLOSED | Только regression matrix в reviewer checklist |
| Consortium Phase 4 backlog | web services merge, mypy, OTel | LLM tooling **не** substitute для Phase 4 |

**Правило:** issues по LLM/RAG — label `dev-tooling` / `optional-operator`; never `P0-processor` или зависимость от #622.

---

## 8. Ссылки

| Ресource | URL / путь |
|----------|------------|
| Источник паттернов | https://github.com/Sumanth077/Hands-On-AI-Engineering |
| Eagle Eye (SOUL pattern) | https://github.com/Sumanth077/Hands-On-AI-Engineering/tree/main/ai_agents/eagle_eye |
| GitHub Intelligence (searchable MCP tools) | https://github.com/Sumanth077/Hands-On-AI-Engineering/tree/main/ai_agents/github_intelligence_agent |
| BirdLense MCP server | `app/web/birdlense_mcp.py` |
| OpenCode config | `opencode.json`, `.cursor/rules/opencode.mdc` |
| EPIC #601 | https://github.com/Gfermoto/BirdLense-Hub/issues/601 |
| Consortium master plan | `docs/strategy/refactoring_consortium_plan.md` |
| OpenCode agents docs | https://dev.opencode.ai/docs/agents/ |

---

*Дистилляция из research 2026-06-10. Application-код не менялся.*
