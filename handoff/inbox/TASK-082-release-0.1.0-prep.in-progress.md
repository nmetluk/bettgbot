---
id: TASK-082
created: 2026-05-31
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - pyproject.toml
  - CHANGELOG.md
  - state/PROJECT_STATUS.md
  - src/shared/build_info.py
priority: high
estimate: S
---

# TASK-082: подготовка релиза v0.1.0 (bump версии + CHANGELOG + PROJECT_STATUS)

## Контекст

Владелец закрывает этап и готовит первый реальный релиз **v0.1.0** (сейчас `pyproject.toml` version
`0.0.0`, тегов нет). Это **подготовка**: бамп версии и release-notes. Сам тег/GitHub Release и деплой
делает владелец вручную (см. «После merge»). Деплой НЕ триггерить из этой задачи.

Важно: после merge этой задачи `build-images.yml` пересоберёт GHCR-образы с `APP_VERSION=0.1.0`
(через build-args, TASK-081), и build-info в проде покажет правильную версию.

## Definition of Done

> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-082-report.md`. Не закрыто, пока CI зелёный и PR смёржен.

- [ ] **Bump версии:** `pyproject.toml` `version = "0.0.0"` → `"0.1.0"`. Проверить, что больше нигде
      версия не захардкожена (grep `0.0.0` по репо; build-info берёт из pyproject — ок).
- [ ] **CHANGELOG.md:** создать (если нет) в формате Keep a Changelog / SemVer, добавить секцию
      `## [0.1.0] - 2026-05-31`. Содержимое — **сгенерировать из фактической истории**
      (`git log`, `handoff/archive/`), сгруппировать по Added / Changed / Fixed / Security. Не выдумывать —
      опираться на реально влитые TASK'и. Ориентир (проверить по истории, не копировать вслепую):
      - Added: админка v2 (события/категории/исходы/результаты, рассылки, аналитика, лидерборд,
        audit-log), build-info (версия/коммит на дашборде и в `/healthz`), hands-free CI merge-гейт.
      - Fixed: 500 на странице события (eager-load relationships) + регрессия; a11y (контраст
        primary/border, aria-hidden иконок, autocomplete); отступы формы события.
      - Changed: единая aware-UTC стратегия времени; CSP — self-host вместо CDN.
      - Security: CSRF/session/proxy-фиксы входа; CSP self-host (убран jsdelivr).
- [ ] **state/PROJECT_STATUS.md:** обновить — отметить готовность v0.1.0 и зафиксировать срез.
      (Обычно `state/` — зона проектировщика; для этой задачи правка **явно разрешена** здесь.)
- [ ] **НЕ** создавать git-тег и НЕ публиковать GitHub Release — это ручной шаг владельца (гейтит деплой).
- [ ] `ruff`/`mypy`/`pytest` зелёные; build-info тест по-прежнему ок (версия из env/pyproject).
- [ ] PR `TASK-082: release v0.1.0 prep (version bump + CHANGELOG)`; auto-merge по зелёному CI; `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## После merge (шаги владельца — НЕ исполнителя)

1. Дождаться, что `build-images.yml` собрал GHCR-образы на новом SHA (APP_VERSION=0.1.0).
2. Релиз/деплой — по решению владельца:
   - **Подготовить без деплоя:** создать git-тег `v0.1.0` на merge-коммите (или Draft Release).
     ⚠️ Публикация GitHub Release (не draft) триггерит `deploy-prod.yml` (`release: published`) →
     автодеплой. Хочешь без деплоя — НЕ публикуй release, только тег/draft.
   - **Деплой, когда готов:** опубликовать Release `v0.1.0` (автодеплой) ИЛИ вручную
     `deploy-prod.yml` → workflow_dispatch с нужным IMAGE_TAG.

## Вне скоупа

- Сам деплой, тег, Release — ручные шаги владельца.
- Менять deploy/build workflow — не требуется (TASK-081 уже прокинул APP_VERSION).

## Артефакты

- `* pyproject.toml` — version 0.1.0
- `* CHANGELOG.md` — секция 0.1.0
- `* state/PROJECT_STATUS.md` — срез готовности (правка разрешена этой задачей)
- `* handoff/outbox/TASK-082-report.md`
