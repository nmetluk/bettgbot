---
id: TASK-062
created: 2026-05-30
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/admin/app.py
  - src/admin/auth/middleware.py
  - src/admin/auth/security.py
  - src/admin/routes/login.py
  - src/admin/templates/login.html
  - infra/Dockerfile.web
  - infra/nginx/admin.conf.template
priority: high
estimate: M
---

# TASK-062: Прод-админка на домене не пускает в систему — починить CSRF под prod-env + сопутствующие дефекты

## Контекст

Админка выложена на реальный домен `a.pinbetting.ru` (HTTPS, nginx + Let's Encrypt,
`ENVIRONMENT=prod`). **Залогиниться невозможно.** Проведён live-аудит через браузер +
разбор кода — первопричина и сопутствующие дефекты установлены однозначно.

### Дефект №1 (БЛОКЕР) — `POST /login` всегда 403 на проде, CSRF-валидация в дедлоке

Live-факт: `POST /login` на домене возвращает **403** при любой попытке входа, включая боевые
креды. Механизм:

- На проде (`environment != "dev"`) `CsrfTokenMiddleware` (`src/admin/auth/middleware.py`) на каждом
  GET руками ставит CSRF-cookie под именем `CSRF_COOKIE_NAME_PROD = "__Host-fastapi-csrf-token"`
  (`src/admin/auth/security.py`).
- Валидацию делает библиотека `fastapi-csrf-protect`: `csrf_protect.validate_csrf(request)` в
  `src/admin/routes/login.py`. Она читает cookie по своему `cookie_key`, а он **не переопределён**
  в `_csrf_config()` (`src/admin/app.py`) и равен дефолту `"fastapi-csrf-token"` (подтверждено в
  `.venv/.../fastapi_csrf_protect/core.py`: `signed_token = request.cookies.get(self._cookie_key)`,
  `load_config.py`: `cookie_key = "fastapi-csrf-token"`).
- Имена куки не совпадают (`__Host-fastapi-csrf-token` записана, `fastapi-csrf-token` читается) →
  `MissingTokenError`/`CsrfProtectError` → 403.
- **Дедлок:** единственное место, где кука ставится под библиотечным именем (`csrf_protect.set_csrf_cookie`),
  — это пути логин-роута, которые выполняются только ПОСЛЕ успешной `validate_csrf`. Поскольку валидация
  падает раньше, корректная кука никогда не выставляется. На проде войти нельзя в принципе.

На IP (`5.188.88.78:8888`) логин работал, т.к. no-domain режим стартует с `ENVIRONMENT=dev`
(`infra/.env.web.example`), где имя куки `fastapi-csrf-token` совпадает с дефолтом библиотеки.

### Дефект №2 — шаблон логина маскирует реальную ошибку

`src/admin/templates/login.html` (~строка 150) в блоке `{% if error %}` выводит **захардкоженный**
текст «Неверный логин или пароль», игнорируя реальную переменную `error`. Поэтому 403-ответ CSRF
(а также «аккаунт отключён», «сессия истекла») показывается пользователю как «неверный пароль».
Именно это сбило диагностику: при дефекте №1 кажется, что не подходят креды. Чинить вместе с №1,
иначе любые будущие сбои снова будут замаскированы.

### Дефект №3 — статика отдаётся по `http://` (схема прокси не учитывается)

Страница грузится по HTTPS, но в разметке ссылки на свою статику — абсолютные
`http://a.pinbetting.ru/static/...` (из `url_for('static', …)` в `base.html`). Live: первые хиты по
`http://` → **503**, затем HSTS-апгрейд до `https://` → 200. Стили в итоге подтягиваются, но через
сбойный первый запрос — поведение хрупкое и неверное.

Причина: работающее приложение не применяет `X-Forwarded-Proto` от nginx, поэтому `url_for` строит
схему `http`. В `infra/Dockerfile.web` флаги `--proxy-headers --forwarded-allow-ips=*` уже есть —
значит, на сервере либо устаревший образ, либо web не пересобран. Нужна двойная защита: гарантировать
proto на уровне кода (не зависеть от CMD-флагов) **и** перевести ссылки на статику на root-relative.

### Дефект №4 (мелкие)

- `_login_rate_limit` (`src/admin/routes/login.py`) при превышении лимита делает `raise JSONResponse(...)`
  — `Response` не исключение, это само бросит `TypeError`. Должно подниматься `HTTPException(429, ...)`.
- Session-cookie `__Host-bb_admin_session` в `middleware.py` и `routes/login.py` ставится **без явного
  `Path=/`** (комментарии «browser подставляет Path=/» неверны — префикс `__Host-` требует явного `Path=/`,
  иначе sliding-TTL на глубоких путях, напр. `/categories/5/edit`, браузер отвергает пересохранение).
- `docs/07-deployment.md` советует открыть `https://your-domain.com/admin`, хотя роуты смонтированы на `/`
  → 404.

## Цель

На проде (`ENVIRONMENT=prod`, HTTPS за nginx) администратор успешно логинится: `POST /login` с валидной
CSRF-парой возвращает 302 на `/`, неверные креды — 401 с **корректным** текстом, статика грузится по
`https://` с первого запроса. Никакого ослабления CSP/безопасности кук.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-062-report.md`.** Без отчёта CI handoff-consistency красный, PR не мёрджится.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен (см. `handoff/README.md`).

**Дефект №1 — CSRF (блокер):**

- [ ] CSRF-cookie, которую ставит `CsrfTokenMiddleware`, и cookie, которую читает
      `csrf_protect.validate_csrf`, имеют **одно и то же имя** под prod-env. Реализация на выбор, отразить
      в отчёте: (а) задать `cookie_key=CSRF_COOKIE_NAME_PROD` (и для dev — соответствующее) в `_csrf_config()`,
      чтобы библиотека читала/писала именно `__Host-`-имя; **либо** (б) отказаться от `__Host-` для CSRF-куки
      (оставить `fastapi-csrf-token` + `Secure` + без `Domain`), а `__Host-` сохранить только для session-cookie.
      Если выбран `__Host-` для CSRF — `set_csrf_cookie`/`set_cookie` библиотеки ОБЯЗАНЫ ставить `Secure`,
      `Path=/`, без `Domain` (иначе браузер отвергнет куку).
- [ ] Запись CSRF-куки централизована: нет ситуации, когда middleware пишет одно имя, а login-роут через
      `csrf_protect.set_csrf_cookie` — другое. Убрать дублирующую установку из `routes/login.py`, если она
      конфликтует с middleware (отразить решение в отчёте).
- [ ] Тест: под `ENVIRONMENT=prod` полный happy-path логина проходит — GET `/login` (кука выставлена) →
      `POST /login` с токеном из формы → **302** на `/` при валидных кредах. Тест **падал бы** на текущем коде.
- [ ] Тест: под prod неверные креды дают **401** (не 403), отключённый аккаунт — **403** с текстом про
      отключённый аккаунт; CSRF реально проверяется (POST без/с битым токеном → 403).

**Дефект №2 — текст ошибки:**

- [ ] `src/admin/templates/login.html` рендерит фактическую ошибку `{{ error }}` вместо захардкоженной
      строки. Хендлеры (`_render_login_error`, `_csrf_error_handler`) уже передают корректный `error` —
      убедиться, что значения осмысленны для пользователя.
- [ ] Тест на различение текстов: 401 → текст про неверные креды; 403/CSRF → текст про истёкшую сессию.

**Дефект №3 — схема статики:**

- [ ] Приложение применяет `X-Forwarded-Proto` независимо от CMD-флагов uvicorn: добавить
      `ProxyHeadersMiddleware` в `create_app()` (`from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware`,
      `trusted_hosts="*"`), либо эквивалент. Цель — `request.url_for(...)`/`url_for` выдают `https` за nginx.
- [ ] Defense-in-depth: ссылки на собственную статику в `base.html` (и прочих шаблонах) переведены на
      **root-relative** `/static/...` вместо `url_for('static', …)`, чтобы схема наследовалась от страницы.
      `git grep "url_for('static'" src/admin/templates/` → пусто (или осознанно оставлено с обоснованием в отчёте).
- [ ] Тест/проверка: при заголовке `X-Forwarded-Proto: https` сгенерированные абсолютные URL содержат `https`.

**Дефект №4 — мелкие:**

- [ ] `_login_rate_limit` поднимает `HTTPException(status_code=429, ...)` вместо `raise JSONResponse(...)`.
      Тест на 429 при >5 попытках, если выполнимо в unit-окружении (иначе отметить в отчёте).
- [ ] Session-cookie `__Host-bb_admin_session` ставится с явным `Path=/` и в `middleware.py`, и в
      `routes/login.py`, и в `/logout` (`delete_cookie(..., path="/")`).
- [ ] `docs/07-deployment.md`: `/admin` → `/` в шагах проверки (явно разрешено этой задачей менять `docs/`
      только в этой строке/секции проверки).

**Общее:**

- [ ] `ruff check` чист, `mypy src/admin src/shared` зелёный, `pytest` зелёный с новыми тестами.
- [ ] PR открыт, имя `TASK-062: fix prod admin login (CSRF/proxy-proto)`, CI зелёный, PR смёржен в `main`.
- [ ] Отчёт в `handoff/outbox/TASK-062-report.md`.
- [ ] **🚨 Move-семантика inbox→archive:** перед `chore(handoff): archive TASK-062 ...` выполнить
      `ls handoff/inbox/ | grep TASK-062`; найденное — `git rm` (и `TASK-062-fix-prod-admin-login.md`, и
      `TASK-062.in-progress.md`). В `handoff/archive/TASK-062-fix-prod-admin-login/` — одна копия (директорией!).

## Артефакты

- `* src/admin/app.py` — `_csrf_config()` (cookie_key) + `ProxyHeadersMiddleware`
- `* src/admin/auth/middleware.py` — имя/атрибуты CSRF-куки, `Path=/` для session
- `* src/admin/auth/security.py` — возможно константы имён кук
- `* src/admin/routes/login.py` — устранение конфликта установки куки, фикс `_login_rate_limit`, `Path=/`
- `* src/admin/templates/login.html` — `{{ error }}`
- `* src/admin/templates/base.html` (+ др. шаблоны) — root-relative `/static/...`
- `* tests/unit/...` — happy-path логина под prod, различение 401/403, 429, proto→https
- `* docs/07-deployment.md` — `/admin` → `/` (только секция проверки)

## Подсказки исполнителю

- Прод-режим в тестах включается `monkeypatch.setenv("ENVIRONMENT", "prod")` + `get_settings.cache_clear()`
  (см. как это делают существующие тесты конфига/мидлвари). Текущие тесты логина, скорее всего, гоняются
  под dev — добавь явный prod-вариант, иначе баг не ловится.
- `__Host-` префикс valid только при: `Secure` + `Path=/` + **без** `Domain`. Любое нарушение → браузер
  молча отвергает куку (в DevTools → Application → Cookies видно отсутствие). Если выберешь `cookie_key`
  с `__Host-` для библиотеки — проверь, что `set_csrf_cookie` библиотеки выставляет `Path=/` и `Secure`
  (в prod `cookie_secure=True` уже стоит в `_csrf_config()`; `Path` библиотека ставит `/` по умолчанию).
- Не ослабляй CSP (`_security_headers.py`) и не трогай доменную/сервисную логику — дефекты чисто в
  транспорте кук, генерации URL и тексте шаблона.
- После мёржа владелец передеплоит web-образ (`make prod.build && make prod.up` или pull свежего GHCR-тега) —
  проверка на проде (на владельце): GET `/login` → DevTools видит CSRF-куку с верным именем/атрибутами;
  логин боевыми кредами → редирект на `/`; статика грузится по `https` с первого запроса; консоль без
  CSP-ошибок. Отметь это в отчёте как остаточную проверку.
