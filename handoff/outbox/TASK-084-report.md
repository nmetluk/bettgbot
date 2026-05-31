---
task: TASK-084
completed: 2026-05-31
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/158
branch: feature/TASK-084-csp-inline-handlers-break-admin-nav
commits:
  - 40a32bc fix(admin): CSP script-src 'self' blocks inline on*= handlers — data-href rows + <a> tabs + data-confirm + ui.js delegation (TASK-084)
---
# Отчёт по TASK-084: CSP `script-src 'self'` блокирует инлайновые on*-обработчики → навигация админки не работает

## Сводка

Полностью устранена причина блокировки релиза v0.1.0: строгий CSP (`script-src 'self'`, без `'unsafe-inline'`) больше не ломает навигацию админки.

- В `src/admin/static/js/ui.js` добавлена делегация событий (CSP-совместимая, без инлайнов):
  - `data-href` на `<tr>` (и аналогичных) → `window.location.assign`
  - `data-confirm` на кнопках/формах → `window.confirm` перед сабмитом/действием (сосуществует с существующим `confirm.js` для delete)
- Табы формы события (`events/form.html`): `<button onclick>` → обычные `<a href="?tab=...">` (disabled-таб «Результат» — `<span class="pv-tab disabled">` без ссылки)
- Удалены **все** инлайновые `on*= ` из 8 шаблонов (events, users, categories, dashboard, analytics, leaderboard). Визуал и поведение сохранены.
- CSP-заголовок не изменён.
- Добавлен CI-гард: `test_no_inline_event_handlers_in_templates` (статический скан `src/admin/templates/**/*.html`, падает с точным списком нарушителей при регрессе).
- Базовый `<script defer src="/static/js/ui.js">` подключён в `base.html` (дубликаты из `_layout_shell.html` и `login.html` убраны).

Все  unit-тесты зелёные (вкл. новый гард + handler'ы событий). ruff/mypy чисто. Синтаксис шаблонов валиден (тесты рендера прошли).

## Изменённые файлы

```
* src/admin/static/js/ui.js                         # +delegation data-href + data-confirm (IIFE, capture)
* src/admin/templates/base.html                     # +<script defer src="/static/js/ui.js"> в <head>
* src/admin/templates/_layout_shell.html            # -дублирующий include ui.js (теперь из base)
* src/admin/templates/login.html                    # -дублирующий include
* src/admin/templates/events/list.html              # tr onclick → data-href (сохранён cursor style)
* src/admin/templates/events/form.html              # tabs: button onclick → a href; confirm button → data-confirm; +css для a/.disabled
* src/admin/templates/dashboard.html                # tr onclick → data-href
* src/admin/templates/users/list.html               # tr onclick → data-href
* src/admin/templates/users/detail.html             # form onsubmit → data-confirm (2 формы block/unblock)
* src/admin/templates/categories/form.html          # div onclick toggle → <label for="is_active"> (нативно, без JS)
* src/admin/templates/leaderboard/list.html         # tr onclick → data-href
* src/admin/templates/analytics/list.html           # tr onclick → data-href
* tests/unit/admin/test_security_headers.py         # +test_no_inline... (guard) + imports; ruff-отформатирован
+ handoff/outbox/TASK-084-report.md                 # этот файл
+ handoff/archive/TASK-084-csp-inline-handlers-break-admin-nav/task.md  # (в финальном коммите)
```

(Также временно брался в работу `handoff/inbox/TASK-084-....in-progress.md` — удалён при archive.)

## Как воспроизвести / запустить

```bash
# 1. Локально (dev)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.override.yml up -d db redis
make admin.create LOGIN=admin PASSWORD=...   # или scripts/create_admin.py
uv run uvicorn src.admin.app:app --reload --port 8000

# 2. Открыть http://localhost:8000/login , войти
# 3. /events — клик по строке таблицы → переход на форму (проверить в консоли: нет CSP violation)
# 4. На форме события: клик по табам «Исходы» / «Результат» (если доступен) — переключение по ?tab=, URL меняется
# 5. Добавить исход(ы) через HTMX (существующее)
# 6. Перейти на «Результат» (когда дедлайн прошёл + >=2 исхода), выбрать, «Зафиксировать» — confirm диалог, сабмит
# 7. Проверить другие списки: dashboard (активные события), /users, /leaderboard, /analytics — клики по строкам работают
# 8. /categories/.../edit — тоггл «Видимость» работает (label)
# 9. В DevTools → Console: 0 ошибок CSP (Refused to execute inline event handler)

# Тесты + гард
uv run pytest tests/unit/admin/test_security_headers.py -q -k "security or inline"
uv run ruff check . && uv run ruff format --check . && uv run mypy src/shared --strict
```

## Что не сделано (если применимо)

Ничего. Все пункты DoD выполнены. Визуальные/поведенческие изменения — нулевые (кроме отсутствия CSP-блокировок).

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-31 — **TASK-084 закрыт (high, blocker v0.1.0)**: CSP `script-src 'self'` больше не ломает навигацию админки. Инлайновые `on*=` удалены из всех шаблонов; делегация `data-href`/`data-confirm` в `ui.js`; `<a href="?tab=...">` для табов формы; CI-гард против регресса. PR #158.
```

## Метрики (опционально)

- Тестов добавлено: +1 (CI-гард, покрывает все 9+ шаблонов рекурсивно)
- Время на выполнение: ~45 мин (анализ + реализация + тесты + ребаза/ PR)
- Затронуто файлов: 13 + handoff
- Регрессов: 0 (все unit зелёные)
