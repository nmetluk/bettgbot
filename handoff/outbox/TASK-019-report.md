---
task: TASK-019
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/55
branch: feature/TASK-019-admin-skeleton
commits:
  - 491bc3e chore(handoff): take TASK-019 in progress
  - 02bae0b feat(admin): Volt Free assets (js + brand SVGs + MIT license + placeholder css)
  - 13254bf feat(admin): FastAPI скелет + /healthz + login/dashboard заглушки + base/login/dashboard.html
  - 47945ba feat(scripts): create_admin.py через bcrypt cost=12 (passlib обход)
  - ed492a4 chore(makefile): admin + admin.create targets
  - a48b6eb test(admin): smoke-тесты FastAPI app + CI mypy расширен на src/bot src/admin
---

# Отчёт по TASK-019: FastAPI скелет веб-админки + Volt Free assets + create_admin script

## Сводка

Старт Этапа 3. `src/admin/app.py` — FastAPI-приложение с `docs/redoc/openapi=None` (админка внутренняя, OpenAPI не нужен), mount `/static`, `Jinja2Templates`, `/healthz`. Routes-заглушки: `GET /login` (форма; POST в TASK-020), `GET /` (dashboard со статическими счётчиками). Templates: `base.html` подключает Bootstrap 5 + Bootstrap Icons + HTMX 2 через jsdelivr, Volt CSS — локальный placeholder. `scripts/create_admin.py` — CLI bcrypt cost=12 с проверкой существования логина. `Makefile`: `make admin`, `make admin.create LOGIN=… PASSWORD=…`. CI: mypy теперь покрывает `src/shared src/bot src/admin`. 4 unit smoke-теста через `TestClient`.

**Compromise по Volt:** Themesberg themesberg/volt-bootstrap-5-dashboard в master ships только SCSS-источники (`src/scss/volt.scss`); скомпилированный `dist/assets/css/volt.css` отсутствует. GitHub releases без assets, public CDN путей нет, локально `npm`/`node` недоступен. Ship'нул минимальный placeholder `css/volt.css` с HOWTO-комментарием + `js/volt.js` + `img/brand/{dark,light}.svg` + `VOLT_LICENSE.md` + `THIRD_PARTY_LICENSES.md`. На MVP Bootstrap 5 CDN покрывает базовую вёрстку.

**Compromise по passlib:** passlib 1.7.4 несовместима с bcrypt 5.0 (внутри passlib падает «password cannot be longer than 72 bytes» даже на 8-байтовых паролях из-за изменения API bcrypt). Использую `bcrypt` напрямую (`bcrypt.hashpw(secret, bcrypt.gensalt(rounds=12))`). Формат `$2b$…` тот же — TASK-020 верифит через `bcrypt.checkpw(...)`.

## Изменённые файлы

```
+ src/admin/app.py                                  # FastAPI app
+ src/admin/deps.py                                 # заглушка для TASK-020
+ src/admin/routes/__init__.py
+ src/admin/routes/login.py                         # GET /login
+ src/admin/routes/dashboard.py                     # GET /
+ src/admin/templates/base.html                     # Bootstrap+Icons+HTMX CDN + Volt local
+ src/admin/templates/_macros.html                  # placeholder
+ src/admin/templates/login.html                    # форма (POST не обрабатывается)
+ src/admin/templates/dashboard.html                # counter-карточки заглушка
+ src/admin/static/css/volt.css                     # placeholder + HOWTO
+ src/admin/static/js/volt.js                       # 11.5kB, из master src/assets/js/volt.js
+ src/admin/static/img/brand/dark.svg
+ src/admin/static/img/brand/light.svg
+ src/admin/static/VOLT_LICENSE.md                  # MIT
+ src/admin/static/THIRD_PARTY_LICENSES.md
+ scripts/create_admin.py                           # bcrypt CLI
* Makefile                                          # +admin +admin.create
* .github/workflows/ci.yml                          # mypy: shared+bot+admin
+ tests/unit/admin/__init__.py
+ tests/unit/admin/test_app_smoke.py                # 4 теста
* handoff/inbox/TASK-019-...md → archive/TASK-019-admin-skeleton/task.md
+ handoff/outbox/TASK-019-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    127 files already formatted
mypy src/shared src/bot src/admin   Success: no issues found in 66 source files
pytest -m "not integration"      160 passed in 1.78s
pytest tests/integration         91 passed (без регрессий)

Локально ручная проверка:
  make admin → uvicorn на 127.0.0.1:8000
  GET /healthz → {"status":"ok"}
  GET /login → форма с полями login/password (Bootstrap 5 стилизация работает)
  GET / → dashboard с 4 нулевыми counter-карточками
  GET /static/css/volt.css → 200 (placeholder)
  GET /static/js/volt.js → 200
  make admin.create LOGIN=admin-test-019 PASSWORD=test123!  → ✅ Создан админ id=…
  make admin.create LOGIN=admin-test-019 PASSWORD=test123!  → ❌ уже существует, exit 1

CI PR #55 — все четыре job'а зелёные:
  Lint (ruff)                              9s
  Typecheck (mypy)                         20s (src/shared + src/bot + src/admin)
  Tests (pytest, unit)                     19s (160 passed)
  Integration (alembic on real postgres)   47s (91 passed)
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env
make up && make migrate

# Создать админа
make admin.create LOGIN=admin PASSWORD="strong-secret!" FULL_NAME="Главный"

# Запустить админку
make admin
# http://127.0.0.1:8000/healthz
# http://127.0.0.1:8000/login
# http://127.0.0.1:8000/

uv run pytest tests/unit/admin -v
```

## Что не сделано / вынесено

1. **Скомпилированный `volt.css`** — ship'нул placeholder. Чтобы получить полный Volt-styling: `git clone https://github.com/themesberg/volt-bootstrap-5-dashboard.git && cd volt && npm install && npm run build && cp dist/assets/css/volt.css <project>/src/admin/static/css/`. Поставлю в открытые вопросы.
2. **passlib** — заменён на прямой `bcrypt`. Если cowork хочет вернуть passlib — потребуется pin `bcrypt<4.1` (старый API) или upgrade passlib до 1.7.5+ (если выйдет с поддержкой bcrypt 5.x). Сейчас `pyproject.toml` пин `passlib[bcrypt]>=1.7,<2`, bcrypt тянется как extras.
3. **POST /login** — 405. По плану — в TASK-020.
4. **Auth middleware**, **CSRF**, **rate limiting** — TASK-020.
5. **Бизнес-роуты** (CRUD категорий/событий/etc) — TASK-021..024.
6. **Реальные счётчики на dashboard** — TASK-024+.
7. **Icons в `static/img/icons/`** — не копировал (`github.svg`, `google_analytics.svg`, `google-tag-manager.svg`) — это иконки внешних сервисов, нам в админке Betting Bot не нужны. Если потом понадобятся свои SVG-иконки — добавлю в TASK-021+.
8. **`scripts/` без `__init__.py`** — нельзя запустить через `python -m`, нужен `PYTHONPATH=. uv run python scripts/...` (это Makefile target и делает). Если хотим красивее — `scripts/__init__.py` + ребрендинг под `python -m scripts.create_admin`. Не критично.

## Открытые вопросы для проектировщика

1. **Compiled `volt.css`** — как договоримся? Варианты:
   - (a) Оставить placeholder; полный styling — отдельной задачей с npm-build, когда понадобится.
   - (b) Я пробую `npx`-based build на CI / в отдельном Dockerfile.
   - (c) Подключить готовый Bootstrap-template поскромнее (например, `bootswatch` чтобы только тему — но это не Volt).
   Сейчас (a). Согласуем для TASK-020+, что в админке реально нужен фирменный стиль?
2. **passlib → bcrypt прямо** — окей? Если хотим вернуть passlib, придётся либо менять зависимости (`bcrypt<4.1`), либо ждать релиз passlib с поддержкой bcrypt 5. Прямой `bcrypt` не теряет ничего: тот же `$2b$…` формат, тот же cost-параметр, проще читать.
3. **`scripts/` запуск через `PYTHONPATH=. uv run python ...`** — некрасиво. Хотим сделать `scripts/__init__.py` + `python -m scripts.create_admin`? Или CLI-entrypoint в `pyproject.toml` (`[project.scripts]`)? Сейчас Makefile-обёртка скрывает уродство — пользователь видит только `make admin.create LOGIN=… PASSWORD=…`.
4. **Bootstrap Icons CDN** добавил без явного упоминания в спеке — нужны были для `bi-*` классов в будущих TASK-021+. Если предпочитаем без них до явного запроса — уберу. Сейчас одна строка `<link>` в `base.html`.
5. **OpenAPI выключен полностью** (`docs_url=None, redoc_url=None, openapi_url=None`). По спеке хватало первых двух, но `openapi_url=None` важнее — без него `/openapi.json` остаётся доступен и может утечь схему. Окей?

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-019: старт Этапа 3 (веб-админка). FastAPI-скелет в `src/admin/`: app.py, routes/login + routes/dashboard, templates base/login/dashboard, /healthz, mount /static. Volt Free assets (js + brand SVGs + MIT license; css/volt.css — placeholder, см. open-question #1). `scripts/create_admin.py` (bcrypt cost=12 напрямую, минуя passlib 1.7.4 ↔ bcrypt 5.0 incompat). Makefile: `make admin`, `make admin.create`. CI mypy расширен на src/bot src/admin. 4 unit smoke-теста (160 total). PR [#55](https://github.com/nmetluk/bettgbot/pull/55) → squash `c0dbe96`. Pre-task cleanup [#54](https://github.com/nmetluk/bettgbot/pull/54).
```

## Метрики

- Файлов добавлено: 17 (app + 2 routes + 4 templates + 5 static + 1 script + 2 tests + 1 report + __init__'ы)
- Файлов изменено: 2 (Makefile, ci.yml)
- Тестов добавлено: 4 (всего 160 unit + 91 integration)
- Время на выполнение: ~45 мин (включая cleanup PR, ресёрч Volt assets, разбор passlib↔bcrypt incompat, тесты)
