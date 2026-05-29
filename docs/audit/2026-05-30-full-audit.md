# Полный технический аудит Betting Bot — 2026-05-30

| | |
|---|---|
| **Дата** | 2026-05-30 |
| **Аудируемый коммит** | `0a508e7` (origin/main, после merge TASK-062 #121) |
| **Аудитор** | cowork-агент (read-only анализ чистого снапшота `git archive origin/main`) |
| **Прогон инструментов** | `ruff check .` → **clean** (verified, ruff latest). `mypy`/`pytest` **не прогнаны** в sandbox: проект требует Python 3.12 (`requires-python ==3.12.*`), build-интерпретатора недоступен в окружении аудита. По остальным джобам — опора на статический разбор + отчёт исполнителя (заявлен зелёным). **Dev-машине: перепрогнать `uv run mypy src/shared src/bot src/admin` и `uv run pytest` для подтверждения.** |

## Executive summary

Кодовая база в целом здорова: чистая слоистость (бизнес-логики в роутах/хендлерах не найдено), Protocol-абстракция внешнего реестра с mock/http-реализациями, линейная цепочка миграций `0001→…→0005`, идемпотентная фоновая доставка рассылок с `FOR UPDATE SKIP LOCKED` и инкрементальными commit-границами, ноль инлайн-`<script>` в шаблонах под строгим CSP, добротный CI (lint + typecheck + unit + integration + gated bandit-SAST), ruff чист.

**Но найден BLOCKER, который означает, что прод-логин в админку ВСЁ ЕЩЁ не работает — TASK-062 закрыл проблему не до конца.** Это та же первопричина (env-зависимое имя cookie рассинхронено между записью и чтением), что чинил TASK-062, но в READ-пути session-куки, который правка проглядела. Корень того, что баг прошёл мимо CI, — системный: **весь набор auth-тестов гоняется только под dev-именами кук**, поэтому целый класс prod-cookie дефектов структурно невидим. Это главный приоритет: фикс на 1 строку + prod-env round-trip тест.

## Находки

| ID | Severity | Категория | Файл:строка | Описание | Риск | Направление фикса |
|----|----------|-----------|-------------|----------|------|-------------------|
| **B1** | **Blocker** | Bug / Безопасность | `src/admin/auth/middleware.py:82` | `RequireAdminMiddleware` читает session-куку **всегда** под dev-именем: `request.cookies.get(SESSION_COOKIE_NAME)` (`bb_admin_session`). А `login.py:144` и сам middleware (`:113`) **пишут** её под prod-именем `__Host-bb_admin_session` при `environment != "dev"`. На проде браузер шлёт `__Host-`-куку, middleware ищет `bb_admin_session` → `None` → `admin_id=None` → редирект на `/login`. **Итог: после успешного логина каждый authed-GET кидает обратно на /login — попасть в админку на проде невозможно.** TASK-062 выровнял CSRF read/write и session write/delete-имена, но READ session-куки оставил с захардкоженным dev-именем. | Прод-админка недоступна несмотря на смёрдженный TASK-062; деплой не «починит» логин. | На `:82` выбирать имя по окружению: `s=get_settings(); name = SESSION_COOKIE_NAME_PROD if s.environment != "dev" else SESSION_COOKIE_NAME; token = request.cookies.get(name)`. Обязательно добавить prod-env тест (см. H1). |
| **H1** | High | Тест-гэп | `tests/unit/admin/test_middleware.py` (и весь admin-auth набор) | Ни один auth-тест не гоняется под `ENVIRONMENT=prod`: `test_middleware.py` ставит/проверяет только `SESSION_COOKIE_NAME` (dev). Класс env-зависимых cookie-багов (причина и TASK-062, и B1) **структурно невидим** для CI. | Любой будущий рассинхрон имён кук между записью/чтением снова просочится в прод. | Добавить prod round-trip: `monkeypatch.setenv("ENVIRONMENT","prod")` + `get_settings.cache_clear()`; GET `/login` ставит `__Host-`-CSRF-куку → POST `/login` валидными кредами ставит `__Host-`-session-куку → следующий authed-GET принимается (тест **упал бы** на текущем коде из-за B1). |
| **M1** | Medium | Несоответствие / Целостность | `src/shared/models/broadcast.py:42-46,74-79`; `0005_broadcasts.py` | FK `category_id` с `ondelete=SET NULL` конфликтует с CHECK `segment='category' ⇒ category_id IS NOT NULL`. Удаление категории, на которую ссылается рассылка с `segment=category`, выставит `category_id=NULL` → нарушит CHECK → `DELETE` упадёт с невнятной ошибкой constraint (вместо осмысленного поведения). | Удаление категории с историей рассылок ломается на уровне БД; неочевидный отказ. | Решить осознанно: либо `ondelete=RESTRICT` (явный запрет удаления, понятная ошибка в сервисе), либо релакс CHECK для исторических строк (например, хранить `segment` снимком и не требовать FK для завершённых). Отразить в `docs/03-data-model.md`. |
| **M2** | Medium | Надёжность | `src/bot/scheduler/jobs.py` (`dispatch_reminders`, commit в конце ~`:86`) | `dispatch_reminders` держит весь батч в одной транзакции и коммитит только в конце; `dispatch_log.record` — до `send_message`. При краше бота в середине батча транзакция откатится → записи лога пропадут → на рестарте напоминания **разошлются повторно**. Тот же класс restart-дублирования, что чинили для рассылок в amendment TASK-061. | Дубли напоминаний при рестарте в середине окна (ниже импакт, чем у рассылок, т.к. батч ограничен `window_minutes`). | Коммитить запись лога до отправки по-элементно (или порциями), как сделано для `dispatch_broadcasts`, чтобы доставленные фиксировались до краша. |
| **L1** | Low | Тех-долг / Ясность | `src/admin/app.py:114-124` | Комментарий утверждает, что `ProxyHeadersMiddleware` — outermost, но `add_middleware` делает outermost **последний** добавленный (`SecurityHeadersMiddleware`), а `ProxyHeaders` (добавлен первым) оказывается innermost. На практике безвредно (uvicorn `--proxy-headers --forwarded-allow-ips=*` в `Dockerfile.web` правит схему на уровне сервера; куки зависят от env, редиректы относительные), т.е. app-level `ProxyHeaders` фактически избыточен. | Вводит в заблуждение; ложное ощущение, что схему правит именно этот middleware. | Поправить комментарий и/или убрать дублирующий app-level middleware, либо поставить его действительно outermost, если на него полагаются. |
| **L2** | Low | Конвенция / Drift | `src/shared/models/broadcast.py:60` | `created_at` использует голую строку `server_default="now()"`, тогда как миграция `0005` корректно использует `sa.text("now()")`. Рантайм определяется DDL миграции (ОК), но bare-string `server_default` — футган при autogenerate (может отрендериться как строковый литерал). | Потенциальный неверный DDL, если кто-то включит autogenerate; рассинхрон модель↔миграция. | В модели использовать `server_default=text("now()")` для единообразия с прочими моделями. |
| **L3** | Low | Нарушение конвенции i18n | `src/bot/routers/events.py:101,157` (и рядом) | Пользовательские строки на русском захардкожены в роутере: `f"<b>{category_name}</b> — страница {page+1}"`, `f"\n\n✅ Ваш прогноз: «{chosen.label}»"`. Конвенция (`CLAUDE.md`, `docs/08-conventions.md`) требует все тексты бота через `src/bot/texts.py`. | Тексты не централизованы; правки/перевод/тон рассыпаны по хендлерам. | Вынести строки в `texts.py`, подставлять через `safe_format`. |
| **L4** | Low (verify) | Безопасность (остаточная) | `src/admin/app.py:_csrf_config`, `routes/login.py:90,158` | Весь CSRF-фикс держится на том, что браузер примет `__Host-fastapi-csrf-token`. Префикс валиден только при `Secure`+`Path=/`+без `Domain`. `_csrf_config` ставит `cookie_secure` на проде, библиотека по умолчанию `cookie_path="/"` и без domain — должно работать, но не проверено вживую. | Если библиотечный `set_csrf_cookie` не выставит `Path=/`/`Secure` — кука молча отвергается, снова 403. | После деплоя подтвердить в DevTools атрибуты куки `__Host-fastapi-csrf-token`. |
| **L5** | Low | Безопасность (supply-chain) | `src/admin/_security_headers.py:41` | CSP разрешает `script-src … https://cdn.jsdelivr.net` без SRI/пиннинга. | Компрометация/подмена ресурса CDN → исполнение чужого JS. | Рассмотреть SRI-хеши на CDN-`<script>` или self-host критичных JS. |

## Подтверждение TASK-062

Диагноз и фиксы TASK-062 верны и реализованы корректно по **четырём** заявленным дефектам: CSRF `cookie_key` выровнен per-env (`app.py:_csrf_config`), `ProxyHeadersMiddleware` + root-relative `/static/`, `login.html` рендерит `{{ error }}`, `_login_rate_limit` → `HTTPException(429)`, явный `Path=/` для session-куки в write/delete. **Однако заявленная цель — «администратор успешно логинится на проде» — НЕ достигнута из-за B1:** правка выровняла имя session-куки в путях записи/удаления, но проглядела единственный путь **чтения** (`middleware.py:82`). Формально TASK-062 закрыл CSRF-403, но открыл/оставил session-cookie-loop. Рекомендуется немедленный hotfix (B1) одной строкой + тест H1, иначе прод-логин по-прежнему не работает.

## Регрессы относительно прошлого аудита

Прошлый аудит — `docs/audit/2026-05-25-mvp-audit.md` (MVP-срез). Новых регрессов по его пунктам в рамках этого прохода не выявлено; B1 — новый дефект, внесённый в ходе работ TASK-053..062 (admin v2 + prod-cookie hardening), а не регресс ранее закрытого.

## Что хорошо (для баланса)

Чистая слоистость (в `src/admin/routes/` нет прямых `session.add/execute/commit/select`), Protocol-абстракция `ExternalUserRegistryClient` с mock/http без обхода, линейные миграции, рассылки с `FOR UPDATE SKIP LOCKED` + идемпотентным `record_delivery` + батчевыми commit'ами, ноль инлайн-`<script>` под строгим CSP (`script-src 'self' …`, без `unsafe-inline`), CI с реальным гейтингом (включая bandit fail-on-HIGH/CRITICAL), ruff чист.

## Рекомендации по приоритизации

1. **Сейчас (hotfix):** B1 + H1 — иначе прод-админка недоступна, а TASK-062 даёт ложное ощущение «починено». Один PR, обязательно prod-env round-trip тест.
2. **Ближайшее:** M1 (целостность category/broadcast) и M2 (restart-дубли reminders) — оба про надёжность данных/доставки.
3. **Гигиена:** L1–L3 (ясность middleware, server_default, i18n) одним cleanup-PR; L4 — пункт чек-листа пост-деплоя; L5 — обсудить SRI.

## Предложения задач для проектировщика (не заведены)

- `TASK-063: hotfix prod session cookie read mismatch (Blocker)` — B1 (`middleware.py:82`, выбор имени по env) + H1 (prod-env auth round-trip тест). Скоуп узкий, parallel-safe: false, blocker.
- `TASK-064: broadcast/category FK vs CHECK integrity` — M1: согласовать `ondelete` и CHECK, обновить `docs/03-data-model.md`.
- `TASK-065: dispatch_reminders crash-safe commit boundaries` — M2: инкрементальные commit'ы по образцу `dispatch_broadcasts`.
- `TASK-066: admin/bot cleanup` — L1 (middleware ordering/комментарий), L2 (`text("now()")`), L3 (вынос строк в `texts.py`).
