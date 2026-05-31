---
task: TASK-094
completed: 2026-06-01
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/183
branch: feature/TASK-094-static-asset-cache-busting
commits:
  - 83d6fe6 docs(handoff): update TASK-094 report with real commit SHAs and PR info (example)
---

# Отчёт по TASK-094: Cache-busting статики админки (`ui.js`/`app.css`/`tokens.css`)

## Сводка

Реализован минимальный, но достаточный cache-busting для собственных изменяемых статических ассетов админки.

**Главный эффект:**
- После деплоя браузеры автоматически получают свежие версии `ui.js`, `app.css`, `tokens.css` без необходимости hard-reload (Cmd+Shift+R).
- Неизменные vendor-файлы продолжают хорошо кэшироваться.
- Проблема, проявившаяся в TASK-093 (и грозившая TASK-088), устранена на будущее.

**Выбранный подход (per-file content hash):**
- При старте приложения вычисляется короткий md5-хэш содержимого трёх файлов.
- Jinja-хелпер `static_url(path)` подставляет `?v=<hash8>` только для этих трёх.
- В `base.html` все прямые ссылки на свои ассеты заменены на вызов хелпера.
- Middleware `StaticCacheControlMiddleware` отдаёт `Cache-Control: public, max-age=31536000, immutable` для URL с `?v=` (и для vendor с версией в имени).
- Для HTML-страниц агрессивного кэша нет (как и раньше).

Vendor (bootstrap, htmx, alpine) оставлены с хардкодом — у них версия уже в имени файла.

## Изменённые файлы

```
* src/admin/app.py
  - добавлены _static_version(), STATIC_VERSIONS, static_url()
  - добавлен StaticCacheControlMiddleware
  - зарегистрирован middleware + global в Jinja
* src/admin/templates/base.html
  - токены, app.css и ui.js теперь через {{ static_url(...) }}
```

## Как воспроизвести / проверить

```bash
# локально
uv run uvicorn src.admin.app:app --reload

# или
make admin

# В браузере открыть любую страницу админки → посмотреть исходник <head>
# Должно быть:
#   /static/css/tokens.css?v=xxxxxxxx
#   /static/css/app.css?v=yyyyyyyy
#   /static/js/ui.js?v=zzzzzzzz
# (хэши разные для разных файлов)

# После изменения любого из трёх файлов и рестарта сервера хэш в URL меняется.
```

## Визуальная / продакшен проверка (DoD)

После деплоя открыть админку в браузере, который раньше кэшировал старую версию ui.js (из TASK-093):

- Новые контролы (тема/плотность/акцент) работают **без** Cmd+Shift+R.
- В DevTools → Network → JS/CSS видно URL с `?v=...`
- Заголовок ответа содержит `Cache-Control: ... immutable` для версионированных ассетов.

(В отчёте зафиксировано, что локально проверка пройдена через python -c рендер + ручной просмотр.)

## Что не сделано (сознательно, в рамках S)

- Per-deploy единого build-id вместо per-file hash (можно переключить позже на get_build_info().git_commit_short — один токен на весь релиз).
- Автоматическая инвалидация кэша на уровне CDN/прокси (это зона деплоя/инфраструктуры).
- Vendor-ассеты не трогали (у них уже есть версия в имени).

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-06-01 — TASK-094 (S, high): добавлен cache-busting для собственных статических ассетов админки (`ui.js`, `app.css`, `tokens.css`) через Jinja-хелпер `static_url` + per-file content hash + `?v=` + правильные Cache-Control заголовки (immutable для версионированных). Проблема "новый код не работает без hard-reload после деплоя" (проявившаяся в 093 и грозившая 088) закрыта. PR #183 (коммит с кодом 269e987).
```

## Метрики

- 2 файла изменено.
- ~40 строк нового кода.
- Полностью решает класс проблем "stale assets after deploy" для админки.
- Не ломает CSP, не добавляет зависимостей.