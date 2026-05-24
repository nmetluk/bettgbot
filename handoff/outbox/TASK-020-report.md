---
task: TASK-020
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/58
branch: feature/TASK-020-admin-auth
related-prs:
  - https://github.com/nmetluk/bettgbot/pull/57 (pre-task cleanup)
commits:
  - 9a30389 chore(handoff): take TASK-020 in progress
  - 656edec chore(deps): remove passlib, add bcrypt + fastapi-limiter + fastapi-csrf-protect
  - 380dd61 feat(config): admin csrf_secret в AdminSettings + .env.example + CI env + test stubs
  - 79fc818 feat(services): AdminAuthService + AdminInvalidCredentialsError + AdminInactiveError
  - 3710966 feat(admin): signed-cookie security + RequireAdminMiddleware + current_admin dep
  - d591766 feat(admin): lifespan FastAPILimiter+Redis + CsrfProtect + POST /login + /logout + protected dashboard
  - 57035d9 test: admin auth — security (7) + login handler (4) + middleware (6) + integration (4); fix dummy_hash + /logout public path + lazy session_maker
---

# Отчёт по TASK-020: аутентификация админки

## Сводка

Веб-админка теперь защищена. Неавторизованный → 302 на /login (кроме whitelist `{"/login", "/logout", "/healthz"}` + `/static/*`). POST /login с rate-limit 5/min (через `fastapi-limiter` 0.1.6 поверх Redis) + CSRF (через `fastapi-csrf-protect` 1.0.7, токен в форме под именем `csrf_token`). Generic-error при неудаче, отдельный текст для inactive. /logout чистит cookie и редиректит на /login. Sliding TTL: cookie переоформляется на каждом успешном запросе через ASGI-middleware (Set-Cookie wrap в send).

`AdminAuthService.authenticate` — timing-attack mitigation: при «admin не найден» делаем dummy `bcrypt.checkpw` против заготовленного валидного hash, чтобы атакующий не различал «logo не найден» vs «password не подходит». Anti-enumeration.

itsdangerous `URLSafeTimedSerializer` с salt `bb-admin-session-v1` (version namespace для будущей ротации). Cookie `bb_admin_session`. `Secure; HttpOnly; SameSite=Lax`.

## Изменённые файлы

```
* pyproject.toml                                  # -passlib +bcrypt +fastapi-limiter (0.1.x) +fastapi-csrf-protect +python-multipart; ruff B008 exempt для src/admin/routes
* uv.lock                                         # пересобран
* infra/.env.example                              # +ADMIN_CSRF_SECRET
* .github/workflows/ci.yml                        # +ADMIN_CSRF_SECRET в integration env
* tests/unit/conftest.py                          # +stub ADMIN_CSRF_SECRET
* src/shared/config.py                            # +AdminSettings.csrf_secret
* src/shared/exceptions.py                        # +AdminInvalidCredentialsError +AdminInactiveError
+ src/shared/services/admin_auth.py               # AdminAuthService
* src/shared/services/__init__.py                 # +AdminAuthService
+ src/admin/auth/__init__.py
+ src/admin/auth/security.py                      # signed-cookie helpers (itsdangerous)
+ src/admin/auth/middleware.py                    # RequireAdminMiddleware (ASGI, lazy session_maker)
* src/admin/deps.py                               # current_admin dependency
* src/admin/app.py                                # lifespan + CsrfProtect + middleware
* src/admin/routes/login.py                       # POST /login (rate-limit + CSRF), /logout
* src/admin/routes/dashboard.py                   # Depends(current_admin)
* src/admin/templates/login.html                  # +csrf_token hidden input
* tests/unit/admin/test_app_smoke.py              # dashboard теперь redirect-test
+ tests/unit/admin/test_security.py               # 7 тестов (с parametrize)
+ tests/unit/admin/test_login_handler.py          # 4 теста
+ tests/unit/admin/test_middleware.py             # 6 тестов
+ tests/integration/services/test_admin_auth_service.py  # 4 теста
* handoff/inbox/TASK-020-...md → archive/TASK-020-admin-auth/task.md
+ handoff/outbox/TASK-020-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    135 files already formatted
mypy src/shared src/bot src/admin   Success: no issues found in 70 source files
pytest -m "not integration"      177 passed in 2.87s
pytest tests/integration         95 passed in 11.05s

CI PR #58 — все четыре job'а зелёные:
  Lint (ruff)                              10s
  Typecheck (mypy)                         22s
  Tests (pytest, unit)                     21s
  Integration (alembic on real postgres)   48s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env
# Заполни ADMIN_SECRET_KEY и ADMIN_CSRF_SECRET:
#   python -c "import secrets;print(secrets.token_urlsafe(48))"
make up && make migrate

make admin.create LOGIN=admin PASSWORD="strong-pwd!" FULL_NAME="Главный"
make admin   # uvicorn 127.0.0.1:8000

# Browser flow:
# GET / → 302 на /login (нет cookie)
# GET /login → форма с скрытым csrf_token + fastapi-csrf-token cookie
# POST /login с правильным паролем → 302 на /, bb_admin_session выставлен
# GET / с cookie → 200 dashboard
# POST /logout (с csrf_token) → 302 на /login, cookie очищен
# 6+ неудачных POST /login за минуту → 429 Too Many Requests
```

## Что не сделано / вынесено

1. **Аdmin-side audit-лог login-событий** — `logger.info(...)` в JSON-stdout. Привязка к `AuditService` (с `admin_id`) — в TASK-026 (UI просмотра audit-лога), как и было запланировано.
2. **Secure-cookie на dev** — Cookie с `Secure=True` не отправляется браузером через `http://localhost`. На dev нужен https-прокси (nginx self-signed) или временно переключать `Secure=False` в коде (через `Settings.environment`). Не сделал — преждевременно.
3. **SSO/OAuth, «забыли пароль», UI создания админов** — outside scope (явно в task.md).
4. **`fastapi-limiter` v0.1.6 vs v0.2.0** — пинил `<0.2`, потому что 0.2 cменил API на `pyrate_limiter.Limiter` (нет `FastAPILimiter.init`/`close`, `RateLimiter(times=, seconds=)`). Если когда-то перейдём — потребуется переписать lifespan и Depends. Записать в `BACKLOG`?
5. **passlib окончательно удалён.** В `pyproject.toml` зависимости больше нет; bcrypt — прямой dep.

## Открытые вопросы для проектировщика

1. **`fastapi-limiter 0.1.6` versus 0.2.x.** Я пиннул `<0.2` — task spec предполагал 0.1.x API. 0.2 это переписанный API через `pyrate-limiter`. Если хочется идти на 0.2 — нужна отдельная задача (lifespan + Depends по-другому). На MVP 0.1.6 работает.
2. **`Secure=True` cookie на dev.** Если разработчики ходят через `http://localhost:8000`, cookie не отправится → бесконечный redirect на /login. Хотим conditional `Secure` через `Settings.environment` (dev/staging/prod)? Сейчас всегда True, для dev — поднимать https-прокси.
3. **`/logout` в public-paths.** Иначе middleware блокировал бы logout до проверки cookie. Это допустимо (logout всегда no-op без cookie). Окей?
4. **CSRF `methods={"POST","PUT","PATCH","DELETE"}`** — GET excluded. Default в библиотеке — `None` (только POST по сути). Явно указал, чтобы будущие PUT/PATCH/DELETE-роуты тоже CSRF-защищены без правок.
5. **Lazy `_get_session_maker()` в middleware** — для тестируемости (patch.object на module-level `SessionLocal`). Если есть более элегантный способ через `app.state` / `lifespan` — переделаем в TASK-021+.
6. **Lifespan + lazy `app = create_app()` на import-time** — `Redis.from_url(...)` создаётся в lifespan, не в import-time. CI tests/unit/admin импортируют `app`, но lifespan не запускается с `TestClient` без `with TestClient(app):`. Это означает, что unit-тесты для /login не могут verify rate-limit (Redis не инициализирован). Обхожу через `dependency_overrides[RateLimiter] = noop`. Для прода — `make admin` запускает uvicorn → lifespan startup → FastAPILimiter.init.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-020: аутентификация админки. `AdminAuthService` (bcrypt + anti-enumeration timing-attack), itsdangerous `bb_admin_session` cookie с sliding TTL, ASGI `RequireAdminMiddleware` (whitelist `/login`,`/logout`,`/healthz`,`/static/*`), `current_admin` dependency. POST /login: rate-limit 5/min (fastapi-limiter 0.1.6 + Redis), CSRF (fastapi-csrf-protect 1.0.7 hidden form input), generic-error, отдельный текст для inactive. /logout чистит cookie. CI mypy включает src/admin. 18 новых тестов (177 unit + 95 integration). Зависимости: `-passlib +bcrypt +fastapi-limiter +fastapi-csrf-protect +python-multipart`. `AdminSettings.csrf_secret: SecretStr`. PR [#58](https://github.com/nmetluk/bettgbot/pull/58) → squash `2f20573`. Pre-task cleanup [#57](https://github.com/nmetluk/bettgbot/pull/57).
```

## Метрики

- Файлов добавлено: 9 (auth/__init__/security/middleware + admin_auth service + 4 теста + report)
- Файлов изменено: 13 (pyproject, lock, config, exceptions, services/__init__, app, deps, dashboard, login.py, login.html, conftest, ci.yml, test_app_smoke)
- Тестов добавлено: 21 (177 unit total, было 160; +95 integration было 91)
- Время на выполнение: ~75 мин (включая cleanup PR, разбор fastapi-limiter 0.1↔0.2 API drift, добавление python-multipart, исправление /logout middleware bug)
