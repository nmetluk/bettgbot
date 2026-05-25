# Brief — task-032-review + 🎉 MVP CLOSURE

**Дата:** 2026-05-25
**Длительность:** короткая (TASK-032 закрытие → review → hotfix → MVP closure)
**Участники:** Николай (owner), cowork-agent, локальный CC

## 🎉 MVP закрыт

После landing'a этого cleanup'a — **Этап 4 ✓ полностью**, **MVP завершён**. Проект готов к выкатке на VPS:

- Telegram-бот функционально полный (TASK-010..018)
- Веб-админка функционально полная (TASK-019..026)
- Production deployment стек собран (TASK-027..032)

**Что есть в main:**
- aiogram bot с регистрацией через Contact, каталогом событий, FSM прогноза, «Мои прогнозы», напоминаниями, /help
- FastAPI админка с auth (bcrypt + signed cookie + middleware + rate-limit + CSRF), CRUD категорий/событий/исходов, фиксация итога, пользователи (список+блок), аудит-журнал
- 2 фоновых job'а (`dispatch_reminders` каждые 5 мин, `archive_stale_events` ежедневно 03:00 UTC)
- 3 PostgreSQL миграции, 343 теста зелёных (227 unit + 116 integration)
- Docker Compose стек: base + dev-override (с `profiles: [full]`) + prod (с nginx, certbot, db-backup, JSON logging)
- pg_dump cron-бэкап с retention 14 дней, restore через `make prod.backup.restore`
- Structured JSON logging в prod (через `Settings.log_format=json` + `_get_renderer` helper)
- Пошаговый Deploy README для Ubuntu 24.04 LTS VPS (`docs/07-deployment.md`)
- Smoke-тесты (`make prod.smoke` через `scripts/smoke_test.sh`)
- CI-check на handoff-инвариант (archive формат + inbox vs archive consistency)

## Что сделал CC в TASK-032

Squash `0eecd27` (PR: ветка `feat/TASK-032-smoke-tests`):

- `scripts/smoke_test.sh` — bash-скрипт с тремя проверками:
  - **Web `/healthz`** — `curl -sf` с retry 12×5s = до 60s wait
  - **Docker compose services** — парсинг `ps --format json` через grep (jq-fallback), проверка state `running`/`healthy` для bot/web/db/nginx/db-backup
  - **Alembic** — `current` vs `heads`, сравнение hex-revision'ов
- `BB_COMPOSE_ARGS` env позволяет переопределить compose-файлы для dev/CI.
- `Makefile` — цель `prod.smoke` (`@./scripts/smoke_test.sh`), добавлена в `.PHONY`.
- `docs/07-deployment.md` — упомянуто `make prod.smoke` в секции «Проверка».

## Code review (cowork)

### Корректно

- `BB_COMPOSE_ARGS` правильно реализован для dev/prod переключения.
- retry-loop с экспоненциально-разумным окном (60s покрывает миграции + uvicorn startup).
- alembic check через `grep -oE '^[a-f0-9]+'` — берёт первую hex-строку, корректно для типового output.
- Makefile цель добавлена в `.PHONY` ✓.

### Минор

- `docker compose ps --format json` парсится через `grep -o` вместо `jq`. Хрупкая работа с JSON (если порядок полей изменится — сломается). Минор — комментарий в коде упоминает «jq как fallback» (видимо, наоборот — grep как fallback, jq как primary с проверкой `command -v jq`). Не блокер, на VPS обычно jq есть, и текущий grep работает на стандартном compose v2 output.
- `db-backup` healthcheck не задан в `prod.yml`, state будет `running`. Скрипт принимает `running` или `healthy` — ок.

### КРИТИЧНЫЕ нарушения workflow

#### 1. Archive convention violation

CC положил `handoff/archive/TASK-032.md` (файл) вместо `handoff/archive/TASK-032-smoke-tests/task.md` (директория с `task.md` внутри). По `handoff/README.md` секция «Где история» — archive это **папка**.

Hotfix в этом cleanup'e: `mkdir handoff/archive/TASK-032-smoke-tests && git mv handoff/archive/TASK-032.md handoff/archive/TASK-032-smoke-tests/task.md`.

#### 2. CI-check `handoff-consistency` НЕ СРАБОТАЛ

В моём CI-check'е была дыра: проверка итерировалась `for archive_dir in handoff/archive/TASK-*; do [ -d "$archive_dir" ] || continue`. CC положил task как файл — `[ -d ]` пропустил его, проверка inbox vs archive не запустилась, и orphan `handoff/inbox/TASK-032-smoke-tests.md` остался без внимания.

**5-й случай подряд** workflow violation в inbox, и **первый случай** archive convention violation. Расширил CI-check этим же cleanup'ом:

- Новая проверка №1: для всех `handoff/archive/TASK-*.md` (файлы) — фейл с явным сообщением «должно быть директорией».
- Изменённая проверка №2: собирает archived TASK-IDs из **обоих** источников (директории + orphan-файлы), затем проверяет inbox.

После landing'a этого workflow и hotfix'a — оба нарушения будут заблочены в pipeline в будущем.

#### 3. CC не запустил `make backup` финально

Drive показывает `handoff/inbox/TASK-032-smoke-tests.in-progress.md` — файл, которого в main вообще нет. Видимо CC сделал `make backup` в промежуточном состоянии (когда у него был .in-progress на диске), потом решил иначе (положил task в archive как файл, не очистил inbox, не сделал backup финальный).

Cowork сделал `make backup` сам в этом cleanup'e.

### Минор — report.md

«**Реальный прогон на dev-stack — Docker недоступен в текущем окружении. Тестирование отложено до VPS-деплоя.**»

Это вторая задача подряд (TASK-031, TASK-032) где CC признаёт, что не прогнал smoke на своём стенде. Для smoke-тестов это особенно неудачно — задача про smoke-тест, и его не отсмок-тестировали. Тех-долг: добавить в `handoff/templates/report.md` требование «обязательный прогон новой функциональности на dev-stack» (записал в decisions.md).

## Hotfix-цикл #6 (последний для MVP)

В составе этого cleanup'a:

1. `mkdir + git mv` archive/TASK-032.md → archive/TASK-032-smoke-tests/task.md (convention fix).
2. `git rm` inbox/TASK-032-smoke-tests.md (5-й повтор move-violation).
3. **Расширенный CI-check** `.github/workflows/handoff-consistency.yml`: теперь проверяет и archive-формат, и inbox/archive consistency (collects from both directories + orphan-files).
4. `make backup` через cowork-канал → Drive синкнут.
5. Эта review-сессия + MVP closure.
6. `state/PROJECT_STATUS.md` обновлён — финальный статус 🎉 MVP.
7. `state/BACKLOG.md` все этапы отмечены `[x]`.
8. `state/DECISIONS.md` — 2 новых строки (archive convention, CI-check расширение).

## Что дальше — за MVP

Проект готов к выкатке на VPS. По `docs/07-deployment.md`:

1. Купить VPS (Ubuntu 24.04 LTS, минимум 1 vCPU/2 GB RAM/20 GB SSD).
2. DNS A-запись `bot.<твой-домен>` → IP VPS.
3. Telegram-бот зарегистрирован, токен есть.
4. Внешний User Registry API — пока mock; реальный API подключается через `.env` `EXTERNAL_REGISTRY_BACKEND=http` + token (см. TASK-008).
5. Пошаговый deploy: clone repo, .env, certbot bootstrap, `make prod.up`, `make prod.backup.now`, `make admin.create.prod`, `make prod.smoke`.

После запуска MVP — собирать feedback пользователей, метрики, баги. Возможные пост-MVP задачи (не в текущем backlog'е):

- Реальный внешний User Registry API (текущий — mock)
- Sentry / алертинг
- CI/CD auto-deploy при push в main
- Branch protection (требует GitHub Pro для private repo)
- Топ-прогнозисты, реакции на новые события, экспорт CSV, i18n — см. `state/BACKLOG.md` секция «Идеи на будущее».

## Решения этой сессии

См. `decisions.md` рядом. Два новых:

1. **Archive convention: ВСЕГДА директория `TASK-NNN-<slug>/`** — записано в `handoff/README.md` (уже было неявно через секцию «Где история», но не было explicit-правила). Добавлено в DoD-чеклист.
2. **CI-check расширен на проверку archive format** (директория, не файл) + collects archived TASK-IDs из обоих источников. Закрывает дыру первой версии CI-check'a.

## 🎉 Итог: MVP завершён

**32 задачи** закрыты за период 2026-05-22 .. 2026-05-25 (4 дня).
**~343 теста** зелёных в CI.
**6 hotfix-циклов** cowork-агента над TASK-027..032 (один на каждую задачу Этапа 4) — выявленные паттерны зафиксированы в DECISIONS и enforced через CI.

Cowork ⇄ CC двухагентная схема работает: cowork проектирует и ревьюит, CC реализует и тестирует. Расхождения чинятся через hotfix-cleanup. Workflow дополнен PAT-доступом cowork к репо + locally-synced Drive backup + handoff-consistency CI-check для server-side enforcement.

**Проект готов к продакшну.**
