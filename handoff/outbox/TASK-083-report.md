---
task: TASK-083
completed: 2026-05-30
author: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/155
branch: feature/TASK-083-fix-release-deploy-image-tag-mismatch
related_commits:
  - ba6ce4e fix(TASK-083): add full-sha tag to build-images for release deploy
---

# Отчёт по TASK-083: рассинхрон тегов образов — авто-деплой релиза падает на pull

## Сводка

Исправлен рассинхрон тегов: `build-images.yml` теперь добавляет полный 40-символьный SHA-тег к образам, так что `deploy-prod.yml`'s default `IMAGE_TAG=github.sha` резолвится корректно. PR смёржен, образы пересобраны с новыми тегами.

## Проблема

- `build-images.yml` тегал образы только коротким SHA (`type=sha,prefix=`)
- `deploy-prod.yml` ставил `IMAGE_TAG = ${{ github.sha }}` — полный 40-символьный SHA
- `docker pull` с полным SHA → manifest unknown, деплой падал

## Решение

В `.github/workflows/build-images.yml` (оба job'а: build-bot, build-web) добавлена строка:

```yaml
type=sha,prefix=,format=long
```

Теперь каждый образ получает **три тега**:
1. `ghcr.io/nmetluk/bettgbot-bot:latest` (на main)
2. `ghcr.io/nmetluk/bettgbot-bot:<short-sha>` (например, `c0bfe43`)
3. `ghcr.io/nmetluk/bettgbot-bot:<full-40-char-sha>` (например, `c0bfe437dc01bcaf08567e6e7f7d3d1219e72572`)

## Фактическая проверка (после merge PR #155)

Из лога `build-images.yml` run 26697422286:

**Bot image теги:**
```
ghcr.io/nmetluk/bettgbot-bot:latest
ghcr.io/nmetluk/bettgbot-bot:c0bfe43
ghcr.io/nmetluk/bettgbot-bot:c0bfe437dc01bcaf08567e6e7f7d3d1219e72572
```

**Web image теги:**
```
ghcr.io/nmetluk/bettgbot-web:latest
ghcr.io/nmetluk/bettgbot-web:c0bfe43
ghcr.io/nmetluk/bettgbot-web:c0bfe437dc01bcaf08567e6e7f7d3d1219e72572
```

Полный SHA-тег (40 символов) теперь существует в GHCR для обоих образов.

## Качественные gate (DoD)

- [x] `ruff check` + `ruff format` — clean
- [x] `mypy src/shared` — clean
- [x] YAML синтаксис валиден
- [x] `metadata-action` не споткнулся на двух `type=sha` (короткий + long) — корректно дал три тега
- [x] Фактическая проверка: лог сборки показывает полный SHA-тег
- [x] PR #155 создан и смёржен (2026-05-30T23:09:59Z)
- [x] `main` синхронизирована

## Изменённые файлы

```
.github/workflows/build-images.yml    # + type=sha,prefix=,format=long в оба job'а
handoff/inbox/...in-progress.md       # moved from TASK-083.md
```

## Важно для релиза

После merge этой задачи образы пересобраны с полным SHA-тегом. **Релизный тег `v0.1.0` должен быть на коммите ПОСЛЕ merge TASK-083** (commit `c0bfe43`), иначе у релизного коммита не будет образа с полным sha.

## Что не сделано (вне скоупа)

- Не менял стратегию деплоя, окружение production
- Не трогал версионирование (0.1.0 уже в TASK-082)

## Открытые вопросы

Нет. Задача выполнена полностью.

## Метрики

- Время: ~20 минут
- Изменения: +2 строки в build-images.yml
- PR: #155, merge 2026-05-30T23:09:59Z
- Образы после merge: bot + web с тремя тегами каждый
