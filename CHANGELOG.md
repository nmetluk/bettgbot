# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-06-04

### Security

- **Бамп `aiohttp` → 3.14.0** (TASK-110) — закрыты `CVE-2026-34993` и `CVE-2026-47265` (транзитивная зависимость через `aiogram`; форсируется через `[tool.uv] override-dependencies`).

## [0.2.1] - 2026-06-03

Деплой-харднинг бэкап-стека по итогам прод-аудита v0.2.0 (двухсерверная топология).

### Fixed

- **`backup_run` навсегда «running»** (TASK-099 hotfix) — `start_backup_run` склеивал id со статус-тегом `INSERT 0 1` → UPDATE до `success/failed` падал. Чинит учёт бэкапов, статус heartbeat и репликацию.
- **Пути репликации** (TASK-108) — `BACKUP_LOCAL_DIR` теперь точка монтирования контейнера (`/backups`); дампы на Admin пишутся в host bind-mount, доступный ssh-источнику (раньше репликация копировала «в пустоту»).
- **Date-зависимые тесты** (TASK-102) — устранены «тайм-бомбы» через инъекцию `reference_now` (детерминизм без привязки к реальному календарю).

### Changed

- **Бот — только на воркере** (TASK-107) — сервис `bot` в Admin-композиции вынесен за профиль; на выделенном воркере поднимается через `docker-compose.bot-only.yml`.

### Added

- **Воркерный деплой** (TASK-104) — `infra/docker-compose.bot-only.yml` + `make prod.bot.*` для отдельного bot-хоста.
- **Обогащение админ-статистики** (TASK-098) — дельты к прошлым суткам, DAU, топ-3 событий, точность закрытых, конверсия; в пост-итоговой сводке — популярный vs верный исход и % участия.
- **Раздел деплоя**: двухсерверная топология (Admin + Worker) в `docs/07-deployment.md`.

### Security

- **Порты Postgres/Redis закрыты по умолчанию** (TASK-103) — экспозиция вынесена в opt-in overlay `infra/docker-compose.expose-db.yml`, применяемый ТОЛЬКО в split-топологии и ТОЛЬКО вместе с `scripts/apply-bot-firewall.sh` (DOCKER-USER whitelist по IP воркера). Одно-серверные/no-domain деплои остаются закрытыми.

## [0.2.0] - 2026-06-03

### Added

- **Админская статистика через бота** (TASK-097) — ежедневный дайджест в 16:00 `Europe/Moscow` за последние 24ч (всего пользователей / новых / прогнозов) и после фиксации итога события — сводка (всего/угадали/распределение по исходам) + CSV угадавших, во все `ADMIN_TELEGRAM_CHAT_IDS`. Развязка web↔bot через колонку `events.result_notified_at`.
- **Мониторинг бэкапов (heartbeat)** (TASK-099) — таблица `backup_run` (миграция 0008), ежечасный bot-джоб проверяет видимость Postgres/Redis и свежесть последнего бэкапа, шлёт OK/ALERT в админ-чат (флаг `BACKUP_HEARTBEAT_ENABLED`).
- **Репликация бэкапа на bot-сервер** (TASK-100) — pull свежего дампа с Admin-сервера по `rsync`+SSH, отметка `backup_run.replicated_at` (флаг `BACKUP_REPLICATION_ENABLED`).

### Changed

- **Открытая регистрация** (TASK-096, ADR-0006) — проверка по внешнему реестру отменена: регистрируется любой, кто поделился контактом; единственный отказной путь — `is_blocked`.
- **Ежечасный бэкап БД** (TASK-101) — контейнер `db-backup` переведён с суточного на ежечасный дамп; интервал и retention через env (`BACKUP_INTERVAL_SECONDS`, `BACKUP_RETENTION_DAYS`).
- **Процесс CI/merge** — в DoD добавлены rebase на свежий `main`, явный auto-merge для feature-веток и `ruff format --check`.

### Removed

- **Внешний реестр пользователей** (`src/shared/external/`, HTTP/mock-клиенты, исключения, env `EXTERNAL_*`/`MOCK_REGISTRY_*`) — удалён полностью вместе с проверкой при регистрации.

## [0.1.0] - 2026-05-31

### Added

- **Admin v2 redesign** — Complete visual refresh with Alpine.js, dark mode, density controls, and design tokens (TASK-053..TASK-056)
- **Broadcast system** — Segment-based announcements to users with delivery tracking and scheduler integration (TASK-061)
- **Analytics screen** — Prediction trends, category accuracy, funnel metrics, and top events (TASK-059, TASK-060)
- **Leaderboard** — User rankings with accuracy metrics and medals (TASK-058)
- **Build metadata** — Version, commit, branch, and build-time exposed via `/healthz` headers and dashboard (TASK-081)
- **Dashboard counters** — Real-time counts for categories, events, users, and predictions (TASK-043)
- **Hands-free merge gate** — Branch protection + auto-merge for CI-passed PRs (TASK-077)
- **MVP foundation** — Telegram bot (registration, catalog, predictions, reminders) and web admin (auth, CRUD, audit) (TASK-001..TASK-032)
- **Production infrastructure** — Docker images, CI/CD, security scans, monitoring, backups (TASK-027..TASK-042)
- **Reminder system** — User-customizable notification intervals with scheduler dispatch (TASK-015..TASK-017)

### Changed

- **Timezone strategy** — Unified aware-UTC approach across all services and templates (TASK-067)
- **CSP self-hosting** — Migrated from CDN (jsdelivr) to self-hosted scripts with SRI (TASK-079)
- **Per-service env segregation** — Bot and web services now have isolated secret requirements (TASK-050)

### Fixed

- **Event detail 500** — Eager-load relationships to prevent N+1 query errors (TASK-074, TASK-076)
- **Admin login in production** — CSRF and proxy-protocol fixes (TASK-062, TASK-063)
- **A11y issues** — Contrast ratios, aria-hidden icons, input borders (TASK-071, TASK-072)
- **Form padding consistency** — Unified event form card spacing (TASK-075)
- **CSRF stale cookie lockout** — Fixed TTL enforcement and rotation behavior (TASK-068, TASK-069)
- **Session cookie read mismatch** — Fixed naive/aware datetime inconsistency (TASK-063)
- **Archive format** — Consolidated reports in archive directories (TASK-078)
- **Handoff consistency** — CI guards for transient inbox suffixes (TASK-080)
- **Reminder misfire handling** — Catchup after restart with wider window (TASK-049)
- **Dispatch log retention** — Cleanup job and indexes (TASK-048)

### Security

- **CSRF hardening** — Rotation on POST, explicit TTL, stale-cookie lockout fix (TASK-035, TASK-068, TASK-069)
- **Session security** — Signed cookies with proper TTL and environment-based Secure flag (TASK-020, TASK-063)
- **CSP tightening** — Self-hosted scripts with SRI, removed unsafe inline scripts (TASK-037, TASK-057, TASK-079)
- **HTML escaping** — User content in Telegram messages (TASK-036)
- **Proxy headers** — Nginx rate-limit and timeout protections (TASK-038)
- **Secrets validation** — Prod secrets required at startup (TASK-034)
- **Offsite encrypted backup** — rclone + age with weekly verification (TASK-039)
- **Security scanning** — CI integration of bandit, pip-audit, trivy, gitleaks (TASK-040)
- **IDOR fix** — Outcomes CRUD authorization (TASK-033)
- **No-domain mode lockdown** — Restricted to localhost only (TASK-047)

[0.1.0]: https://github.com/nmetluk/bettgbot/compare/v0.0.0...v0.1.0
