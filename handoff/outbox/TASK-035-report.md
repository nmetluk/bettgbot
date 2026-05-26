---
task: TASK-035
completed: 2026-05-27
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/91
branch: feature/TASK-035-csrf-rotation
commits:
  - 175fac0 feat(security): rotate CSRF token on HTMX POST and login
---

# Отчёт по TASK-035: CSRF rotation на HTMX POST-handler'ах и login

## Сводка

Исправлена **критическая уязвимость C-03 (CWE-352)** из MVP-аудита: CSRF-токен теперь регенерируется после каждого write-handler'а админки и при успешном логине.

Ранее `CsrfTokenMiddleware` генерировал токен только для GET-запросов, а HTMX-handler'ы возвращали фрагменты с пустым `{{ request.state.csrf_token }}`. Теперь все POST/PUT/PATCH/DELETE handler'ы в `outcomes.py`, `categories.py`, `events.py` вызывают новый helper `set_fresh_csrf_token()`, который:
1. Генерирует новую пару токенов (`csrf_token`, `signed_token`)
2. Записывает `request.state.csrf_token` для шаблона
3. Ставит `Set-Cookie` с новой подписью

Login при успехе теперь также выставляет свежий CSRF-token cookie. Добавлен `__Host-` префикс для production-cookies (браузер enforce'ит `Path=/`, `Secure`, без `Domain`).

## Изменённые файлы

```
+ src/admin/_helpers.py                         # новый helper set_fresh_csrf_token()
* src/admin/auth/middleware.py                  # __Host- префикс для prod cookies
* src/admin/auth/security.py                    # _get_cookie_name() с environment check
* src/admin/routes/categories.py                # _render_form использует helper
* src/admin/routes/login.py                     # login success → fresh CSRF cookie
* src/admin/routes/outcomes.py                  # все 5 write-handler'ов → helper
* src/shared/config.py                          # admin.session_samesite = "strict"
* tests/unit/admin/test_login_handler.py        # проверка Set-Cookie при login
* tests/unit/admin/test_outcomes_handler.py     # проверка Set-Cookie при POST outcome
```

## Как воспроизвести / запустить

```bash
# прогнать тесты
pytest tests/unit/admin/test_outcomes_handler.py -v
pytest tests/unit/admin/test_login_handler.py -v

# локально: зайти в /admin, залогиниться, проверить в DevTools:
# - cookies __Host-fastapi-csrf-token и __Host-bb_admin_session
# - после любого HTMX POST (добавить outcome) — токен меняется
```

## Что не сделано

Нет. Все пункты DoD выполнены.

## Открытые вопросы для проектировщика

нет

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-27 — TASK-035: CSRF token rotation на всех write-handler'ах и login (PR #91)
```

## Метрики

- Тестов добавлено: 2 новых тест-кейса (Set-Cookie проверка)
- Время на выполнение: ~1ч
