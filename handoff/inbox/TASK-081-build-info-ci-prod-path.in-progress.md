---
id: TASK-081
created: 2026-05-30
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - PR #148 (feat build metadata)
  - .github/workflows/build-images.yml
  - infra/Dockerfile.bot
  - infra/Dockerfile.web
  - src/shared/build_info.py
  - scripts/generate_build_info.sh
priority: high
estimate: M
---

# TASK-081: build-info должен работать в проде (CI/GHCR-образы), а не только при `make prod.build`

## Контекст

PR #148 добавил build-metadata (скрипт `generate_build_info.sh` → `_build_info.py`, `build_info.py`,
вывод версии на дашборд и в `/healthz`). Код чистый и безопасный (graceful fallback). **Но в реальном
проде он показывает `unknown`**, потому что:

- Прод тянет образы из GHCR: `infra/docker-compose.prod.yml` → `image: ghcr.io/nmetluk/bettgbot-bot:${IMAGE_TAG}`.
- Образы собирает CI `build-images.yml` (push→main→GHCR), который **не запускает** `generate_build_info.sh`.
- Даже если запустить «в лоб»: `actions/checkout@v4` по умолчанию `fetch-depth: 1`, detached HEAD →
  `git rev-parse --abbrev-ref HEAD` = `HEAD`, `git describe --tags` пусто. Git-детект скрипта в CI не работает.

Итого `make prod.build` (локальная сборка) — работает, а прод (GHCR) — нет. Надо прокинуть метаданные
в CI-сборку из **GitHub-контекста**, который надёжен (`github.sha`, `github.ref_name`).

## Цель

Чтобы образы, собранные `build-images.yml` и запущенные в проде, показывали реальные commit/branch/tag/
build-time на дашборде и в заголовках `/healthz`.

## Definition of Done

> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-081-report.md`. Не закрыто, пока CI зелёный и PR смёржен.
> Доделывать в рамках **той же ветки PR #148** (чтобы фича влилась цельной), либо отдельным PR — отметить в отчёте.

- [ ] **build-images.yml (оба job'а build-bot, build-web):** перед `build-push-action` посчитать
      `APP_VERSION` (из `pyproject.toml`) и `BUILD_TIME` (UTC ISO-8601) в step с output'ами; в
      `build-push-action` добавить:
      ```yaml
      build-args: |
        GIT_COMMIT=${{ github.sha }}
        GIT_BRANCH=${{ github.ref_name }}
        GIT_TAG=${{ github.ref_type == 'tag' && github.ref_name || '' }}
        BUILD_TIME=${{ steps.meta_build.outputs.build_time }}
        APP_VERSION=${{ steps.meta_build.outputs.app_version }}
      ```
- [ ] **Dockerfile.bot и Dockerfile.web:** принять `ARG GIT_COMMIT GIT_BRANCH GIT_TAG BUILD_TIME APP_VERSION`
      и пробросить в `ENV` (напр. `BUILD_GIT_COMMIT`, `BUILD_GIT_BRANCH`, `BUILD_GIT_TAG`,
      `BUILD_TIME`, `BUILD_APP_VERSION`). `COMMIT_SHORT` можно вычислить в build_info (первые 12 символов sha).
- [ ] **`src/shared/build_info.py`:** добавить **env-fallback** в `get_build_info()`. Порядок:
      (1) модуль `src.shared._build_info` (локальная сборка) → если есть, использовать;
      (2) иначе переменные окружения `BUILD_*` (CI/GHCR-образы) → если заданы, собрать `BuildInfo` из них
      (git_commit_short = первые 12 символов BUILD_GIT_COMMIT);
      (3) иначе placeholder. Остаться таким же defensive (любая ошибка → placeholder).
- [ ] **Тесты (обязательно, при здешней тест-культуре):** unit-тест на `get_build_info()`:
      - нет ни модуля, ни env → placeholder (`unknown`/`dev`);
      - заданы `BUILD_*` env → значения из env, `git_commit_short` усечён корректно;
      (модуль-кейс — по желанию). Гонять через monkeypatch env / отсутствие модуля.
- [ ] Локальный путь (`make prod.build` → `_build_info.py`) **не сломать** — приоритет модуля над env сохраняет его.
- [ ] (опц.) Подчистить мелочи из ревью PR #148: Makefile `2>/dev/null || true` маскирует ошибки
      генератора (рассмотреть убрать глушилку); heredoc в `generate_build_info.sh` сломается на ветке/теге
      с `"` (низкий риск; при желании экранировать через python json.dumps значений).
- [ ] `ruff`/`mypy`/`pytest` зелёные; PR (тот же #148 или новый) с auto-merge по зелёному CI; `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Проверка (в отчёт)

- [ ] Подтвердить, что образ, собранный с build-args, на рантайме отдаёт реальные значения: либо локально
      `docker build --build-arg GIT_COMMIT=… … && docker run … curl -sI /healthz | grep X-Build`, либо
      описать, как проверено. Не «CI зелёный» на словах — показать фактические заголовки/значения.

## Вне скоупа

- Менять набор полей build-info или UI дашборда (он уже ок).
- Триггерить сборку на тегах, если сейчас только `push: main` — отдельным решением владельца.

## Ссылки

- `infra/docker-compose.prod.yml` — `image: ghcr.io/nmetluk/bettgbot-{bot,web}` (прод = GHCR)
- `.github/workflows/build-images.yml` — `on: push: branches:[main]`, `build-push-action`, `context: .`
- PR #148 — базовая реализация (локальный путь рабочий, CI — нет)
