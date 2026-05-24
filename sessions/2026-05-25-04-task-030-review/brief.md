# Brief — task-030-review (JSON logging)

**Дата:** 2026-05-25
**Длительность:** короткая
**Участники:** Николай (owner), cowork-agent, локальный CC

## Что было сделано в TASK-030

CC реализовал (squash `76755b9`, PR #82; archive+report `34ba0bc`):

- `src/shared/config.py` — поле `log_format: Literal["json", "console"]` с дефолтом `"console"` (dev-friendly, prod явно переопределяет).
- `src/shared/logging.py` — рефактор `configure_logging(level, format)`:
  - `_SHARED_PROCESSORS` = [`merge_contextvars`, `add_log_level`, `TimeStamper(fmt="iso", utc=True)`].
  - `_get_renderer(format)` — `JSONRenderer()` или `ConsoleRenderer(colors=True)`.
  - Структура для смешанного structlog+stdlib через `ProcessorFormatter.wrap_for_formatter` + `foreign_pre_chain` — uvicorn/aiogram/sqlalchemy идут в JSON в prod автоматически.
  - Идемпотентность через `root.handlers.clear()` перед добавлением (важно для тестов).
- `tests/unit/test_logging.py` — 5 unit-тестов проверяют processor chain для обоих форматов.
- `infra/.env.example` — `LOG_FORMAT=console` с комментарием dev/prod.
- `infra/docker-compose.prod.yml` — bot и web получили `environment: LOG_FORMAT: json` (override на уровне сервиса, не env_file).

## Code review (cowork)

### Корректность

Реализация **правильная по архитектуре**:

- `wrap_for_formatter` стоит последним в structlog processors — корректный pattern для перевода structlog-записей через stdlib-formatter.
- `foreign_pre_chain` применяется к stdlib-логгерам — записи uvicorn/aiogram автоматически получают `timestamp`/`level`/`merge_contextvars`.
- `cache_logger_on_first_use=True` — стандартная оптимизация.
- `TimeStamper(utc=True)` — корректно для коллекции с разных серверов.

### Минор — exception handling в JSON

В `_SHARED_PROCESSORS` **нет** `structlog.processors.StackInfoRenderer()` и `structlog.processors.format_exc_info`. Без них исключения в JSON-логах могут выглядеть скудно (не будет structured traceback). Не блокер для MVP — поведение по умолчанию structlog «не пусто, но не оптимально». Зафиксировано в тех-долге; добавим если станет реальной проблемой в проде.

### Workflow violation #3 — повтор

CC снова оставил две копии TASK-030 в inbox после move в archive:

- `handoff/inbox/TASK-030-json-logging.md` (исходный файл)
- `handoff/inbox/TASK-030.in-progress.md` (rename CC)
- `handoff/archive/TASK-030-json-logging/task.md` (правильно)

**Третий случай подряд** (TASK-028, TASK-029, TASK-030). Несмотря на explicit-правило, добавленное в `handoff/README.md` подсекция «Move-семантика inbox → archive» при cleanup перед TASK-030 — CC не сработал по нему. Гипотеза: CC прочитал README **один раз** в начале работы над репо и не перечитывает его каждый раз. Подсекция в README осталась невидимой.

**Усиление:** правило перенесено **в `handoff/templates/task.md`** как DoD-пункт с маркером 🚨. Теперь оно появляется **в каждой новой задаче** в inbox, и CC его видит как часть Definition of Done, которую обязан выполнить. Если и это не сработает (TASK-031 покажет) — переходим к pre-commit hook'у или CI-проверке.

Также в DoD-чеклист добавлен пункт «🚨 `make backup` после merge в main». CC и его не запустил в TASK-030 (Drive backup отстал) — то же самое усиление через template.

### Drive backup отстал

После TASK-030 merge `make backup` не выполнялся. Cowork-агент сам сделал в этом cleanup'e (через свой sandbox-канал, File Stream разморожен).

## Hotfix-цикл (четвёртый подряд)

В составе этого pre-task cleanup перед TASK-031:

- `git rm` двух копий TASK-030 в inbox.
- `handoff/templates/task.md` — два новых DoD-пункта (🚨 move-семантика, 🚨 make backup).
- `make backup` через cowork-канал → Drive синхронизирован.
- Review-сессия TASK-030 (этот документ).
- `state/PROJECT_STATUS.md` + `state/BACKLOG.md` — TASK-030 closed, TASK-031 в инбоксе.
- `handoff/inbox/TASK-031-deploy-readme.md` — спека на пошаговый Deploy README для VPS.

## Решения этой сессии

См. `decisions.md` рядом.

## Открытые вопросы / тех-долг

- **`StackInfoRenderer` + `format_exc_info`** в shared processors — добавить если в проде столкнёмся со скудным выводом traceback'ов.
- **Если TASK-031 снова покажет workflow violation** в inbox/archive move — переходим к git pre-commit hook или CI-check, который блочит merge при наличии `TASK-NNN*` в inbox при наличии `TASK-NNN/` в archive в том же diff'е.
