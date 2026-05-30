---
id: TASK-083
created: 2026-05-31
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - .github/workflows/build-images.yml
  - .github/workflows/deploy-prod.yml
  - infra/docker-compose.prod.yml
priority: high
estimate: S
---

# TASK-083: рассинхрон тегов образов — авто-деплой релиза падает на pull

## Проблема (блокирует релиз v0.1.0)

- `build-images.yml` тегает образы: `type=sha,prefix=` (КОРОТКИЙ sha) + `type=raw,value=latest`
  (на default-ветке). То есть в GHCR существуют `ghcr.io/nmetluk/bettgbot-{bot,web}:<short-sha>` и `:latest`.
- `deploy-prod.yml`, шаг `Set IMAGE_TAG`: при `release: published` (без `inputs.image_tag`) ставит
  `IMAGE_TAG = ${{ github.sha }}` — **полный 40-символьный SHA**.
- `docker-compose.prod.yml`: `image: ghcr.io/...:${IMAGE_TAG}`.
- Итог: `docker compose pull ...:<40-символьный sha>` → **тега нет** (образ под коротким sha) →
  `manifest unknown`, деплой падает. Авто-деплой по публикации Release нерабочий.

(Ручной `workflow_dispatch` с правильным коротким sha или `latest` работает — но цель: чтобы
публикация Release выкатывала без ручного подбора тега.)

## Цель

Согласовать тегирование так, чтобы `IMAGE_TAG`, который использует `deploy-prod` по умолчанию
(`github.sha`), **точно существовал** в GHCR.

## Definition of Done

> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-083-report.md`. Не закрыто, пока CI зелёный и PR смёржен.

Рекомендуемый путь (надёжный, immutable-pin) — добавить полный SHA-тег в сборку:

- [ ] В `build-images.yml` (оба job'а) добавить в `tags:` строку `type=sha,prefix=,format=long`
      (рядом с существующими). Тогда образы будут тегаться И коротким, И полным 40-символьным sha,
      и `deploy-prod`'s `github.sha` найдёт образ. `latest` оставить.
- [ ] Сверить непротиворечивость: `deploy-prod` `Set IMAGE_TAG` default (`github.sha`) теперь
      резолвится в существующий тег. Альтернативно/дополнительно можно научить deploy брать короткий sha,
      но достаточно полного тега в сборке — выбрать одно, не плодить расхождений.
- [ ] Убедиться, что `metadata-action` не споткнётся на двух `type=sha` (короткий + long) — оба
      валидны, дают два разных тега. Привести в отчёт фактический список тегов из лога сборки
      (`steps.meta.outputs.tags`).
- [ ] (sanity) Описать в отчёте, как проверено, что `IMAGE_TAG=<полный sha>` теперь pull'ится
      (лог build-images с полным sha-тегом, либо `docker manifest inspect`/`crane`/`gh` — что доступно).
- [ ] `ruff`/`mypy`/`pytest` зелёные (workflow-yaml тесты не трогают, но pipeline CI должен быть зелёным);
      PR `TASK-083: fix release deploy image tag mismatch (full-sha tag)`; auto-merge; `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Важно для релиза

После merge этой задачи `build-images.yml` пересоберёт образы на новом HEAD уже с полным sha-тегом.
**Релизный тег `v0.1.0` нужно ставить на коммит ПОСЛЕ merge TASK-083** (иначе у релизного коммита
не будет образа с полным sha). Тег/Release ставит архитектор/владелец — НЕ исполнитель.

## Вне скоупа

- Менять стратегию деплоя, окружение `production`/required reviewers (это намеренная защита прода).
- Версионирование (0.1.0 уже сделано в TASK-082).

## Артефакты

- `* .github/workflows/build-images.yml` — `type=sha,prefix=,format=long` в оба job'а
- `* (если выбран этот путь) .github/workflows/deploy-prod.yml` — согласование IMAGE_TAG
- `* handoff/outbox/TASK-083-report.md`

## Ссылки

- `build-images.yml` `tags:` (`type=sha,prefix=` + `latest`)
- `deploy-prod.yml` `Set IMAGE_TAG` (`github.sha` по умолчанию)
- `docker-compose.prod.yml` `image: ...:${IMAGE_TAG}`
