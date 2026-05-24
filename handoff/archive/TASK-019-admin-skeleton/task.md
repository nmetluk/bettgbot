---
id: TASK-019
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/05-admin-spec.md
  - docs/02-tech-stack.md
  - docs/07-deployment.md
  - src/admin/
priority: high
estimate: M
---

# TASK-019: FastAPI скелет веб-админки + Volt Free шаблон + create_admin script

## Контекст

**Старт Этапа 3 (веб-админка).** До сих пор `src/admin/` был пустой каталог с одним `__init__.py`. Спецификация админки — [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md). Стек уже подготовлен ([`docs/02-tech-stack.md`](../../docs/02-tech-stack.md)): FastAPI + Jinja2 + HTMX + Bootstrap 5. Все нужные зависимости уже в `pyproject.toml` (`fastapi`, `uvicorn[standard]`, `jinja2`, `passlib[bcrypt]`, `itsdangerous`).

TASK-019 — **только скелет**: каркас FastAPI-приложения, готовый шаблон Bootstrap 5, базовая структура `routes/templates/static`, healthcheck, заглушки страниц без бизнес-логики и без аутентификации (auth — отдельной задачей **TASK-020**).

**Выбор Bootstrap 5 шаблона: Volt Free от Themesberg.**

Источники:

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) — структура страниц, шаблон файлов `src/admin/`, безопасность (HTTPS, CSRF, cookie-настройки).
- [`docs/02-tech-stack.md`](../../docs/02-tech-stack.md) — стек.
- [`docs/07-deployment.md`](../../docs/07-deployment.md) — упоминание nginx + uvicorn для админки в проде.

## Перед стартом — pre-task cleanup PR

В origin/main `94e666c` — последний коммит (archive TASK-018). **Working tree этой машины:**

- `state/PROJECT_STATUS.md` — закрытие TASK-018 + Этапа 2, новый шаг TASK-019.
- `state/DECISIONS.md` — 2 новых строки (release of `Event` invariant; cowork checks docs/03 invariants).
- `state/BACKLOG.md` — 1 новый пункт тех-долга (`fresh_db` CASCADE TRUNCATE).
- Новая сессия `sessions/2026-05-24-04-task-018-block-resolution/` + `sessions/2026-05-24-05-task-018-review/` (если первая уже в git — только вторая).
- `handoff/inbox/TASK-019-admin-skeleton.md` — эта задача.

Проверь `git log --oneline -5` — если PR #51 (block resolution) уже включил `sessions/2026-05-24-04`, тогда в working tree только `-05`. Branch: `chore/post-TASK-018-cowork-cleanup`, PR. После merge — `feature/TASK-019-admin-skeleton`.

## Цель

Запускаемый `uv run uvicorn src.admin.app:app --reload` FastAPI-сервер с базовым Bootstrap 5 layout'ом, статическими файлами темы, шаблонами `base.html` / `login.html` / `dashboard.html` (заглушки без логики), `/healthz`-эндпоинтом. Скрипт `scripts/create_admin.py` создаёт первого админа в БД через bcrypt-hash. **Без реальной аутентификации** — это TASK-020.

## Definition of Done

### Step 1 — Скачать Volt Free template

- [ ] **Volt Free** — публичный Bootstrap 5 admin template от Themesberg (MIT License). Репозиторий: `https://github.com/themesberg/volt-bootstrap-5-dashboard`.
- [ ] Скачать релиз или clone'нуть, взять оттуда:
  - `dist/assets/css/volt.css` → `src/admin/static/css/volt.css`
  - `dist/assets/img/` (минимально — `brand/`, `icons/`) → `src/admin/static/img/`
  - `dist/assets/js/volt.js` → `src/admin/static/js/volt.js`
- [ ] **Не качать** всё подряд — нам не нужны примеры страниц темы, нужны только базовые asset'ы. Размер копии должен быть в пределах нескольких MB.
- [ ] **Лицензия:** добавить в репо `src/admin/static/THIRD_PARTY_LICENSES.md` с упоминанием Volt MIT (1 файл, 10-15 строк — заголовок + копия MIT-текста или ссылка на оригинал).
- [ ] **HTMX и Bootstrap CDN.** Не качать — подключать через `<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.4">`, `<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">`. На MVP CDN допустим; будущий production-deployment в TASK-027 при необходимости перевернёт на self-hosted.

### Step 2 — `src/admin/app.py` — FastAPI application

- [ ] Module docstring «FastAPI admin app (TASK-019)».
- [ ] Минимальный код:
  ```python
  from __future__ import annotations

  from pathlib import Path

  from fastapi import FastAPI
  from fastapi.staticfiles import StaticFiles
  from fastapi.templating import Jinja2Templates

  from src.shared.logging import configure_logging, get_logger
  from src.shared.config import get_settings

  __all__ = ["app", "templates"]


  logger = get_logger(__name__)

  _BASE_DIR = Path(__file__).parent
  templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


  def create_app() -> FastAPI:
      s = get_settings()
      configure_logging(s.log_level, s.log_format)

      app = FastAPI(
          title="Betting Bot Admin",
          version="0.0.0",
          docs_url=None,         # OpenAPI docs не нужен для админки
          redoc_url=None,
      )

      app.mount(
          "/static",
          StaticFiles(directory=str(_BASE_DIR / "static")),
          name="static",
      )

      # Импорты в локальной области — избежать import-time side-effects.
      from .routes import dashboard as dashboard_routes
      from .routes import login as login_routes

      app.include_router(login_routes.router)
      app.include_router(dashboard_routes.router)

      @app.get("/healthz", tags=["meta"])
      async def healthz() -> dict[str, str]:
          return {"status": "ok"}

      logger.info("admin.startup")
      return app


  app = create_app()
  ```
- [ ] **`templates` экспортируется** для использования в роутах (`from src.admin.app import templates`).

### Step 3 — Routes-заглушки

#### `src/admin/routes/__init__.py`

- [ ] Пустой файл с docstring «Routes админки (TASK-019)».

#### `src/admin/routes/login.py`

- [ ] Заглушка без обработки POST (только GET формы — POST появится в TASK-020):
  ```python
  """Login route — форма входа. Реальная обработка POST — TASK-020."""

  from __future__ import annotations

  from fastapi import APIRouter, Request
  from fastapi.responses import HTMLResponse

  from ..app import templates

  __all__ = ["router"]


  router = APIRouter(tags=["auth"])


  @router.get("/login", response_class=HTMLResponse)
  async def login_form(request: Request) -> HTMLResponse:
      """Форма входа — отрендерена, POST пока не обрабатывается."""
      return templates.TemplateResponse(
          request=request,
          name="login.html",
          context={"error": None},
      )
  ```
  - **Без POST handler'а** — это TASK-020. Если кто-то отправит форму — получит 405. Это норм, временно.

#### `src/admin/routes/dashboard.py`

- [ ] Заглушка для главной:
  ```python
  """Dashboard route — заглушка. Реальные счётчики — после TASK-021/022/024/026."""

  from __future__ import annotations

  from fastapi import APIRouter, Request
  from fastapi.responses import HTMLResponse

  from ..app import templates

  __all__ = ["router"]


  router = APIRouter(tags=["dashboard"])


  @router.get("/", response_class=HTMLResponse)
  async def dashboard(request: Request) -> HTMLResponse:
      """Главная админки — заглушка. Auth добавится в TASK-020."""
      return templates.TemplateResponse(
          request=request,
          name="dashboard.html",
          context={"counters": {"users": 0, "events": 0, "categories": 0, "predictions": 0}},
      )
  ```
  - `counters` пока статические нули. Реальные значения подтянем в TASK-024+.

### Step 4 — Jinja2-шаблоны

#### `src/admin/templates/base.html`

Базовый шаблон с подключённым Bootstrap 5 (CDN) + Volt CSS (local) + HTMX (CDN). Структура:

```html
<!doctype html>
<html lang="ru" data-bs-theme="light">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Betting Bot Admin{% endblock %}</title>

    <!-- Bootstrap 5 + Volt -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="{{ url_for('static', path='css/volt.css') }}">

    <!-- HTMX -->
    <script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js"></script>

    {% block head_extra %}{% endblock %}
</head>
<body>
    {% block sidebar %}
        <nav class="sidebar"><!-- TASK-021+ заполнит --></nav>
    {% endblock %}
    <main class="content">
        {% block content %}{% endblock %}
    </main>
    <script src="{{ url_for('static', path='js/volt.js') }}"></script>
    {% block scripts_extra %}{% endblock %}
</body>
</html>
```

- [ ] Минимальный layout без полного sidebar (наполнится в TASK-021+).

#### `src/admin/templates/_macros.html`

- [ ] Пустой файл с комментарием «Reusable Jinja macros — наполнится в TASK-021+ (form-fields, status-badges, pagination)».

#### `src/admin/templates/login.html`

- [ ] Простая страница с формой:
  ```html
  {% extends "base.html" %}

  {% block title %}Вход — Betting Bot Admin{% endblock %}

  {% block content %}
  <div class="container py-5">
      <div class="row justify-content-center">
          <div class="col-md-4">
              <div class="card">
                  <div class="card-body">
                      <h4 class="card-title text-center">Вход</h4>
                      {% if error %}
                          <div class="alert alert-danger">{{ error }}</div>
                      {% endif %}
                      <form method="post" action="/login">
                          <div class="mb-3">
                              <label class="form-label">Логин</label>
                              <input type="text" name="login" class="form-control" required>
                          </div>
                          <div class="mb-3">
                              <label class="form-label">Пароль</label>
                              <input type="password" name="password" class="form-control" required>
                          </div>
                          <button class="btn btn-primary w-100" type="submit">Войти</button>
                      </form>
                  </div>
              </div>
          </div>
      </div>
  </div>
  {% endblock %}
  ```
  - Форма не работает (нет POST handler'а) — TASK-020 подключит.

#### `src/admin/templates/dashboard.html`

- [ ] Минимальная страница с counter-карточками:
  ```html
  {% extends "base.html" %}

  {% block title %}Дашборд — Betting Bot Admin{% endblock %}

  {% block content %}
  <div class="container py-4">
      <h1 class="mb-4">Дашборд</h1>
      <div class="row g-3">
          {% for key, value in counters.items() %}
          <div class="col-md-3">
              <div class="card text-center">
                  <div class="card-body">
                      <div class="display-4">{{ value }}</div>
                      <div class="text-muted text-uppercase">{{ key }}</div>
                  </div>
              </div>
          </div>
          {% endfor %}
      </div>
      <p class="text-muted mt-4">⚠️ Реальные счётчики подключатся в TASK-024+.</p>
  </div>
  {% endblock %}
  ```

### Step 5 — `src/admin/deps.py` (заглушка)

- [ ] Module docstring «DI dependencies админки (заглушка для TASK-020+)».
- [ ] Минимальный код для будущих импортов:
  ```python
  """DI dependencies для FastAPI-роутов админки.

  На TASK-019 — заглушка. Реальные dependencies (current_admin, db_session)
  появятся в TASK-020.
  """

  from __future__ import annotations

  __all__: list[str] = []  # пополнится в TASK-020
  ```

### Step 6 — `scripts/create_admin.py`

- [ ] Новый скрипт CLI для создания первого админа:
  ```python
  """CLI для создания первого админа.

  Использование:
    uv run python scripts/create_admin.py --login admin --password "secret"

  Скрипт хеширует пароль через passlib[bcrypt] cost=12 и пишет в admin_user.
  Если админ с таким login уже есть — отказ с понятным сообщением.
  """

  from __future__ import annotations

  import argparse
  import asyncio
  import sys

  from passlib.context import CryptContext

  from src.shared.db import SessionLocal
  from src.shared.models import AdminUser
  from sqlalchemy import select


  _pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


  async def create_admin(*, login: str, password: str, full_name: str | None) -> None:
      async with SessionLocal() as session:
          exists = await session.execute(
              select(AdminUser).where(AdminUser.login == login)
          )
          if exists.scalar_one_or_none() is not None:
              print(f"❌ Админ с login='{login}' уже существует.", file=sys.stderr)
              sys.exit(1)

          admin = AdminUser(
              login=login,
              password_hash=_pwd_ctx.hash(password),
              full_name=full_name or login,
          )
          session.add(admin)
          await session.commit()
          await session.refresh(admin)
          print(f"✅ Создан админ id={admin.id} login={admin.login}")


  def main() -> None:
      parser = argparse.ArgumentParser(description="Создать первого админа.")
      parser.add_argument("--login", required=True)
      parser.add_argument("--password", required=True)
      parser.add_argument("--full-name", default=None)
      args = parser.parse_args()

      asyncio.run(create_admin(
          login=args.login,
          password=args.password,
          full_name=args.full_name,
      ))


  if __name__ == "__main__":
      main()
  ```
  - **Проверь поле `AdminUser.password_hash`** в текущей модели. Если оно называется `password_hash` — оставь; если `hashed_password` — переименуй.
  - **`AdminUser.full_name`** есть из TASK-005 review (String(128)).
  - **`bcrypt__rounds=12`** соответствует требованию `docs/05-admin-spec.md` («cost ≥ 12»).
- [ ] Сделать скрипт исполняемым: `chmod +x scripts/create_admin.py` (но это не обязательно, можно запускать через `uv run python scripts/...`).

### Step 7 — Makefile target

- [ ] **В `Makefile`** добавить:
  ```makefile
  .PHONY: admin
  admin: ## Запустить веб-админку через uvicorn (auto-reload)
  	uv run uvicorn src.admin.app:app --reload --host 127.0.0.1 --port 8000
  ```
- [ ] Обновить `make help` (если автогенерируется по docstring'ам `## ...` — добавит сам).

### Step 8 — Smoke unit-тест

`tests/unit/admin/test_app_smoke.py` (создать каталог `tests/unit/admin/` + `__init__.py`):

- [ ] **3 unit-теста через FastAPI TestClient:**
  ```python
  """Smoke-тесты FastAPI-приложения админки (TASK-019)."""

  from __future__ import annotations

  from fastapi.testclient import TestClient

  from src.admin.app import app


  def test_app_builds_without_error() -> None:
      """Просто проверка, что FastAPI собрался."""
      assert app.title == "Betting Bot Admin"


  def test_healthz_returns_ok() -> None:
      client = TestClient(app)
      response = client.get("/healthz")
      assert response.status_code == 200
      assert response.json() == {"status": "ok"}


  def test_login_form_renders() -> None:
      client = TestClient(app)
      response = client.get("/login")
      assert response.status_code == 200
      assert "Вход" in response.text
      assert 'name="login"' in response.text
      assert 'name="password"' in response.text


  def test_dashboard_renders() -> None:
      client = TestClient(app)
      response = client.get("/")
      assert response.status_code == 200
      assert "Дашборд" in response.text
  ```
- [ ] **Внимание:** для импорта `from src.admin.app import app` нужно, чтобы `Settings()` собрался. В `tests/unit/conftest.py` уже stub'ятся env'ы (TASK-004). Если не хватит — добавь fixture для admin-окружения.
- [ ] Если используется `pytest-asyncio` — `httpx.AsyncClient` лучше, но `TestClient` (sync) проще для smoke. Используй `TestClient`.

### Step 9 — Каталог `tests/unit/admin/`

- [ ] `tests/unit/admin/__init__.py` — пустой.
- [ ] `tests/unit/admin/test_app_smoke.py` — из Step 8.
- [ ] **НЕ создавать** `tests/integration/admin/` сейчас — реальный E2E с базой будет в TASK-021+.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — расширить, чтобы покрыть и админку. Add `src/admin` в `[tool.mypy] files = [...]` или в CI команду.
- [ ] **mypy strict для `src/shared`** остаётся; для `src/admin/` (новое) — non-strict (как в bot, см. `docs/08-conventions.md`).
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая 4 новых smoke.
- [ ] `uv run pytest tests/integration -m integration` — без падений.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):**
  - `uv run python scripts/create_admin.py --login admin --password "test123!"` — создаёт админа.
  - `make admin` — uvicorn стартует на 127.0.0.1:8000.
  - В браузере `http://127.0.0.1:8000/healthz` → `{"status":"ok"}`.
  - `http://127.0.0.1:8000/login` → форма с полями login/password (POST не работает, но GET рендерится).
  - `http://127.0.0.1:8000/` → дашборд-заглушка с нулевыми счётчиками.
  - Volt CSS подгружается, страница имеет Bootstrap-стиль.
- [ ] Ветка `feature/TASK-019-admin-skeleton`, Conventional Commits:
  - `feat(admin): FastAPI скелет приложения + /healthz`
  - `feat(admin): Volt Free template assets`
  - `feat(admin): base.html + login.html + dashboard.html (заглушки)`
  - `feat(admin): /login GET + /  GET routes (заглушки)`
  - `feat(scripts): create_admin.py через passlib bcrypt`
  - `chore(makefile): make admin target`
  - `test(admin): smoke-тесты FastAPI app (4)`
  - `docs(admin): THIRD_PARTY_LICENSES.md для Volt Free`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-019-report.md`, задача → `handoff/archive/TASK-019-admin-skeleton/task.md`.

## Артефакты

```
+ src/admin/app.py
+ src/admin/deps.py
+ src/admin/routes/__init__.py
+ src/admin/routes/login.py
+ src/admin/routes/dashboard.py
+ src/admin/templates/base.html
+ src/admin/templates/_macros.html
+ src/admin/templates/login.html
+ src/admin/templates/dashboard.html
+ src/admin/static/css/volt.css         (из Volt Free)
+ src/admin/static/js/volt.js           (из Volt Free)
+ src/admin/static/img/...               (минимум — brand/icons)
+ src/admin/static/THIRD_PARTY_LICENSES.md
+ scripts/create_admin.py
+ tests/unit/admin/__init__.py
+ tests/unit/admin/test_app_smoke.py
* Makefile                                # +admin target
* pyproject.toml / CI                     # mypy include src/admin (если нужно)
```

## Ссылки

- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — спецификация админки целиком
- [docs/02-tech-stack.md](../../docs/02-tech-stack.md) — стек
- [docs/07-deployment.md](../../docs/07-deployment.md) — упоминание nginx + uvicorn для админки
- [Volt Free GitHub](https://github.com/themesberg/volt-bootstrap-5-dashboard) — Bootstrap 5 admin template (MIT)
- [src/shared/db.py](../../src/shared/db.py) — `SessionLocal` для скрипта
- [src/shared/models/admin_user.py](../../src/shared/models/admin_user.py) — модель AdminUser

## Подсказки исполнителю

- **Volt Free объёмный** (~10MB с примерами). Качай только `dist/assets/css/volt.css`, `dist/assets/js/volt.js`, `dist/assets/img/brand/`, `dist/assets/img/icons/`. Остальное — не нужно. После копирования размер `src/admin/static/` должен быть в пределах 1-3 MB.
- **Bootstrap 5 через CDN** на MVP допустимо. `docs/07-deployment.md` предполагает nginx с возможностью кешировать; production-deployment в TASK-027 решит, переключаться ли на self-hosted CSS/JS.
- **HTMX 2.x**, не 1.x — это разные API. Volt Free совместим с обоими, но новый Bootstrap 5.3+ требует HTMX 2.x для некоторых паттернов (например, `hx-target` через `<form>`).
- **`templates` экспортируется** из `src/admin/app.py` через `__all__`, не создавай его в каждом router'е. Это упростит будущие тесты.
- **`Jinja2Templates`** требует `directory=str(...)`, не `Path`. См. документацию FastAPI.
- **`TestClient` из `fastapi.testclient`** — НЕ `httpx.Client`. Он специально настроен для FastAPI с lifespan и dependency overrides.
- **`Settings()` при импорте `src.admin.app`** — стандартный паттерн. В тестах stub-env из `tests/unit/conftest.py` (TASK-004) должен это покрыть; если нет — добавь conftest на уровне `tests/unit/admin/`.
- **`docs_url=None, redoc_url=None`** в FastAPI — отключает OpenAPI/Swagger UI. Админка — внутренний инструмент, REST-API-docs не нужны.
- **`app.include_router(...)` после `app.mount(...)` со static** — FastAPI порядок не критичен, но для читаемости: static первым, потом routes.
- **`url_for('static', path='css/volt.css')`** в Jinja — стандартная Starlette-функция. Если jinja-renderer не понимает — проверь, что используется `request: Request` в `TemplateResponse(request=request, ...)` (новый стиль FastAPI 0.110+).
- **AdminUser.login или AdminUser.username?** Проверь модель `src/shared/models/admin_user.py` — какое именно имя поля. Адаптируй `scripts/create_admin.py` и `tests/unit/admin/...` под реальное.

## Что НЕ делать

- **Не делать реальную аутентификацию** — это TASK-020 (логин/пароль verify, signed cookie, middleware, fastapi-limiter, CSRF).
- Не добавлять бизнес-роуты (CRUD категорий/событий/исходов) — это TASK-021..024.
- Не делать HTMX-fragments — пока нет реальных списков для inline-edit, HTMX не нужен.
- Не оборачивать `/` и другие endpoint'ы в `require_admin` — middleware появится в TASK-020. На TASK-019 dashboard доступен всем.
- Не настраивать CSRF — это TASK-020.
- Не качать весь репозиторий Volt Free со всеми примерами и темами — только минимальные assets.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не добавлять зависимости (все нужные уже в pyproject).
- Не зеркалить в Drive вручную — это зона cowork.
