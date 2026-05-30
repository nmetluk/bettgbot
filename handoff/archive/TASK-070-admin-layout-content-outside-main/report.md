---
task: TASK-070
completed: 2026-05-30
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/127
branch: feature/TASK-070-admin-layout-content-outside-main
commits:
  - 9e3d763 fix(admin): layout content inside <main> via template inheritance (TASK-070)
---

# Отчёт по TASK-070: BLOCKER — контент всех страниц админки рендерится НИЖЕ шелла (пустой <main>)

## Сводка

**Корень проблемы:** `{% block pv_content %}` объявлялся в теле страницы после `{% include "_layout_shell.html" %}`. В Jinja блоки внутри `{% include %}` не переопределяются родителем — подключённый шелл рендерил свой `{% block pv_content %}` пустым, а контент страницы рендерился инлайн после include, вне сетки.

**Решение:** Перешли на нормальное наследование шаблонов:
- `_layout_shell.html` теперь `{% extends "base.html" %}` и оборачивает грид в `{% block body %}`
- `ui.js` перенесён в `{% block scripts_extra %}` (грузится один раз)
- Все 12 авторизованных шаблонов теперь `{% extends "_layout_shell.html" %}`, `{% block pv_content %}` идёт напрямую

**Проверка:**
```bash
git grep 'include "_layout_shell.html"' src/admin/templates/  # → пусто ✓
git grep 'extends "base.html"' src/admin/templates/          # → только _layout_shell.html и login.html ✓
```

## Изменённые файлы

```
* src/admin/templates/_layout_shell.html       # extends base + block body + scripts_extra
* src/admin/templates/dashboard.html           # extends _layout_shell, убраны body/include
* src/admin/templates/categories/list.html     # extends _layout_shell, убраны body/include
* src/admin/templates/categories/form.html     # extends _layout_shell, убраны body/include
* src/admin/templates/events/list.html         # extends _layout_shell, убраны body/include
* src/admin/templates/events/form.html         # extends _layout_shell, убраны body/include
* src/admin/templates/users/list.html          # extends _layout_shell, убраны body/include
* src/admin/templates/users/detail.html        # extends _layout_shell, убраны body/include
* src/admin/templates/leaderboard/list.html    # extends _layout_shell, убраны body/include
* src/admin/templates/analytics/list.html      # extends _layout_shell, убраны body/include
* src/admin/templates/audit/list.html          # extends _layout_shell, убраны body/include
* src/admin/templates/broadcasts/list.html      # extends _layout_shell, убраны body/include
* src/admin/templates/broadcasts/form.html      # extends _layout_shell, убраны body/include
```

## Как воспроизвести / запустить

```bash
# Проверить что refactoring корректен
git grep 'include "_layout_shell.html"' src/admin/templates/
git grep 'extends "base.html"' src/admin/templates/

# Прогнать тесты
uv run pytest tests/unit/admin/ -q
```

## Что не сделано

Нет. Все пункты DoD выполнены.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — **TASK-070 ЗАКРЫТ:** фикс layout админки через наследование шаблонов. `_layout_shell.html` теперь extends "base.html", все 12 авторизованных страниц extend "_layout_shell". Контент рендерится внутри `<main>`, а не ниже шелла. PR #127.
```

## Метрики

- Шаблонов обновлено: 13 (_layout_shell + 12 страниц)
- Строк удалено: 51 (убрана обёртка `{% block body %}` + include в каждой странице)
- Строк добавлено: 19 (extends + scripts_extra в _layout_shell)
- Время на выполнение: ~1 час
