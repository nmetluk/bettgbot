# Полный технический аудит Betting Bot — 2026-05-31

| | |
|---|---|
| **Дата** | 2026-05-31 |
| **Аудируемый коммит** | `08adb25` (origin/main, после merge TASK-084 #158) |
| **Версия** | `v0.1.0` (тег выставлен, релиз готов) |
| **Аудитор** | cowork-агент (read-only анализ чистого снапшота `git archive origin/main`) |
| **Прогон инструментов** | `uvx ruff check .` → **clean** (verified). `mypy`/`pytest` **не прогнаны** в sandbox: проект требует Python 3.12 (`requires-python >=3.12,<3.13`), а загрузка standalone-интерпретатора в окружении аудита заблокирована сетью. По остальным джобам — статический разбор + отчёты исполнителя (заявлены зелёными, CI на main зелёный). **Dev-машине: перепрогнать `uv run mypy src/shared src/bot src/admin` и `uv run pytest`.** |
| **Объём** | 98 py-модулей в `src/` (~10 260 строк), 70 тест-файлов (~447 тест-функций, 41 unit + 29 integration), 21 шаблон, 6 миграций. |

## Executive summary

Кодовая база зрелая и здоровая. С прошлого аудита (`2026-05-30`, коммит `0a508e7`, TASK-062) проделана большая работа по prod-hardening: закрыт **блокер прод-логина** (B1 → TASK-063), унифицирована timezone-стратегия (aware UTC везде → TASK-067), починена ротация CSRF-куки и self-heal на просроченной куке (TASK-068/069), исправлена вёрстка admin-шелла и a11y-контраст (TASK-070/071/072), устранён supply-chain вектор CDN через self-host всех вендорных ассетов (L5 → TASK-079), убраны инлайновые `on*=`-обработчики под строгим CSP (TASK-084), настроен полностью автоматический merge-гейт (TASK-077), build-info для GHCR-образов (TASK-081) и подготовлен релиз v0.1.0 (TASK-082/083).

Архитектура чистая: **ноль прямых DB-операций в роутерах/хендлерах** (слоистость соблюдена), Protocol-абстракция внешнего реестра с mock/http без обхода, линейная цепочка миграций `0001 → 0002 → 0003 → 0003b → 0004 → 0005`, рассылки с `FOR UPDATE SKIP LOCKED` + идемпотентным `record_delivery` + батчевыми commit-границами, строгий CSP (`script-src 'self'`, без `'unsafe-inline'` для скриптов), CI из 6+ джобов с реальным гейтингом (включая bandit fail-on-HIGH/CRITICAL), ruff чист.

**Блокеров нет.** Но **две Medium-находки прошлого аудита (M1, M2) так и остались открытыми** — предложенные тогда TASK-064/065 не были заведены, и эти дефекты надёжности/целостности данных всё ещё в коде. Плюс три Low-находки (L1–L3) тоже не закрыты. Это главный вывод аудита: верх воронки (блокеры, security) проработан отлично, а «хвост» средних/низких находок дрейфует. Рекомендуется завести их явными задачами, чтобы не потерять.

## Находки

| ID | Severity | Категория | Файл:строка | Описание | Риск | Направление фикса |
|----|----------|-----------|-------------|----------|------|-------------------|
| **M1** | **Medium** | Целостность данных | `src/shared/models/broadcast.py:44,75-76`; `src/migrations/versions/0005_broadcasts.py:70-98` | FK `category_id` с `ondelete="SET NULL"` прямо конфликтует с CHECK `(segment='category' AND category_id IS NOT NULL) OR (segment != 'category')`. Удаление категории, на которую ссылается рассылка с `segment='category'`, выставит `category_id=NULL` → нарушит CHECK → `DELETE` упадёт с невнятной constraint-ошибкой на уровне БД. **Перенесено из аудита 2026-05-30 (там же M1) — не исправлено.** | Удаление категории с историей рассылок ломается на уровне БД; неочевидный отказ вместо осмысленного поведения. | Решить осознанно: либо `ondelete="RESTRICT"` (явный запрет + понятная доменная ошибка в `CategoryService`), либо хранить `segment`/название снимком и релаксировать CHECK для исторических строк. Отразить в `docs/03-data-model.md`. → **TASK-085**. |
| **M2** | **Medium** | Надёжность доставки | `src/bot/scheduler/jobs.py` — `dispatch_reminders`, единственный `session.commit()` в конце (~`:85`) | `dispatch_reminders` держит весь батч в одной транзакции: `dispatch_log.record(...)` зовётся до `send_message`, но commit — только в самом конце цикла. При краше бота в середине батча транзакция откатится → записи лога пропадут → на рестарте напоминания **разошлются повторно**. Рядом `dispatch_broadcasts` уже сделан crash-safe (батчевые commit'ы `commit_batch_size`, строки ~`:151,167,219-225`). **Перенесено из аудита 2026-05-30 (там же M2) — не исправлено.** | Дубли напоминаний при рестарте в середине окна доставки (импакт ниже, чем у рассылок, т.к. батч ограничен `window_minutes`, но класс бага тот же, что чинили amendment'ом TASK-061). | Коммитить запись лога до/сразу после отправки по-элементно или порциями, по образцу `dispatch_broadcasts`. → **TASK-086**. |
| **L1** | Low | Тех-долг / Ясность | `src/admin/app.py:123-131` | Комментарий утверждает, что `ProxyHeadersMiddleware` (добавлен первым, `:128`) — outermost. На деле Starlette `add_middleware` делает outermost **последний** добавленный (`SecurityHeadersMiddleware`, `:131`), а `ProxyHeaders` оказывается innermost. На практике безвредно (uvicorn `--proxy-headers` правит схему на уровне сервера, куки и редиректы от этого не зависят), но комментарий вводит в заблуждение. **Перенесено из аудита 2026-05-30 (L1).** | Ложное ощущение, что схему правит именно этот middleware; запутает при отладке proxy-проблем. | Поправить комментарий и/или убрать дублирующий app-level `ProxyHeaders`, либо поставить его действительно outermost. → **TASK-087**. |
| **L2** | Low | Конвенция / Drift | `src/shared/models/broadcast.py:60`; `src/shared/models/broadcast_delivery.py:32` | `created_at`/`delivered_at` используют голую строку `server_default="now()"`, тогда как все остальные 11 моделей — `server_default=func.now()`. Рантайм определяется DDL миграции (ОК), но bare-string — футган при autogenerate (может отрендериться строковым литералом). **Перенесено из аудита 2026-05-30 (L2); теперь затронуты 2 модели.** | Потенциально неверный DDL при включении autogenerate; рассинхрон модель↔миграция. | Заменить на `server_default=func.now()` для единообразия. → **TASK-087**. |
| **L3** | Low | Нарушение конвенции i18n | `src/bot/routers/events.py:100,156` | Пользовательские строки на русском захардкожены в роутере: `f"<b>{category_name}</b> — страница {page+1}"` и `f"\n\n✅ Ваш прогноз: «{chosen.label}»"`. Конвенция (`CLAUDE.md`, `docs/08-conventions.md`) требует все тексты бота через `src/bot/texts.py`. Остальной роутер уже корректно использует `texts.*` + `safe_format`. **Перенесено из аудита 2026-05-30 (L3).** | Тексты не централизованы; правки/тон/перевод рассыпаны по хендлерам. | Вынести строки в `texts.py`, подставлять через `safe_format`. → **TASK-087**. |
| **L4** | Low (verify) | Безопасность (остаточная) | `src/admin/_security_headers.py:43` | CSP `style-src` всё ещё допускает `'unsafe-inline'` (для Bootstrap/HTMX-паттернов) — `script-src` уже строгий (`'self'`), но инлайновые стили разрешены. Низкий вектор (стили, не скрипты), но это единственное оставшееся послабление в CSP. | Теоретический CSS-инъекшн/exfil через инлайн-стиль; на практике маловероятно. | Опционально: вынести инлайн-стили в self-hosted CSS и убрать `'unsafe-inline'` из `style-src`. Не блокер релиза. |
| **L5** | Low | Инфра / Параллелизм | `infra/nginx/admin-no-domain.conf` vs `infra/nginx/admin.conf.template:1-2` | Доменный nginx-конфиг имеет `limit_req_zone` (login 10r/m, app 60r/m), а no-domain вариант — нет. Если прод поднят без домена (IP-only), nginx-level rate-limit на `/login` отсутствует (остаётся только app-level fastapi-limiter 5/min). | Двойная защита `/login` есть только при доменном деплое; на no-domain слой nginx-rate-limit отсутствует. | Перенести `limit_req_zone`/`limit_req` в no-domain конфиг для паритета (если этот режим используется в проде). |

## Статус находок прошлого аудита (`2026-05-30-full-audit.md`)

| ID | Что было | Статус сейчас | Чем закрыто / где |
|----|----------|---------------|-------------------|
| **B1** | Blocker: session-кука читается под dev-именем → прод-логин зациклен | ✅ **Закрыто** | TASK-063: `middleware.py:90-91` читает имя по окружению (`SESSION_COOKIE_NAME_PROD if env != "dev"`). Verified в коде. |
| **H1** | Тест-гэп: auth-тесты только под dev-именами кук | ✅ **Закрыто** | TASK-063: добавлен `test_prod_env_round_trip_with_correct_cookie_name` (по отчёту; dev-машине подтвердить прогоном). |
| **M1** | broadcast FK `SET NULL` vs CHECK | ❌ **Открыто** | TASK-064 не заведён. См. M1 выше → **TASK-085**. |
| **M2** | `dispatch_reminders` не crash-safe (один commit в конце) | ❌ **Открыто** | TASK-065 не заведён. См. M2 выше → **TASK-086**. |
| **L1** | Неверный комментарий о порядке middleware | ❌ **Открыто** | См. L1 выше → **TASK-087**. |
| **L2** | bare `server_default="now()"` | ❌ **Открыто** (расширилось на 2 модели) | См. L2 выше → **TASK-087**. |
| **L3** | Хардкод RU-строк в `events.py` | ❌ **Открыто** | См. L3 выше → **TASK-087**. |
| **L4** | CSRF `__Host`-кука: проверить вживую | ⚠️ **Снято/адресовано** | TASK-068/069 переработали CSRF-куку (нет ротации на каждый GET, self-heal на stale, единый TTL 900s). Пост-деплой verify в DevTools остаётся пунктом чек-листа. |
| **L5** | CSP `script-src` с jsdelivr без SRI | ✅ **Закрыто** | TASK-079: self-host 4 вендорных ассета в `src/admin/static/vendor/`, jsdelivr удалён из CSP. |

## Регрессы относительно прошлого аудита

Новых регрессов не выявлено. Timezone-фиксы (TASK-067) разобраны и консистентны: колонки `TIMESTAMP(timezone=True)` (с `0001_init`), helper `src/shared/time.utcnow()` → aware UTC, `app.py` отдаёт `utcnow` в шаблоны. Прежние naive/aware-баги из `bugs-found-during-update.md` (#3, #4) закрыты унификацией. Цепочка миграций линейна; исторический инцидент с переименованием `0004` (manual `UPDATE alembic_version` в проде) митигирован миграцией `0003b` (расширение `version_num` до varchar(64)).

## Что хорошо (для баланса)

- **Чистая слоистость**: `git grep` по `session.add/execute/commit/select(` в `src/admin/routes/` и `src/bot/routers/` — пусто. Бизнес-логика только в сервисах/репозиториях.
- **Безопасность входа**: bcrypt напрямую (cost=12) + anti-enumeration timing-mitigation, signed cookie (`itsdangerous`), ASGI `RequireAdminMiddleware` с whitelist, env-aware имена кук (`__Host-` на проде), rate-limit (fastapi-limiter 5/min + nginx 10r/m), CSRF с TTL и self-heal.
- **CSP**: `default-src 'self'`, `script-src 'self'` без `'unsafe-inline'`, ноль инлайновых `<script>`/`on*=` в шаблонах (TASK-084), все вендорные ассеты self-hosted.
- **Надёжность рассылок**: `claim_next_queued` через `SELECT ... FOR UPDATE SKIP LOCKED`, `record_delivery` до отправки, батчевые commit'ы — crash-safe.
- **CI**: lint (ruff check + format), mypy (strict для `src/shared/`), unit, integration на реальном postgres:16, bandit (fail on HIGH/CRITICAL), build-images, deploy-prod с авто-rollback на smoke-fail, backup-verify, auto-handoff-PR. ruff чист.
- **Handoff-дисциплина**: линейная нумерация задач, отчёты в outbox, archive с move-семантикой, CI handoff-consistency (включая guard на transient-суффиксы — TASK-080).

## Рекомендации по приоритизации

1. **Ближайшее (надёжность/целостность):** M1 (`TASK-085`) и M2 (`TASK-086`) — обе про данные/доставку, обе висят с прошлого аудита. Не блокируют v0.1.0, но это первый кандидат на пост-релизный спринт.
2. **Гигиена одним PR:** L1 + L2 + L3 (`TASK-087`) — комментарий middleware, `func.now()` в 2 моделях, вынос 2 строк в `texts.py`. Мелко, parallel-safe.
3. **Чек-лист/опционально:** L4 (`unsafe-inline` в `style-src`) и L5 (nginx no-domain rate-limit) — обсудить, не срочно.
4. **Dev-машине:** подтвердить зелёные `uv run mypy src/shared src/bot src/admin` и `uv run pytest` на `08adb25` (в sandbox аудита Python 3.12 недоступен).

## Заведённые задачи

По итогам аудита в `handoff/inbox/` положены:

- **TASK-085** — broadcast/category: согласовать `ondelete` и CHECK (M1), обновить `docs/03-data-model.md`.
- **TASK-086** — `dispatch_reminders`: crash-safe commit-границы по образцу `dispatch_broadcasts` (M2).
- **TASK-087** — cleanup: комментарий middleware-ordering (L1) + `func.now()` в broadcast/broadcast_delivery (L2) + вынос строк `events.py` в `texts.py` (L3). `parallel-safe: true`.
