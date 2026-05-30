---
task: TASK-082
completed: 2026-05-30
author: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/152
branch: feature/TASK-082-release-0.1.0-prep
related_commits:
  - f82fc15 feat(TASK-082): release v0.1.0 prep (version bump + CHANGELOG)
---

# Отчёт по TASK-082: подготовка релиза v0.1.0

## Сводка

Полностью выполнена подготовка к релизу v0.1.0: версия bumped, CHANGELOG составлен, PROJECT_STATUS обновлён. PR смёржен, main синхронизирован.

## Что сделано

### 1. Bump версии
- `pyproject.toml`: `version = "0.0.0"` → `"0.1.0"`
- Проверено: больше нигде `0.0.0` не захардкожено (grep показал только `src/admin/app.py`)

### 2. Исправлена захардкоженная версия в admin
- `src/admin/app.py`: `version="0.0.0"` → `version=info.app_version` (динамически из `get_build_info()`)
- FastAPI теперь показывает актуальную версию из build-info

### 3. CHANGELOG.md создан
- Формат Keep a Changelog / SemVer
- Секция `## [0.1.0] - 2026-05-31`:
  - **Added**: админка v2, broadcast, analytics, leaderboard, build-info, dashboard counters, hands-free merge, MVP foundation, prod infra, reminder system
  - **Changed**: timezone strategy (aware-UTC), CSP self-hosting, per-service env segregation
  - **Fixed**: event detail 500, admin login, a11y, form padding, CSRF stale cookie, session cookie, archive format, handoff consistency, reminder misfire, dispatch log retention
  - **Security**: CSRF hardening, session security, CSP tightening, HTML escaping, proxy headers, secrets validation, offsite encrypted backup, security scanning, IDOR fix, no-domain lockdown

### 4. state/PROJECT_STATUS.md обновлён
- Обновлено: 2026-05-31 (TASK-082)
- Текущая фаза: ✅ v0.1.0 готов к релизу
- Добавлены записи про TASK-081 и TASK-082 в «Что готово (последние)»

## Качественные gate (DoD)

- [x] `ruff check` — clean
- [x] `ruff format --check` — clean (183 files)
- [x] `mypy src/shared` — clean (47 files)
- [x] `pytest` — **471 passed** (warnings acceptable, no failures)
- [x] Build-info тесты проходят (version из env/pyproject)
- [x] PR открыт (#152) и смёржен
- [x] Auto-merge включён, CI зелёный
- [x] `main` синхронизирована

## Изменённые файлы

```
pyproject.toml                    # version 0.0.0 → 0.1.0
src/admin/app.py                  # dynamic version from build_info
CHANGELOG.md                      # NEW
state/PROJECT_STATUS.md           # v0.1.0 readiness snapshot
handoff/inbox/...in-progress.md   # moved from TASK-082.md
uv.lock                           # version bump
```

## Что не сделано (вне скоупа)

- Git-тег `v0.1.0` — **ручной шаг владельца**
- GitHub Release — **ручной шаг владельца** (публикация триггерит deploy-prod.yml)
- Деплой — **ручный шаг владельца**

## После merge (шаги владельца)

1. **Дождаться сборки GHCR-образов** — `build-images.yml` соберёт с `APP_VERSION=0.1.0`
2. **Создать тег `v0.1.0`** — на merge-коммите (или Draft Release без деплоя)
3. **Опубликовать Release** — когда готов к деплою (автодеплой через `deploy-prod.yml`)

## Открытые вопросы

Нет. Задача выполнена полностью по спецификации.

## Предложение для PROJECT_STATUS.md

Добавлена строка:
```markdown
- **TASK-082 ЗАКРЫТ (2026-05-31) — подготовка релиза v0.1.0.** `pyproject.toml` version bumped до 0.1.0; захардкоженная версия в `admin/app.py` заменена на динамическую из `get_build_info()`; создан `CHANGELOG.md` с полным списком изменений; `state/PROJECT_STATUS.md` обновлён. После merge CI пересоберёт GHCR-образы с APP_VERSION=0.1.0, build-info покажет корректную версию.
```

## Метрики

- Время: ~30 минут
- Тесты: 471 passed
- Изменения: +64 -7 строк (6 файлов)
- PR: #152, merge 2026-05-30T22:45:53Z
