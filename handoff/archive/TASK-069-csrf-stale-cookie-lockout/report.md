---
task: TASK-069
completed: 2026-05-30
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/126
branch: feature/TASK-069-csrf-stale-cookie-lockout
commits:
  - 2d73107 fix(admin): CSRF cookie self-heal on stale cookie (TASK-069)
  - db54733 fix(admin): ruff imports fix for tests (TASK-069)
---

# Отчёт по TASK-069: BLOCKER — фикс ротации 068 ломает вход для браузеров со «старой» CSRF-кукой

## Сводка

**Корень проблемы:** В `CsrfTokenMiddleware._get_token_from_cookie` декодирование CSRF-куки шло с `max_age=None`, что принимало просроченные куки (>15 мин). При этом `validate_csrf` на POST использует `max_age=900`. Это приводило к 403 «Сессия истекла» для возвращающихся пользователей.

**Решение:**
1. Вынес `CSRF_TTL_SECONDS = 900` как единую константу в `src/admin/auth/security.py`
2. `_get_token_from_cookie` теперь декодирует с тем же TTL, что и `validate_csrf`
3. Просроченная кука → `SignatureExpired` → `None` → middleware выдаёт свежую (self-heal)
4. `_csrf_config` в `app.py` использует константу вместо захардкоженного 900

**Скользящее окно** (опциональный пункт задачи) реализовано частично: при просроченной/битой куке middleware выдаёт новую валидную пару (self-heal). Активное продление «стареющей» валидной куки не реализовано — это усложнило бы код без существенной выгоды (TTL=15 мин достаточен для заполнения формы).

## Изменённые файлы

```
* src/admin/auth/security.py          # +CSRF_TTL_SECONDS константа
* src/admin/app.py                     # _csrf_config использует константу
* src/admin/auth/middleware.py        # _get_token_from_cookie с TTL
* tests/unit/admin/test_middleware.py # +2 новых теста
```

## Как воспроизвести / запустить

```bash
# прогнать тесты middleware
uv run pytest tests/unit/admin/test_middleware.py -v

# проверить весь проект
uv run pytest tests/unit/ -q
uv run ruff check src/admin/ tests/unit/admin/
uv run mypy src/admin/
```

## Что не сделано

**Скользящее окно** для «стареющей» валидной куки (переиздание с тем же токеном и свежим timestamp) не реализовано:
- Причина: усложняет код без существенной выгоды
- TTL=15 мин достаточен для заполнения формы
- Текущее решение (self-heal при просрочке) покрывает кейс возвратившегося пользователя
- При необходимости можно выделить отдельную задачу

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — **TASK-069 ЗАКРЫТ:** CSRF self-heal на просроченной куке. `CSRF_TTL_SECONDS` как единая константа для декодирования и валидации. 2 новых теста покрывают сценарий «старая кука → не 403». PR #126.
```

## Метрики

- Тестов добавлено: 2 (test_stale_csrf_cookie_self_heals_on_next_get, test_csrf_cookie_respects_ttl_in_decode)
- Время на выполнение: ~2 часа (включая отладку ruff импортов)
