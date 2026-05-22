# Betting Bot

Telegram-бот для приёма пользовательских прогнозов на спортивные и иные события, с минимальной веб-админкой. Без биллинга и финансовой части — только события, прогнозы и статистика «сбылся / не сбылся».

> **Статус:** на этапе проектирования. Реализация ещё не начата.
> Актуальный снапшот всегда лежит в [`state/PROJECT_STATUS.md`](state/PROJECT_STATUS.md).

---

## Карта репозитория для нового читателя

Если ты впервые открыл этот репозиторий — будь то человек или ИИ-агент — читай в этом порядке:

1. **[`state/PROJECT_STATUS.md`](state/PROJECT_STATUS.md)** — что сделано прямо сейчас, что в работе, что следующее.
2. **[`docs/00-overview.md`](docs/00-overview.md)** — бизнес-цели и scope.
3. **[`docs/01-architecture.md`](docs/01-architecture.md)** — высокоуровневая архитектура с диаграммой.
4. **[`docs/`](docs/)** целиком — спецификации стека, данных, бота, админки, внешнего API, деплоя, конвенций.
5. **[`docs/adr/`](docs/adr/)** — журнал архитектурных решений с обоснованием.
6. **[`state/DECISIONS.md`](state/DECISIONS.md)** — краткий журнал решений за пределами ADR.
7. **[`state/GLOSSARY.md`](state/GLOSSARY.md)** — термины предметной области.

Если нужно узнать историю проектирования — смотри [`sessions/`](sessions/).
Если нужно поставить задачу на исполнение — смотри [`handoff/`](handoff/).

## Воркфлоу: два агента

Над проектом работают два агента и один владелец продукта:

| Роль | Кто | Где живёт | Что делает |
|---|---|---|---|
| Owner | Николай | — | Даёт команды, принимает результат |
| Проектировщик | cowork-агент (Claude в Cowork mode) | Десктоп-приложение | Проектирует, пишет спецификации, формирует задачи |
| Исполнитель | локальный Claude Code | Эта же машина | Читает задачи, пишет код, запускает тесты, коммитит и пушит в GitHub |

Обмен между агентами идёт **через папку [`handoff/`](handoff/)** в этом репозитории. Это и канал связи, и журнал. Подробный протокол — [`handoff/README.md`](handoff/README.md).

## Структура репозитория

```text
.
├── README.md                # Этот файл — карта для нового читателя
├── CLAUDE.md                # Инструкции для локального Claude Code
├── docs/                    # Стабильные спецификации
│   ├── 00-overview.md
│   ├── 01-architecture.md
│   ├── 02-tech-stack.md
│   ├── 03-data-model.md
│   ├── 04-bot-flows.md
│   ├── 05-admin-spec.md
│   ├── 06-external-api.md
│   ├── 07-deployment.md
│   ├── 08-conventions.md
│   └── adr/                 # Architecture Decision Records
├── handoff/                 # Поток задач cowork ⇄ Claude Code
│   ├── README.md            # Протокол обмена
│   ├── inbox/               # Задачи от cowork исполнителю
│   ├── outbox/              # Отчёты исполнителя cowork-агенту
│   ├── templates/           # Шаблоны task.md и report.md
│   └── archive/             # Закрытые задачи
├── sessions/                # Журнал сессий проектирования
│   └── YYYY-MM-DD-NN-slug/
│       ├── brief.md
│       ├── decisions.md
│       └── artifacts/
├── state/                   # Живой контекст
│   ├── PROJECT_STATUS.md
│   ├── BACKLOG.md
│   ├── DECISIONS.md
│   └── GLOSSARY.md
├── src/
│   ├── bot/                 # Telegram-бот (aiogram)
│   ├── admin/               # Веб-админка (FastAPI + Jinja2 + HTMX)
│   ├── shared/              # ORM-модели, конфиг, репозитории, внешний API-клиент
│   └── migrations/          # Alembic
├── tests/
│   ├── unit/
│   └── integration/
├── infra/                   # Docker Compose, Dockerfile.*, .env.example
├── scripts/                 # Утилитарные скрипты
└── .github/workflows/       # CI
```

## Технологический стек (кратко)

Python 3.12, aiogram 3.x, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16, Redis 7, Jinja2 + HTMX + Bootstrap 5, pytest, Docker Compose. Полное обоснование — [`docs/02-tech-stack.md`](docs/02-tech-stack.md) и [`docs/adr/0001-tech-stack.md`](docs/adr/0001-tech-stack.md).

## Принципы работы с этим репозиторием

- **Источник истины — файлы в репо.** Память агента — вспомогательный кеш; если расходится с файлом, прав файл.
- **Каждая сессия проектирования оставляет след** в [`sessions/`](sessions/) и обновляет [`state/PROJECT_STATUS.md`](state/PROJECT_STATUS.md).
- **Каждая задача исполнения** проходит цикл `handoff/inbox → in-progress → handoff/outbox → handoff/archive`.
- **Любое не-тривиальное решение** дублируется в [`state/DECISIONS.md`](state/DECISIONS.md); крупное архитектурное — ещё и в [`docs/adr/`](docs/adr/).
- **Git-история** — Conventional Commits; ветки feature-* per task; пушит локальный Claude Code.
