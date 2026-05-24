# Решения — task-020-review

**5 keep + 1 change + 1 в тех-долг:**

| # | Решение | Альтернативы | Обоснование |
|---|---|---|---|
| 1 | `fastapi-limiter 0.1.6` остаётся, **тех-долг BACKLOG**: «переход на 0.2+» | Сразу мигрировать на 0.2.x | В 0.2 переписан API на `pyrate-limiter` (`Limiter` вместо `FastAPILimiter`, новые `Depends`). Локальный CC правильно пиннул `<0.2`. Триггер перехода — security advisory или нужда в новых фичах |
| 2 (**change**) | **Secure cookie conditional через `Settings.environment`** — закрываем в Step 0 TASK-021 | Оставить `Secure=True` всегда + требовать https-прокси на dev | Без conditional Secure разработчик на `http://localhost:8000` получит **бесконечный редирект на /login** (браузер не отправит Secure cookie). Settings.environment ∈ `{"dev", "staging", "prod"}` с conditional `secure=` в cookie helpers. Default — `"dev"` для удобства локальной разработки; в prod `.env` явно ставится `prod`. Реализация — небольшое расширение Settings + 4-5 точек правок в `middleware.py` + `routes/login.py` |
| 3 | `/logout` в public-paths (whitelist) — keep | Logout под auth | Logout без cookie = no-op. Помещение под auth даёт цикл при stale-token: пользователь не может ни войти (cookie невалидный), ни выйти (требуется auth). Public с no-op — самая чистая семантика |
| 4 | CSRF methods explicit `{POST, PUT, PATCH, DELETE}` — keep | Default (`None`, по умолчанию POST) | Защита для будущих TASK-021+ роутов с PUT/PATCH/DELETE без необходимости править CSRF-config в каждой задаче. Минимальный диффер от default'а |
| 5 | Lazy `_get_session_maker()` в `RequireAdminMiddleware` — keep | `app.state.session_maker` через lifespan | Компромисс ради тестируемости (`patch.object` на module-level `SessionLocal`). `app.state` требует `request.app.state`, что усложняет тесты middleware изолированно. Если найдём более элегантный способ — отдельная refactor-задача |
| 6 | Lifespan + import-time `app = create_app()` — keep | Отказаться от import-time `app` (фабрика без attr-доступа) | Unit-тесты используют `dependency_overrides[RateLimiter] = noop`. Для прода — `make admin` запускает uvicorn → lifespan → FastAPILimiter.init. Текущая структура соответствует стандартному FastAPI-паттерну |

## Timing-attack mitigation паттерн (фиксируется как принцип)

В `AdminAuthService.authenticate` при `admin is None` делается dummy `bcrypt.checkpw(password.encode(), b"$2b$12$" + b"x"*53)`. Это анти-enumeration: время отклика не различает «login не найден» vs «password не подходит». Generic-error `AdminInvalidCredentialsError` ровный в обоих случаях.

Применять во всех будущих auth-сервисах (если появятся).
