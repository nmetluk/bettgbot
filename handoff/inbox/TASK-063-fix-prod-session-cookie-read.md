---
id: TASK-063
created: 2026-05-30
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/admin/auth/middleware.py
  - src/admin/auth/security.py
  - src/admin/routes/login.py
  - tests/unit/admin/test_middleware.py
  - docs/audit/2026-05-30-full-audit.md
priority: high
estimate: S
---

# TASK-063: Hotfix — прод-логин всё ещё зациклен: session-кука читается под dev-именем

## Контекст

TASK-062 чинил «на проде не залогиниться» и закрыл CSRF-403 + 4 сопутствующих дефекта. **Но цель не
достигнута:** аудит `docs/audit/2026-05-30-full-audit.md` (находка **B1, Blocker**) показал, что прод-логин
по-прежнему зациклен по той же первопричине, что и исходный баг — env-зависимое имя cookie рассинхронено
между записью и чтением, но в проглядённом **READ-пути** session-куки.

Факт по коду (`origin/main` @ `97e7c88`):

- `src/admin/routes/login.py:144` и `src/admin/auth/middleware.py:113` **пишут** session-куку под
  prod-именем `SESSION_COOKIE_NAME_PROD = "__Host-bb_admin_session"` при `environment != "dev"`.
- `src/admin/auth/middleware.py:82` её **читает** безусловно под dev-именем:
  `token = request.cookies.get(SESSION_COOKIE_NAME)` (`"bb_admin_session"`).

На проде браузер шлёт `__Host-bb_admin_session`, middleware ищет `bb_admin_session` → `None` →
`admin_id = None` → редирект на `/login`. **Итог: после успешного входа каждый authed-GET кидает обратно
на `/login`. Попасть в админку на проде нельзя — деплой TASK-062 логин НЕ чинит.**

Почему проскочило мимо CI (находка **H1, High**): весь admin-auth набор тестов гоняется только под
dev-именами кук (`tests/unit/admin/test_middleware.py` ставит/проверяет лишь `SESSION_COOKIE_NAME`),
поэтому целый класс prod-cookie дефектов структурно невидим. Без prod-env теста этот баг (и будущие
такого же рода) не ловится.

## Цель

На проде (`ENVIRONMENT=prod`, HTTPS за nginx) администратор после `POST /login` реально попадает на `/` и
остаётся залогинен на последующих authed-GET. Регресс закрыт тестом, который **падал бы** на текущем коде.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать `handoff/outbox/TASK-063-report.md`.**
> Без отчёта CI handoff-consistency красный, PR не мёрджится. Шаблон — `handoff/templates/report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен.

**B1 — фикс чтения (блокер):**

- [ ] `src/admin/auth/middleware.py:82` выбирает имя session-куки по окружению, как уже делается в
      строках 95-99/113 и в `login.py`/`logout`:
      `s = get_settings(); session_name = SESSION_COOKIE_NAME_PROD if s.environment != "dev" else SESSION_COOKIE_NAME; token = request.cookies.get(session_name)`.
      (Импорт `SESSION_COOKIE_NAME_PROD` в `middleware.py` уже есть.)
- [ ] `git grep -n "cookies.get(SESSION_COOKIE_NAME)" src/admin/` → пусто (нет других мест, читающих
      session-куку под захардкоженным dev-именем). Если найдутся — поправить тем же способом.
- [ ] Никаких ослаблений: имена/атрибуты `__Host-` (Secure, Path=/, без Domain) не меняются, CSP не трогается.

**H1 — prod-env round-trip тест (обязателен, иначе баг не зафиксирован):**

- [ ] Тест под `monkeypatch.setenv("ENVIRONMENT", "prod")` + `get_settings.cache_clear()` (как в существующих
      prod-режимных тестах конфига): полный цикл — GET `/login` выставляет `__Host-`-CSRF-куку →
      `POST /login` валидными кредами выставляет `__Host-bb_admin_session` и редиректит на `/` →
      **следующий authed-GET (например `/`) с этой кукой возвращает 200, а не редирект на `/login`**.
      Тест **должен падать** на текущем коде (из-за B1) и проходить после фикса — явно отметить это в отчёте.
- [ ] Параметризовать (или продублировать) ключевой auth-тест и для dev, и для prod, чтобы оба имени кук
      покрывались. Имена кук в ассертах брать из `security.py` (`SESSION_COOKIE_NAME[_PROD]`), не хардкодить.

**Общее:**

- [ ] `ruff check` чист, `mypy src/admin src/shared` зелёный, `pytest` зелёный с новым тестом.
- [ ] PR `TASK-063: fix prod session cookie read mismatch (hotfix)`, CI зелёный, PR смёржен в `main`.
- [ ] **🚨 Move-семантика inbox→archive:** перед `chore(handoff): archive TASK-063 ...` —
      `ls handoff/inbox/ | grep TASK-063`; найденное `git rm` (и `TASK-063-<slug>.md`, и
      `TASK-063.in-progress.md`). В `handoff/archive/TASK-063-fix-prod-session-cookie-read/` — одна копия (директорией).

## Артефакты

- `* src/admin/auth/middleware.py` — выбор имени session-куки по env в READ-пути (строка ~82)
- `* tests/unit/admin/test_middleware.py` (+ при необходимости `tests/unit/admin/test_login_handler.py`) —
  prod-env round-trip; параметризация dev/prod
- `* handoff/outbox/TASK-063-report.md` — отчёт

## Ссылки

- Аудит-первоисточник: [`docs/audit/2026-05-30-full-audit.md`](../../docs/audit/2026-05-30-full-audit.md) (B1, H1)
- Предыдущая правка той же области: TASK-062 (`handoff/archive/TASK-062-fix-prod-admin-login/`)
- Имена/атрибуты кук: [`src/admin/auth/security.py`](../../src/admin/auth/security.py)

## Подсказки исполнителю

- Это та же первопричина, что у TASK-062, но в чтении сессии. Фикс — буквально 1-2 строки; **главная
  ценность задачи в тесте H1**, без него регресс вернётся. Не закрывай задачу, пока новый тест реально
  падает на коде до фикса (проверь, временно откатив правку, или убедись логикой).
- После мёржа владелец передеплоит web-образ и проверит на `a.pinbetting.ru`: вход боевыми кредами →
  остаёшься на `/` (не выкидывает на `/login`); в DevTools `__Host-bb_admin_session` присутствует и шлётся.
  Отметь это в отчёте как остаточную проверку.
- Узкий скоуп: только выравнивание имени куки в чтении + тест. Доменную/сервисную логику не трогать.
