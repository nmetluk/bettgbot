# Brief — task-019-review

**Дата:** 2026-05-24
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-019 и подготовить TASK-020 (аутентификация админки).

## Контекст

Локальный CC закрыл TASK-019 за 6 коммитов (squash `c0dbe96`), 45 минут. FastAPI-скелет работает, smoke-тесты зелёные, CI mypy расширен на `src/admin/`. PR [#55](https://github.com/nmetluk/bettgbot/pull/55).

**Compromises (важно для понимания текущего состояния):**

### Volt CSS = placeholder

Themesberg/volt-bootstrap-5-dashboard в master shipping **только SCSS-источники** (`src/scss/volt.scss`), скомпилированного `dist/assets/css/volt.css` в репо нет. Public CDN путей для Volt тоже нет. Локальный CC ship'нул placeholder CSS с HOWTO-комментарием + загрузил готовый `volt.js` (он не зависит от компиляции) + brand SVGs + MIT license. **Bootstrap 5 через CDN покрывает базовую вёрстку**, фирменный Volt-стайлинг (тёмные карты, специальные accent-цвета) — отсутствует.

Это **моя ошибка проектирования** (вторая после TASK-018): я выбрал Volt без проверки, доступен ли скомпилированный CSS. Должен был открыть https://github.com/themesberg/volt-bootstrap-5-dashboard/tree/master/dist перед публикацией задачи.

**Решение:** placeholder остаётся. Когда фирменный стиль станет реально важным (TASK-021+ когда появятся реальные таблицы CRUD с custom-styled элементами), сделаем отдельную мини-задачу `npm-build volt.css`. Записать в **тех-долг BACKLOG**: «скомпилировать `volt.css` из SCSS-источников Volt Free для фирменного стайлинга админки».

### passlib → bcrypt напрямую

`passlib 1.7.4` несовместим с `bcrypt 5.0` — внутри passlib падает `password cannot be longer than 72 bytes` даже на коротких паролях из-за изменения API в bcrypt 5.x. Локальный CC использовал `bcrypt` напрямую: `bcrypt.hashpw(secret, bcrypt.gensalt(rounds=12))`. Формат `$2b$…` остаётся; в TASK-020 verify через `bcrypt.checkpw(...)`.

**Решение:** keep, более того — **зафиксировать как архитектурное**: «hashing паролей через `bcrypt` напрямую, без passlib». Альтернативы (pin `bcrypt<4.1` или ждать релиз passlib с поддержкой bcrypt 5.x) — добавляют ограничения без выигрыша. `bcrypt` напрямую проще, меньше слоёв.

`pyproject.toml` пока остаётся с `passlib[bcrypt]>=1.7,<2` — bcrypt тянется как extras. Удалить `passlib` из зависимостей — отдельный мини-cleanup, могу включить в Step 0 TASK-020 (раз TASK-020 будет править pyproject под `fastapi-limiter`, заодно подчищу).

## Что сделано в этой сессии

Приняты решения по 5 open questions — **все «keep» + 1 в тех-долг (Volt CSS) + Step 0 в TASK-020 (cleanup passlib)**:

- **(Q1) Compiled `volt.css`** — placeholder остаётся, фирменный стиль — отдельной задачей по npm-build, когда реально нужно. В BACKLOG: «скомпилировать volt.css из Volt Free SCSS».
- **(Q2) passlib → bcrypt direct** — keep, фиксируем как принцип. Cleanup pyproject — в Step 0 TASK-020.
- **(Q3) `scripts/` запуск** — keep через Makefile-обёртку. `python -m scripts.create_admin` рефакторинг — если когда-нибудь будет 3+ скрипта.
- **(Q4) Bootstrap Icons CDN** — keep, будут полезны в TASK-021+ для `bi-*` иконок таблиц/форм.
- **(Q5) OpenAPI полностью off** (`openapi_url=None` тоже) — keep, безопасный default для internal admin (не утечёт схема).

Обновлены:

- [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) — закрытие TASK-019, новый шаг TASK-020.
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — 2 строки (Volt placeholder; bcrypt напрямую как архитектурный принцип).
- [`state/BACKLOG.md`](../../state/BACKLOG.md) — 1 новый пункт тех-долга (compiled volt.css).
- Сформирована задача [`handoff/inbox/TASK-020-admin-auth.md`](../../handoff/inbox/TASK-020-admin-auth.md). Размер L (~3-4h): POST /login + verify + signed cookie + middleware + rate-limit + CSRF + POST /logout + tests + Step 0 cleanup passlib.

## Уроки

**Урок для cowork (мой):** перед публикацией задачи с готовыми шаблонами/библиотеками **проверять, что они доступны в нужной форме** (скомпилированный CSS, готовый wheel, CDN URL). Volt Free — каноничный пример: репозиторий обещает «Bootstrap 5 admin dashboard», но в нём только SCSS. Должен был открыть `dist/` директорию в master перед TASK-019.

Уроки от Этапа 3 после двух compromise'ов в TASK-019:
- Если в task используется готовый шаблон/тема — добавлять в DoD проверку «assets доступны в готовом виде, не требуют сборки».
- Если в task используется библиотека/extras (passlib[bcrypt]) — упоминать конкретные версии в DoD, проверять compatibility matrix.

## Следующие шаги

1. Локальный CC берёт **TASK-020**: auth-flow админки (POST /login, signed cookie, middleware `require_admin`, rate-limit, CSRF, logout). Step 0 — cleanup pyproject (убрать passlib). Размер L.
2. После TASK-020 — TASK-021 (CRUD категорий). Размер M-L.
3. После TASK-021..026 — Этап 3 закрыт.
