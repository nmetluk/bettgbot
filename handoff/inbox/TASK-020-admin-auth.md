---
id: TASK-020
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/05-admin-spec.md
  - docs/08-conventions.md
  - src/shared/models/admin_user.py
  - src/admin/app.py
  - src/admin/routes/login.py
priority: high
estimate: L
---

# TASK-020: аутентификация админки (bcrypt + signed cookie + middleware + rate-limit + CSRF)

## Контекст

Авторизация для веб-админки. После TASK-019 у нас работает скелет (`/login` GET форма, `/` GET dashboard заглушка, `/healthz`), но **никакой защиты**: dashboard виден всем, `POST /login` отдаёт 405. Эта задача закрывает auth.

Спецификация — [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) разделы «Аутентификация» и «Безопасность». Ключевые требования:

- **Хеш паролей:** bcrypt cost ≥ 12 (TASK-019 уже использует bcrypt напрямую, см. [DECISIONS](../../state/DECISIONS.md)).
- **Сессия:** signed cookie через `itsdangerous`. TTL 8 часов, sliding (продление при активности).
- **Cookie-настройки:** `Secure, HttpOnly, SameSite=Lax`.
- **Rate-limit на `/login`:** 5 попыток/мин с IP, через `fastapi-limiter` поверх Redis.
- **CSRF:** через `fastapi-csrf-protect` или собственный middleware с signed token в форме.
- **Generic error** при неуспехе: «неверный логин или пароль» (не раскрывать, что именно).
- **Regистрация админов через UI отсутствует** — создаются скриптом `scripts/create_admin.py` (готов из TASK-019).
- Все формы — POST, никаких GET для изменений.

Источники:

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) — раздел «Аутентификация», «Безопасность», «Шаблон проекта» (структура `src/admin/auth/`).
- [`src/shared/models/admin_user.py`](../../src/shared/models/admin_user.py) — поля `login`, `password_hash`, `full_name`, `is_active`, `last_login_at`.
- [`src/shared/services/`](../../src/shared/services/) — образец `AuditService` (TASK-009) для последующего audit-логирования login-событий.
- [`scripts/create_admin.py`](../../scripts/create_admin.py) — bcrypt cost=12 готов.
- [`src/shared/config.py`](../../src/shared/config.py) — `AdminSettings` (TASK-004). Добавим поле `session_secret: SecretStr`.

## Перед стартом — pre-task cleanup PR

В origin/main `063441e` — последний коммит (archive TASK-019). **Working tree этой машины:**

- `state/PROJECT_STATUS.md` — закрытие TASK-019, новый шаг TASK-020.
- `state/DECISIONS.md` — 2 новых строки (bcrypt напрямую + Volt placeholder).
- `state/BACKLOG.md` — 1 новый пункт (compiled volt.css).
- Новая сессия `sessions/2026-05-24-06-task-019-review/`.
- `handoff/inbox/TASK-020-admin-auth.md` — эта задача.

Branch: `chore/post-TASK-019-cowork-cleanup`, PR, merge. После — `feature/TASK-020-admin-auth`.

## Цель

Веб-админка защищена: незалогиненный пользователь видит только `/login`/`/healthz`/`/static/*`, остальные пути — redirect на `/login`. Залогиненный — нормально работает. `POST /login` имеет rate-limit. `POST /logout` чистит сессию. CSRF на всех POST. Логин-события и неудачные попытки логируются. Покрыто unit-тестами через `TestClient` + integration-тестом на `AdminAuthService`.

## Definition of Done

### Step 0 — Cleanup pyproject и зависимостей

- [ ] **Убрать `passlib[bcrypt]` из `pyproject.toml`** (зафиксировано в [DECISIONS](../../state/DECISIONS.md) 2026-05-24: «bcrypt используется напрямую»).
- [ ] **Добавить в `pyproject.toml`:**
  - `bcrypt>=4.1,<6` — раньше тянулся как extras passlib, теперь явная зависимость. Pin по верху <6 потому что в bcrypt 6 могут быть breaking changes.
  - `fastapi-limiter>=0.1.6,<1` — async Redis-based rate-limit для FastAPI.
  - `fastapi-csrf-protect>=0.4,<1` — CSRF middleware. Активно поддерживаемая библиотека.
- [ ] `uv lock` → `uv.lock` обновляется. Проверь, что `uv sync --frozen` устанавливает новые зависимости.
- [ ] `mypy` всё ещё зелёный после обновления.

### Step 1 — Settings: `admin_session_secret`

- [ ] **В `src/shared/config.py`** добавить в `AdminSettings` (или в основной `Settings`, если `AdminSettings` уже вложенный):
  ```python
  session_secret: SecretStr  # ≥ 32 bytes random — для itsdangerous signing
  session_ttl_minutes: int = 480  # 8 часов
  csrf_secret: SecretStr  # отдельный для CSRF (best practice — отдельный ключ)
  ```
  - `SecretStr` для маскировки в logs.
  - **Никаких defaults** — оба secret'а обязательны в env. Это защита от запуска прода с дефолтным ключом.
- [ ] **В `infra/.env.example`** добавить:
  ```
  # Admin auth
  ADMIN__SESSION_SECRET=  # сгенерируй: python -c "import secrets; print(secrets.token_urlsafe(48))"
  ADMIN__SESSION_TTL_MINUTES=480
  ADMIN__CSRF_SECRET=  # сгенерируй так же
  ```
- [ ] **В `tests/unit/conftest.py`** (stub-env) — добавить тестовые значения для обоих secret'ов.

### Step 2 — `AdminAuthService` в `src/shared/services/admin_auth.py`

- [ ] **Новый сервис:**
  ```python
  """`AdminAuthService` — verify пароля, проверка is_active, обновление last_login_at."""

  from __future__ import annotations

  from datetime import UTC, datetime

  import bcrypt
  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession

  from ..exceptions import AdminInvalidCredentialsError, AdminInactiveError
  from ..models import AdminUser

  __all__ = ["AdminAuthService"]


  class AdminAuthService:
      def __init__(self, session: AsyncSession) -> None:
          self._session = session

      async def authenticate(self, *, login: str, password: str) -> AdminUser:
          """Verify login/password. Возвращает AdminUser или поднимает доменное исключение.

          - `AdminInvalidCredentialsError` — login не найден ИЛИ password не подходит
            (одинаково — чтобы не давать enumeration-вектор).
          - `AdminInactiveError` — admin найден, password верный, но `is_active=False`.
          """
          stmt = select(AdminUser).where(AdminUser.login == login)
          result = await self._session.execute(stmt)
          admin = result.scalar_one_or_none()
          if admin is None:
              # Делаем dummy bcrypt-verify, чтобы не было timing-leak (хэширование занимает время).
              bcrypt.checkpw(password.encode("utf-8"), b"$2b$12$" + b"x" * 53)
              raise AdminInvalidCredentialsError()

          if not bcrypt.checkpw(password.encode("utf-8"), admin.password_hash.encode("utf-8")):
              raise AdminInvalidCredentialsError()

          if not admin.is_active:
              raise AdminInactiveError(admin_id=admin.id)

          admin.last_login_at = datetime.now(tz=UTC)
          await self._session.commit()
          return admin
  ```
  - **Timing-attack mitigation**: при `admin is None` делаем фиктивный `bcrypt.checkpw` с любым dummy-hash, чтобы время отклика не давало enumeration-сигнал. Стандартный паттерн.
  - **Generic error**: `AdminInvalidCredentialsError` без причины. Handler рендерит «неверный логин или пароль».
  - `AdminInactiveError` — отдельный кейс: пароль был верный, но учётка деактивирована. Текст в handler'е «учётная запись отключена, обратитесь к администратору».
- [ ] **В `src/shared/exceptions.py`** добавить:
  ```python
  class AdminInvalidCredentialsError(DomainError):
      """Login не найден или password не подходит. Генерик, без enumeration."""


  class AdminInactiveError(DomainError):
      """Учётка админа существует, password верный, но is_active=False."""

      def __init__(self, *, admin_id: int) -> None:
          super().__init__(f"admin {admin_id} is inactive")
          self.admin_id = admin_id
  ```
- [ ] **В `src/shared/services/__init__.py`** добавить `AdminAuthService` в re-export и `__all__`.

### Step 3 — `src/admin/auth/security.py` — signed cookie helpers

- [ ] **Новый каталог `src/admin/auth/`** с `__init__.py`:
  ```python
  """Auth helpers и middleware админки (TASK-020)."""
  ```
- [ ] **`src/admin/auth/security.py`:**
  ```python
  """Signed cookie через itsdangerous + utilities."""

  from __future__ import annotations

  from datetime import UTC, datetime, timedelta

  from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

  from src.shared.config import get_settings

  __all__ = [
      "SESSION_COOKIE_NAME",
      "create_session_token",
      "verify_session_token",
  ]


  SESSION_COOKIE_NAME = "bb_admin_session"


  def _serializer() -> URLSafeTimedSerializer:
      """Фабрика. Не singleton — `get_settings()` в тестах может вернуть свежий конфиг."""
      s = get_settings()
      return URLSafeTimedSerializer(
          secret_key=s.admin.session_secret.get_secret_value(),
          salt="bb-admin-session-v1",
      )


  def create_session_token(*, admin_id: int) -> str:
      """Подписанный token с admin_id и timestamp (внутри itsdangerous).

      Срок жизни — `admin.session_ttl_minutes` — проверяется при verify.
      """
      return _serializer().dumps({"admin_id": admin_id})


  def verify_session_token(token: str) -> int | None:
      """Возвращает admin_id или None при просроченном/инвалидном/подменённом."""
      s = get_settings()
      max_age = s.admin.session_ttl_minutes * 60
      try:
          payload = _serializer().loads(token, max_age=max_age)
      except SignatureExpired:
          return None
      except BadSignature:
          return None
      admin_id = payload.get("admin_id") if isinstance(payload, dict) else None
      return int(admin_id) if isinstance(admin_id, int) else None
  ```
  - `salt="bb-admin-session-v1"` — version-namespace для будущей ротации secret'а.
  - Sliding TTL: каждый verify обновляет cookie на 8 часов от текущего момента (см. Step 5 — middleware re-issues cookie на каждом запросе).

### Step 4 — `src/admin/auth/middleware.py` — `RequireAdminMiddleware`

- [ ] **`src/admin/auth/middleware.py`:**
  ```python
  """RequireAdminMiddleware — защищает все пути, кроме whitelisted."""

  from __future__ import annotations

  from collections.abc import Awaitable, Callable
  from datetime import UTC, datetime, timedelta

  from fastapi import Request
  from fastapi.responses import RedirectResponse
  from sqlalchemy import select
  from starlette.responses import Response
  from starlette.types import ASGIApp

  from src.shared.config import get_settings
  from src.shared.db import SessionLocal
  from src.shared.logging import get_logger
  from src.shared.models import AdminUser

  from .security import (
      SESSION_COOKIE_NAME,
      create_session_token,
      verify_session_token,
  )

  __all__ = ["RequireAdminMiddleware"]

  logger = get_logger(__name__)

  # Пути, доступные без логина.
  _PUBLIC_PATHS = frozenset({"/login", "/healthz"})
  _PUBLIC_PREFIXES = ("/static/",)


  def _is_public(path: str) -> bool:
      if path in _PUBLIC_PATHS:
          return True
      return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


  class RequireAdminMiddleware:
      """ASGI-middleware. Если путь приватный — verify cookie, подгрузка AdminUser.

      Реализуем как ASGI-callable (не `BaseHTTPMiddleware`), чтобы избежать
      двойной буферизации тел запросов и поддержать streaming-ответы.
      """

      def __init__(self, app: ASGIApp) -> None:
          self.app = app

      async def __call__(self, scope, receive, send) -> None:
          if scope["type"] != "http":
              await self.app(scope, receive, send)
              return

          request = Request(scope, receive=receive)
          path = request.url.path

          if _is_public(path):
              await self.app(scope, receive, send)
              return

          token = request.cookies.get(SESSION_COOKIE_NAME)
          admin_id = verify_session_token(token) if token else None
          if admin_id is None:
              response = RedirectResponse(url="/login", status_code=302)
              await response(scope, receive, send)
              return

          # Подгружаем AdminUser. Это +1 SQL на каждый защищённый запрос —
          # приемлемо для админки (низкочастотный трафик). Если станет
          # горячо — кешировать в Redis по admin_id.
          async with SessionLocal() as session:
              admin = await session.get(AdminUser, admin_id)

          if admin is None or not admin.is_active:
              # Стейл-токен (admin был удалён или деактивирован после issue cookie)
              logger.warning("admin.auth.stale_session", admin_id=admin_id)
              response = RedirectResponse(url="/login", status_code=302)
              response.delete_cookie(SESSION_COOKIE_NAME)
              await response(scope, receive, send)
              return

          # Кладём admin в request.state для use в dependency `current_admin`.
          scope["state"] = scope.get("state") or {}
          scope["state"]["admin"] = admin

          # Sliding session: рефрешим cookie на каждом запросе.
          # Wrap send, чтобы вшить Set-Cookie в response.
          new_token = create_session_token(admin_id=admin.id)
          s = get_settings()
          expires = datetime.now(tz=UTC) + timedelta(minutes=s.admin.session_ttl_minutes)

          async def send_with_cookie(message):
              if message["type"] == "http.response.start":
                  cookie_header = (
                      f"{SESSION_COOKIE_NAME}={new_token}; "
                      f"HttpOnly; Secure; SameSite=Lax; "
                      f"Path=/; "
                      f"Expires={expires.strftime('%a, %d %b %Y %H:%M:%S GMT')}"
                  )
                  headers = list(message.get("headers", []))
                  headers.append((b"set-cookie", cookie_header.encode("latin-1")))
                  message = {**message, "headers": headers}
              await send(message)

          await self.app(scope, receive, send_with_cookie)
  ```
  - **Sliding TTL**: каждый успешный запрос рефрешит cookie. Если пользователь не активен 8 часов — cookie expired, redirect на /login.
  - **Стейл-токен**: если cookie валиден, но admin удалён/деактивирован — очищаем cookie + редирект.
  - **`Secure` cookie**: на dev (`http://localhost`) Secure-cookie не работает — браузер не отправит. Это **сознательный компромисс**: на dev открой через https (через nginx-proxy с self-signed) или временно `Secure=False`. В production только https. Опционально — `if s.environment == "dev": secure = False` через Settings, но это усложнение.

### Step 5 — `src/admin/deps.py` — `current_admin` dependency

- [ ] **Обновить `src/admin/deps.py`:**
  ```python
  """DI dependencies для админки (TASK-020+)."""

  from __future__ import annotations

  from fastapi import HTTPException, Request, status

  from src.shared.models import AdminUser

  __all__ = ["current_admin"]


  async def current_admin(request: Request) -> AdminUser:
      """Достаёт текущего админа из request.state (положен middleware'ом).

      Если middleware не отработал (вызывают вне middleware, баг конфигурации) —
      401. На практике все приватные роуты пройдут через `RequireAdminMiddleware`,
      и dependency просто типизирует возвращаемое значение для роута.
      """
      admin = getattr(request.state, "admin", None)
      if admin is None:
          raise HTTPException(
              status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
          )
      return admin
  ```

### Step 6 — Регистрация middleware и lifespan в `src/admin/app.py`

- [ ] **Обновить `create_app`:**
  ```python
  from contextlib import asynccontextmanager

  from fastapi import FastAPI
  from fastapi.staticfiles import StaticFiles
  from fastapi.templating import Jinja2Templates
  from fastapi_limiter import FastAPILimiter
  from redis.asyncio import Redis

  from src.shared.config import get_settings
  from src.shared.logging import configure_logging, get_logger

  from .auth.middleware import RequireAdminMiddleware


  @asynccontextmanager
  async def lifespan(app: FastAPI):
      s = get_settings()
      redis_client = Redis.from_url(str(s.redis_url), decode_responses=True)
      await FastAPILimiter.init(redis_client)
      logger.info("admin.startup", redis=str(s.redis_url))
      yield
      await FastAPILimiter.close()
      await redis_client.aclose()
      logger.info("admin.shutdown")


  def create_app() -> FastAPI:
      s = get_settings()
      configure_logging(s.log_level, s.log_format)

      app = FastAPI(
          title="Betting Bot Admin",
          version="0.0.0",
          docs_url=None,
          redoc_url=None,
          openapi_url=None,
          lifespan=lifespan,
      )

      # Order matters: static must be mounted before middleware,
      # чтобы /static/* не проходил через auth.
      app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")

      app.add_middleware(RequireAdminMiddleware)

      from .routes import dashboard as dashboard_routes
      from .routes import login as login_routes

      app.include_router(login_routes.router)
      app.include_router(dashboard_routes.router)

      @app.get("/healthz", tags=["meta"])
      async def healthz() -> dict[str, str]:
          return {"status": "ok"}

      return app
  ```
  - **`lifespan`**: инициализирует `FastAPILimiter` с Redis. Закрывает при shutdown.
  - **`StaticFiles` до `add_middleware`** — статика не должна проходить через auth (whitelist в `_is_public` тоже её включает, но это double-protection).

### Step 7 — POST `/login` handler

- [ ] **Обновить `src/admin/routes/login.py`:**
  ```python
  """Login routes — GET форма, POST verify, /logout."""

  from __future__ import annotations

  from datetime import UTC, datetime, timedelta

  from fastapi import APIRouter, Depends, Form, Request, status
  from fastapi.responses import HTMLResponse, RedirectResponse
  from fastapi_limiter.depends import RateLimiter
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.shared.config import get_settings
  from src.shared.db import SessionLocal
  from src.shared.exceptions import AdminInactiveError, AdminInvalidCredentialsError
  from src.shared.logging import get_logger
  from src.shared.services import AdminAuthService

  from ..app import templates
  from ..auth.security import SESSION_COOKIE_NAME, create_session_token

  __all__ = ["router"]

  logger = get_logger(__name__)

  router = APIRouter(tags=["auth"])


  async def _session_dep() -> AsyncSession:
      async with SessionLocal() as session:
          yield session


  @router.get("/login", response_class=HTMLResponse)
  async def login_form(request: Request) -> HTMLResponse:
      return templates.TemplateResponse(
          request=request, name="login.html", context={"error": None}
      )


  @router.post(
      "/login",
      dependencies=[Depends(RateLimiter(times=5, seconds=60))],
  )
  async def login_submit(
      request: Request,
      login: str = Form(...),
      password: str = Form(...),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse | RedirectResponse:
      service = AdminAuthService(session)
      try:
          admin = await service.authenticate(login=login, password=password)
      except AdminInvalidCredentialsError:
          logger.info("admin.auth.failed", login=login, ip=request.client.host if request.client else None)
          return templates.TemplateResponse(
              request=request,
              name="login.html",
              context={"error": "Неверный логин или пароль."},
              status_code=status.HTTP_401_UNAUTHORIZED,
          )
      except AdminInactiveError:
          logger.warning("admin.auth.inactive", login=login)
          return templates.TemplateResponse(
              request=request,
              name="login.html",
              context={"error": "Учётная запись отключена. Обратитесь к администратору."},
              status_code=status.HTTP_403_FORBIDDEN,
          )

      token = create_session_token(admin_id=admin.id)
      s = get_settings()
      expires = datetime.now(tz=UTC) + timedelta(minutes=s.admin.session_ttl_minutes)

      response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
      response.set_cookie(
          key=SESSION_COOKIE_NAME,
          value=token,
          httponly=True,
          secure=True,
          samesite="lax",
          expires=expires,
          path="/",
      )
      logger.info("admin.auth.success", admin_id=admin.id, login=admin.login)
      return response


  @router.post("/logout")
  async def logout(request: Request) -> RedirectResponse:
      response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
      response.delete_cookie(SESSION_COOKIE_NAME, path="/")
      logger.info("admin.auth.logout")
      return response
  ```

- [ ] **`src/admin/routes/dashboard.py`** — добавить защиту через dependency:
  ```python
  from ..deps import current_admin

  @router.get("/", response_class=HTMLResponse)
  async def dashboard(
      request: Request,
      admin: AdminUser = Depends(current_admin),
  ) -> HTMLResponse:
      return templates.TemplateResponse(
          request=request,
          name="dashboard.html",
          context={
              "counters": {"users": 0, "events": 0, "categories": 0, "predictions": 0},
              "admin": admin,
          },
      )
  ```
  - Middleware и так редиректит без сессии, dependency дублирует — но это даёт типизированный `admin` в роутах. Стандартный FastAPI-паттерн.

### Step 8 — CSRF middleware

- [ ] **Установить `fastapi-csrf-protect`** (через `pyproject.toml`).
- [ ] **В `src/admin/app.py`** настроить:
  ```python
  from fastapi_csrf_protect import CsrfProtect
  from fastapi_csrf_protect.exceptions import CsrfProtectError

  from pydantic import BaseModel as PydBase

  class _CsrfSettings(PydBase):
      secret_key: str
      cookie_secure: bool = True
      cookie_samesite: str = "lax"


  @CsrfProtect.load_config
  def _get_csrf_config():
      s = get_settings()
      return _CsrfSettings(secret_key=s.admin.csrf_secret.get_secret_value())


  @app.exception_handler(CsrfProtectError)
  async def _csrf_error_handler(request: Request, exc: CsrfProtectError):
      return templates.TemplateResponse(
          request=request,
          name="login.html",
          context={"error": "Сессия истекла, обновите страницу."},
          status_code=403,
      )
  ```
- [ ] **В `login.html`** добавить hidden CSRF-input:
  ```html
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
  ```
- [ ] **В `routes/login.py` GET /login** — генерировать token:
  ```python
  @router.get("/login", response_class=HTMLResponse)
  async def login_form(request: Request, csrf_protect: CsrfProtect = Depends()) -> HTMLResponse:
      csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
      response = templates.TemplateResponse(
          request=request,
          name="login.html",
          context={"error": None, "csrf_token": csrf_token},
      )
      csrf_protect.set_csrf_cookie(signed_token, response)
      return response
  ```
- [ ] **В `routes/login.py` POST /login** — verify CSRF:
  ```python
  await csrf_protect.validate_csrf(request)  # бросит CsrfProtectError, поймает global handler
  ```

### Step 9 — Тесты

#### `tests/unit/admin/test_security.py`

- [ ] `test_create_and_verify_session_token_roundtrip` — `verify_session_token(create_session_token(admin_id=42))` → 42.
- [ ] `test_verify_returns_none_for_expired_token` — manually-issued token с истёкшим max_age → None. Используй `freezegun` или подмену `_serializer()`.
- [ ] `test_verify_returns_none_for_bad_signature` — token с подменённой буквой → None.
- [ ] `test_verify_returns_none_for_garbage` — `verify_session_token("nothing")` → None.

#### `tests/integration/services/test_admin_auth_service.py`

Использовать nested_session-фикстуру:

- [ ] `test_authenticate_success_updates_last_login_at` — создан AdminUser с bcrypt-hash пароля, authenticate → возвращает admin, `last_login_at` обновлён.
- [ ] `test_authenticate_wrong_password_raises_invalid_credentials`.
- [ ] `test_authenticate_unknown_login_raises_invalid_credentials` — для несуществующего login тот же exception (anti-enumeration).
- [ ] `test_authenticate_inactive_admin_raises_inactive` — `is_active=False`, password верный → `AdminInactiveError`.

#### `tests/unit/admin/test_login_handler.py`

Через `TestClient`:

- [ ] `test_login_form_renders_with_csrf_input` — GET /login → 200, в HTML есть `name="csrf_token"`.
- [ ] `test_login_post_invalid_credentials_returns_401_with_generic_error` — mock `AdminAuthService.authenticate` бросает `AdminInvalidCredentialsError`. Проверить, что в response есть «Неверный логин или пароль».
- [ ] `test_login_post_success_sets_cookie_and_redirects` — mock authenticate → AdminUser, response 302 на /, cookie `bb_admin_session` присутствует.
- [ ] `test_logout_clears_cookie_and_redirects_to_login`.

**Важно для тестов:**
- `RateLimiter` требует Redis — в unit-тестах нужно либо мокать (`monkeypatch.setattr("src.admin.routes.login.RateLimiter", lambda **kw: lambda: None)`), либо использовать testcontainers-redis. На MVP — mock.
- `CsrfProtect` тоже требует валидный config — настроить через `Settings()` stub в conftest.

#### `tests/unit/admin/test_middleware.py`

Через `TestClient` с `src.admin.app:app`:

- [ ] `test_unauthenticated_redirects_to_login` — GET / без cookie → 302, Location `/login`.
- [ ] `test_public_paths_pass_through_without_cookie` — GET /healthz, /login, /static/css/volt.css — все 200 без cookie.
- [ ] `test_valid_cookie_passes_through` — TestClient.cookies.set('bb_admin_session', create_session_token(admin_id=<seed-admin-id>)), GET / → 200. Но это требует AdminUser в БД — лучше unit с моком `SessionLocal`.
- [ ] `test_stale_cookie_admin_deleted_returns_redirect_and_clears_cookie` — mock SessionLocal возвращает None → redirect + Set-Cookie deletion.

### Step 10 — Settings & .env update

- [ ] **`src/shared/config.py`** — добавить поля в `AdminSettings`.
- [ ] **`infra/.env.example`** — пример секретов.
- [ ] **`tests/unit/conftest.py`** — stub-values для admin secrets (без них тесты упадут на `Settings()`).

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая ~15 новых.
- [ ] `uv run pytest tests/integration -m integration` — все integration, включая 4 новых на AdminAuthService.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):**
  - `make admin.create LOGIN=admin PASSWORD="strong-secret!"` — создать админа.
  - `make admin` → uvicorn 127.0.0.1:8000.
  - GET / → redirect на /login.
  - GET /login → форма с csrf_token.
  - POST /login с неверным паролем → 401 + текст «Неверный логин или пароль».
  - 5 неверных попыток за минуту → 6-я возвращает 429 (rate-limit).
  - POST /login с правильным паролем → 302 на /, cookie выставлен.
  - GET / с cookie → 200 dashboard.
  - POST /logout → 302 на /login, cookie очищен.
- [ ] Ветка `feature/TASK-020-admin-auth`, Conventional Commits:
  - `chore(deps): remove passlib, add bcrypt + fastapi-limiter + fastapi-csrf-protect`
  - `feat(config): admin session_secret + csrf_secret + ttl`
  - `feat(services): AdminAuthService + AdminInvalidCredentialsError + AdminInactiveError`
  - `feat(admin): signed-cookie security helpers (itsdangerous)`
  - `feat(admin): RequireAdminMiddleware + current_admin dependency`
  - `feat(admin): POST /login + /logout + rate-limit + CSRF`
  - `feat(admin): lifespan FastAPILimiter + Redis + CsrfProtect config`
  - `feat(admin): login.html форма с CSRF token`
  - `test(admin): security, login handler, middleware (~15 unit)`
  - `test(integration): AdminAuthService (4 сценария)`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-020-report.md`, задача → `handoff/archive/TASK-020-admin-auth/task.md`.

## Артефакты

```
* pyproject.toml                                       # -passlib +bcrypt +fastapi-limiter +fastapi-csrf-protect
* uv.lock                                              # обновлено
* infra/.env.example                                   # +ADMIN__SESSION_SECRET / CSRF_SECRET / TTL_MINUTES
* src/shared/config.py                                 # +session_secret, csrf_secret, session_ttl_minutes в AdminSettings
* src/shared/exceptions.py                             # +AdminInvalidCredentialsError, +AdminInactiveError
+ src/shared/services/admin_auth.py                    # AdminAuthService
* src/shared/services/__init__.py                      # +AdminAuthService
+ src/admin/auth/__init__.py
+ src/admin/auth/security.py                           # signed-cookie helpers
+ src/admin/auth/middleware.py                         # RequireAdminMiddleware
* src/admin/deps.py                                    # +current_admin dependency
* src/admin/app.py                                     # lifespan + RequireAdminMiddleware + CsrfProtect config
* src/admin/routes/login.py                            # POST /login (rate-limit + CSRF) + /logout
* src/admin/routes/dashboard.py                        # +Depends(current_admin)
* src/admin/templates/login.html                       # +CSRF hidden input
* tests/unit/conftest.py                               # +stub admin secrets
+ tests/unit/admin/test_security.py                    # 4 теста
+ tests/unit/admin/test_login_handler.py               # 4 теста
+ tests/unit/admin/test_middleware.py                  # 4 теста
+ tests/integration/services/test_admin_auth_service.py # 4 теста
```

## Ссылки

- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — разделы «Аутентификация», «Безопасность»
- [src/shared/models/admin_user.py](../../src/shared/models/admin_user.py)
- [src/admin/app.py](../../src/admin/app.py) — текущий скелет (после TASK-019)
- [scripts/create_admin.py](../../scripts/create_admin.py) — образец bcrypt usage
- [state/DECISIONS.md](../../state/DECISIONS.md) — строка 2026-05-24 про bcrypt напрямую

## Подсказки исполнителю

- **`fastapi-limiter` lifespan**: `init` в startup, `close` в shutdown. Стандартный паттерн. См. документацию `https://github.com/long2ice/fastapi-limiter`.
- **`fastapi-csrf-protect`**: использует двойную submitted cookie. На GET /login генерируем (token, signed_token) пара. В шаблон передаём `csrf_token`, в response — set_csrf_cookie(`signed_token`). На POST verify через `validate_csrf(request)`. См. `https://github.com/aekasitt/fastapi-csrf-protect`.
- **Timing-attack mitigation в `authenticate`**: при `admin is None` делаем dummy `bcrypt.checkpw(password.encode(), b"$2b$12$" + b"x"*53)` чтобы время отклика не отличалось от случая «admin найден, password не подходит». Игнорируем результат.
- **`Set-Cookie` в middleware**: вшиваем через `send`-wrapper в ASGI scope, не через `response.set_cookie` (его в чистом ASGI middleware нет). См. пример выше.
- **`Secure cookie` на dev (`http://localhost`)**: браузер не отправит cookie с `Secure=True` через http. Если хочется тестировать локально через http — `Settings.environment = "dev"` + condition. На MVP не делаем — пользователь использует https через nginx-proxy или ставит `Secure=False` руками только в dev `.env`.
- **`RateLimiter(times=5, seconds=60)`** считается per-IP-address по умолчанию через `Identifier`-функцию. Если хочешь per-login (что более логично для прода — атакующий с одним IP не должен лочить всех users) — `Identifier` через login из form. На MVP per-IP достаточно.
- **`SessionLocal`** в middleware — каждый запрос создаёт свою сессию. Это +1 SQL на запрос (`session.get(AdminUser, admin_id)`). Для админки (низкочастотный трафик) приемлемо; если станет горячо — кешировать AdminUser в Redis по admin_id, инвалидация при logout/update.
- **Тесты с TestClient + middleware**: `RateLimiter` требует Redis. В unit-тестах мокать `RateLimiter` через `monkeypatch.setattr` ИЛИ использовать `dependency_overrides`. Образец:
  ```python
  from src.admin.routes.login import router
  router.dependency_overrides[RateLimiter] = lambda: None
  ```
- **`AdminInvalidCredentialsError` логируется как `info`**, не `warning` — для legit-пользователя неудача — нормальный кейс (опечатка). `warning` зарезервирован для `AdminInactiveError` (что-то пошло не так на стороне организации).

## Что НЕ делать

- Не добавлять «забыли пароль» — это процесс на стороне организации (через сменого пароля скриптом).
- Не делать UI добавления админов — на MVP только через `scripts/create_admin.py`.
- Не делать SSO / OAuth — outside scope.
- Не делать audit-логирование login-событий с `AuditService` — TASK-026 (UI audit-лога) добавит, если потребуется.
- Не выносить `RequireAdminMiddleware` в `src/shared/` — это специфично админке (whitelist путей).
- Не делать sliding TTL через background-job — middleware re-issue cookie на каждом запросе достаточен.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не зеркалить в Drive вручную.
