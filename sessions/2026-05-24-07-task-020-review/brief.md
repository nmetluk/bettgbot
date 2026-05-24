# Brief — task-020-review

**Дата:** 2026-05-24
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-020 и подготовить TASK-021 (CRUD категорий — первая бизнес-задача в админке).

## Контекст

Локальный CC закрыл TASK-020 за **7 коммитов** (squash `2f20573`), 75 минут. **Веб-админка теперь полностью защищена.** Самая большая инфраструктурная задача проекта после TASK-006 (migrations) и TASK-017 (scheduler).

Что сделано:

- **Step 0 cleanup pyproject:** `-passlib +bcrypt +fastapi-limiter +fastapi-csrf-protect +python-multipart` (multipart — для FastAPI form data, локальный CC заметил отсутствие). `uv.lock` пересобран. CI mypy включает `src/admin`.
- **Settings:** `AdminSettings.csrf_secret: SecretStr` (без default). `.env.example` + `tests/unit/conftest.py` stub + CI env обновлены.
- **`AdminAuthService.authenticate`** (`src/shared/services/admin_auth.py`) с **timing-attack mitigation**: при «admin не найден» делает dummy `bcrypt.checkpw` против заготовленного валидного hash. `last_login_at` обновляется при success. `AdminInvalidCredentialsError` (generic, anti-enumeration) + `AdminInactiveError`.
- **`src/admin/auth/security.py`**: `URLSafeTimedSerializer` с salt `bb-admin-session-v1`, helpers `create_session_token` / `verify_session_token`. Cookie `bb_admin_session`.
- **`RequireAdminMiddleware`** (`src/admin/auth/middleware.py`): ASGI-callable, whitelist `{/login, /logout, /healthz, /static/*}`, **sliding TTL через Set-Cookie wrap в send**. Stale-token (admin удалён/деактивирован) → redirect + clear_cookie. **Lazy `_get_session_maker()`** для тестируемости.
- **`current_admin`** dependency в `src/admin/deps.py`.
- **`lifespan` в `src/admin/app.py`**: `FastAPILimiter.init(redis_client)` + close. `CsrfProtect.load_config` через Settings. Middleware подключён.
- **POST `/login`**: rate-limit 5/min IP (через `fastapi-limiter` 0.1.6) + CSRF validate. Generic error на 401, отдельный текст для inactive 403. Сetting cookie с `Secure; HttpOnly; SameSite=Lax`.
- **POST `/logout`**: clear cookie, 302 на /login.
- **`login.html`**: hidden `<input name="csrf_token" value="{{ csrf_token }}">`.

**21 новый тест:** 7 unit security + 4 unit login handler + 6 unit middleware + 4 integration AdminAuthService. **Всего 177 unit + 95 integration = 272.** CI 4 зелёных job'а.

PR [#58](https://github.com/nmetluk/bettgbot/pull/58) → squash `2f20573`. Pre-task cleanup PR [#57](https://github.com/nmetluk/bettgbot/pull/57). Archive PR [#59](https://github.com/nmetluk/bettgbot/pull/59).

## Что сделано в этой сессии

6 open questions исполнителя — **5 keep + 1 change + 1 в тех-долг**:

- **(Q1) `fastapi-limiter` 0.1.6 vs 0.2.x API drift** — keep на 0.1.6 для MVP. В 0.2 cменили API на `pyrate-limiter` (`Limiter` вместо `FastAPILimiter`, новые `Depends`). Локальный CC правильно пиннул `<0.2`. **Тех-долг в BACKLOG**: «переход на fastapi-limiter 0.2+ когда понадобится» (триггер — security advisory против 0.1.6 или нужда в новых фичах).
- **(Q2 — change!) Secure cookie на dev** — браузер не отправит cookie с `Secure=True` через `http://localhost`, что даст **бесконечный редирект на /login при разработке**. Решение: добавить `Settings.environment: Literal["dev", "staging", "prod"] = "dev"` (или `Settings.admin.cookie_secure: bool = True`) с conditional `secure=` в `set_cookie` и `send`-wrapper. **Закрою в Step 0 TASK-021** (заодно с CRUD).
- **(Q3) `/logout` в public-paths** — keep. Logout = no-op без cookie, безопасно держать публичным. Альтернатива (logout под auth) даёт цикл при stale-token: пользователь не может ни войти, ни выйти.
- **(Q4) CSRF methods explicit `{POST, PUT, PATCH, DELETE}`** — keep. Защита для будущих TASK-021+ роутов без дополнительных правок.
- **(Q5) Lazy `_get_session_maker()` в middleware** — keep. Компромисс ради тестируемости (`patch.object` на module-level `SessionLocal`). Если найдём более элегантный способ через `app.state` — отдельная refactor-задача.
- **(Q6) Lifespan + import-time `app = create_app()`** — keep. Unit-тесты используют `dependency_overrides[RateLimiter] = noop`, чтобы обойти Redis в TestClient без lifespan. Для прода — `make admin` запускает uvicorn → lifespan startup → FastAPILimiter.init.

Обновлены:

- [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) — закрытие TASK-020, новый шаг TASK-021.
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — 4 строки: timing-attack mitigation паттерн; /logout в public; CSRF methods explicit; lazy session_maker как тестируемость-компромисс.
- [`state/BACKLOG.md`](../../state/BACKLOG.md) — 1 пункт тех-долга (`fastapi-limiter` 0.2 transition).
- Сформирована задача [`handoff/inbox/TASK-021-admin-categories.md`](../../handoff/inbox/TASK-021-admin-categories.md). Размер L. Step 0 — conditional Secure cookie через Settings.environment.

## Замечание о результате

Локальный CC отметил `python-multipart` — нужен для FastAPI Form() handling. Я в task-спеке его не упомянул — моя неточность. Хорошо, что он заметил и добавил.

**Прецеденты «исполнитель добавляет что-то полезное, не указанное в task»** уже регулярны:
- TASK-017: `User.is_blocked = FALSE` в find_candidates.
- TASK-019: VOLT_LICENSE.md отдельным файлом.
- TASK-020: `python-multipart` + ruff B008 exempt для Form() depends.

Это **здоровый признак** — исполнитель не догматичен, добавляет очевидно нужное, мне как cowork остаётся сверить и зафиксировать.

## Следующие шаги

1. Локальный CC берёт **TASK-021**: CRUD категорий. Step 0 — Settings.environment + conditional Secure cookie. Размер L.
2. **TASK-022** — CRUD событий с фильтрами + публикация.
3. **TASK-023** — CRUD исходов через HTMX inline-редактирование.
4. **TASK-024** — фиксация итога + автоматическая отметка прогнозов.
5. **TASK-025** — список пользователей + блок/разблок.
6. **TASK-026** — UI аудит-лога.
