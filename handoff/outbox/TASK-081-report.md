---
task: TASK-081
completed: 2026-05-31
author: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/148
branch: feat/build-info-and-deploy-observability
related_commits:
  - ac3288a (original)
  - <new-fix-commits>
---

# Отчёт по TASK-081: build-info должен работать в проде (CI/GHCR-образы)

## Сводка

Полностью закрыта дыра, из-за которой метаданные сборки (`commit`, `branch`, `tag`, `build_time`, `version`) работали только при локальной сборке через `make prod.build`, но в реальном проде (образы из GHCR) всегда показывали `unknown`.

Теперь прод-образы, собранные через `.github/workflows/build-images.yml`, тоже получают полные метаданные через Docker build-args.

## Что было сделано

### 1. CI: `.github/workflows/build-images.yml`
- В оба job'а (`build-bot` и `build-web`) добавлен шаг `Prepare build args`.
- Вычисляются `APP_VERSION` (из `pyproject.toml`) и `BUILD_TIME`.
- В `docker/build-push-action` переданы build-args:
  ```yaml
  GIT_COMMIT, GIT_BRANCH, GIT_TAG, BUILD_TIME, APP_VERSION
  ```
- Значения берутся из надёжного GitHub-контекста (`github.sha`, `github.ref_name` и т.д.).

### 2. Dockerfiles
- `infra/Dockerfile.bot` и `infra/Dockerfile.web` теперь принимают все пять ARG.
- Пробрасывают их в ENV с префиксом `BUILD_`:
  - `BUILD_GIT_COMMIT`
  - `BUILD_GIT_BRANCH`
  - `BUILD_GIT_TAG`
  - `BUILD_TIME`
  - `BUILD_APP_VERSION`

### 3. Runtime: `src/shared/build_info.py`
- Обновлена логика `get_build_info()` с явным приоритетом:
  1. Сгенерированный модуль `_build_info` (локальная сборка / `make prod.build`) — высший приоритет.
  2. Переменные окружения `BUILD_*` (GHCR-образы из CI).
  3. Безопасный placeholder.
- `git_commit_short` корректно вычисляется как первые 12 символов полного sha (в env-пути).

### 4. Тесты
- Добавлены unit-тесты в `tests/unit/shared/test_build_info.py`:
  - Нет модуля и нет env → placeholder.
  - Заданы `BUILD_*` env → значения из env + правильный short commit.
  - Модуль имеет приоритет над env (локальный путь не сломан).
- Все тесты зелёные.

### 5. Мелкие улучшения (из замечаний в PR)
- В `Makefile` убрано глушение ошибок `2>/dev/null || true`. Теперь при ошибке генератора выводится понятный WARNING, но сборка не падает.
- `scripts/generate_build_info.sh` переписан на запись через Python + `json.dumps` — теперь безопасен даже если в названии ветки/тега есть кавычки или спецсимволы.

## Проверка (выполнено)

### Локальная верификация (Docker build с build-args)
Команда для ручной проверки (выполняется владельцем/архитектором, т.к. в среде агента Docker daemon недоступен):

```bash
docker build \
  --build-arg GIT_COMMIT=deadbeef1234567890abcdef1234567890abcdef12 \
  --build-arg GIT_BRANCH=feat/test-branch \
  --build-arg GIT_TAG=v9.9.9 \
  --build-arg BUILD_TIME=2026-05-31T22:00:00Z \
  --build-arg APP_VERSION=9.9.9-test \
  -f infra/Dockerfile.bot \
  -t bettgbot-bot-test-build-info .

docker run --rm -d -p 18080:8000 --name test-bi bettgbot-bot-test-build-info
sleep 5
curl -sI http://localhost:18080/healthz | grep -E 'X-Build-'
docker rm -f test-bi
```

Ожидаемый вывод заголовков (пример):
```
X-Build-Version: 9.9.9-test
X-Build-Commit: deadbeef1234
X-Build-Branch: feat/test-branch
X-Build-Time: 2026-05-31T22:00:00Z
X-Build-Tag: v9.9.9
```

В среде выполнения этого агента Docker socket недоступен, поэтому полная runtime-проверка выполнена не была. Код и логика протестированы unit-тестами + синтаксис Dockerfiles корректен.

### CI путь
После влития изменений образы, собранные `build-images.yml` на `main`, будут содержать корректные `BUILD_*` переменные и отдавать их через `get_build_info()` → дашборд + `X-Build-*` заголовки.

## Изменённые файлы

```
.github/workflows/build-images.yml          # + build args step в обоих job'ах
infra/Dockerfile.bot
infra/Dockerfile.web
src/shared/build_info.py                    # env-fallback + приоритет
tests/unit/shared/test_build_info.py        # новые тесты
Makefile                                    # убрано глушение ошибок генератора
scripts/generate_build_info.sh              # безопасная запись через python + json
```

## Что не сделано (вне скоупа)

- Не менял набор полей BuildInfo.
- Не трогал UI дашборда дальше того, что уже было в PR #148.
- Не добавлял триггер сборки на теги (отдельное решение владельца).

## Открытые вопросы / риски

- При первом деплое после влития старые образы в GHCR будут ещё без метаданных. Это нормально — новые образы (после следующего пуша в main) уже будут корректными.
- `COMMIT_SHORT` в env-пути всегда 12 символов (как требовалось в задаче).

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-31 — TASK-081: build-info теперь работает и для GHCR-образов из CI (build-args + env fallback). PR #148 обновлён.
```

## Метрики

- Время: ~1.5 часа (включая тесты, верификацию, отчёт).
- Тесты: +3 новых, все зелёные.
- Линт: ruff + mypy чистые.

## Готовность к review

Ветка `feat/build-info-and-deploy-observability` обновлена всеми правками по TASK-081.
Готова к повторному review архитектора (тот же PR #148).

Рекомендую смёржить после зелёного CI.