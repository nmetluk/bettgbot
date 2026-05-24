# Решения — task-030-review

## Новое решение

1. **Усиление move-семантики через DoD-чеклист в `handoff/templates/task.md`.** Подсекция в `handoff/README.md` (добавлена в cleanup перед TASK-030) не сработала — CC не перечитывает README перед каждой задачей. Перенос правила в **сам template задачи** как DoD-пункт с маркером 🚨 делает его видимым в каждой новой `inbox/TASK-NNN-*.md`, CC обязан выполнить. Аналогично добавлен 🚨 для `make backup`. Если и это не сработает в TASK-031+ — переходим к git pre-commit hook'у / CI-check.

## Подтверждённые keep (review TASK-030)

| # | Решение | Обоснование |
|---|---|---|
| 1 | `_SHARED_PROCESSORS` = [`merge_contextvars`, `add_log_level`, `TimeStamper(iso, utc)`] | Минимальный набор для prod. `merge_contextvars` первым — корректно для context-pull. |
| 2 | `ProcessorFormatter.wrap_for_formatter` последним в structlog processors | Стандартный pattern для смешанного structlog+stdlib. |
| 3 | `foreign_pre_chain=_SHARED_PROCESSORS` для stdlib-handler | uvicorn/aiogram/sqlalchemy получают те же timestamp/level/context, без отдельной конфигурации. |
| 4 | `root.handlers.clear()` перед `addHandler` | Идемпотентность — повторный `configure_logging` в тестах не плодит дубликаты. |
| 5 | `LOG_FORMAT=console` дефолт в Settings + `.env.example` | Dev-friendly. Prod явно переопределяет через `environment: LOG_FORMAT: json` в compose.prod.yml. |
| 6 | Override `LOG_FORMAT` на уровне service (compose.prod.yml), не env_file | Чище: prod-специфика в prod.yml, не в общем `.env`. |
| 7 | Docker `json-file` driver с `max-size/max-file` остаётся (заложено в TASK-027) | Ротация логов на уровне инфры, дублировать в коде через `TimedRotatingFileHandler` не нужно. |

## Тех-долг (зафиксировано)

- **`StackInfoRenderer` + `format_exc_info`** в `_SHARED_PROCESSORS` — добавить, если в проде traceback'и в JSON-логах окажутся скудными. Сейчас structlog даёт минимальный fallback, может быть достаточно.
- **CI-check на workflow-violation `inbox vs archive`** — если 🚨 в DoD-template не сработает (TASK-031+ покажет), реализовать git pre-commit hook или `.github/workflows/` step, который проверяет: при наличии `handoff/archive/TASK-NNN-*/` в diff — не должно быть `handoff/inbox/TASK-NNN*.md`.
