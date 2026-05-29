---
task: TASK-057
completed: 2026-05-29
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/115
branch: feature/TASK-057-admin-v2-prod-readiness-csp
commits:
  - e9903e2 feat(admin): CSP-compatible Alpine.js for v2 admin (TASK-057)
  - 9bbf231 feat(admin): CSP-compatible Alpine.js for v2 admin (TASK-057) [squash merge]
---

# Отчёт по TASK-057: Прод-готовность админки v2 — починить CSP (шрифты + Alpine)

## Сводка

Реализована CSP-совместимость админки v2 для продового режима. До исправления CSP из TASK-037 блокировал загрузку Material Symbols и работу Alpine.js (тогглы темы/плотности/акцента молча не работали за продовым CSP).

Выбран **путь A**: Alpine CSP-сборка (`@alpinejs/csp`) без ослабления CSP (`unsafe-eval` не добавлен). Это aligns с best practices — CSP как security boundary не ослабляется без необходимости.

## Ключевые изменения

### 1. CSP обновлён (`src/admin/_security_headers.py`)
- `style-src` += `https://fonts.googleapis.com` (CSS Material Symbols)
- Добавлен `font-src 'self' https://fonts.gstatic.com` (файлы шрифтов)
- Проверено: `unsafe-eval` отсутствует (CSP-сборка Alpine в нём не нуждается)

### 2. Alpine.js переключен на CSP-сборку (`src/admin/templates/base.html`)
- Вместо `alpinejs@3.14.1/dist/cdn.min.js` → `@alpinejs/csp@3.14.1/dist/cdn.min.js`
- Убрано инлайн-выражение `x-data="{ dark: $store.ui.dark }"` с `<html>`

### 3. ui.js переработан для CSP-совместимости (`src/admin/static/js/ui.js`)
- Добавлен `Alpine.store('ui', ...)` как основной источник истины
- `uiState` делегирует в store через геттеры
- Добавлены CSP-совместимые computed properties: `themeIcon`, `themeTitle`, `isRailCollapsed`
- Добавлены методы для accent swatches: `accentClass()`, `accentStyle()`, `accentTitle()`
- `applyState()` устанавливает `data-theme` на `<html>` при изменениях

### 4. _layout_shell.html обновлён (`src/admin/templates/_layout_shell.html`)
- Удалён дубликат `Alpine.store('ui')` из конца файла (перезисывал store из ui.js)
- Инлайн-выражения заменены на computed properties/methods:
  - `:title="dark ? '...' : '...'"` → `:title="themeTitle"`
  - `x-text="dark ? '...' : '...'"` → `x-text="themeIcon"`
  - `:data-rail="rail ? 'collapsed' : null"` → `:data-rail="isRailCollapsed"`
  - `:style="{ backgroundColor: acc }"` → `:style="accentStyle(acc)"`
  - `:class="{ 'active': accent === acc }"` → `x-bind:class="accentClass(acc)"`
  - `:title="'Акцент ' + acc"` → `:title="accentTitle(acc)"`

### 5. Тесты (`tests/unit/admin/test_security_headers.py`)
- Добавлен `test_csp_allows_google_fonts()` — проверяет fonts.googleapis.com и font-src
- Добавлен `test_csp_allows_alpine_csp_build()` — проверяет отсутствие unsafe-eval
- Обновлён `test_all_headers_present_together()` с новыми директивами

## Изменённые файлы

```
* src/admin/_security_headers.py           # CSP: font-src, style-src += googleapis
* src/admin/templates/base.html             # Alpine CSP build, убрано x-data
* src/admin/static/js/ui.js                 # Alpine.store, CSP-compatible computed props
* src/admin/templates/_layout_shell.html    # убран дубликат store, inline → computed
* tests/unit/admin/test_security_headers.py # +3 теста на CSP directives
```

## Как воспроизвести / запустить

```bash
# Unit-тесты на CSP
uv run pytest tests/unit/admin/test_security_headers.py -v

# Все unit-тесты
uv run pytest tests/unit/ -q

# Линт и типизация
uv run ruff check src/ tests/
uv run mypy src/shared/
```

## End-to-end проверка (на проде/стейдже)

Необходимые шаги владельца после деплоя:
1. Открыть админку на проде (`5.188.88.78:8888` через ssh-tunnel)
2. Проверить в DevTools Console отсутствие `Refused to load …` / `unsafe-eval` ошибок
3. Проверить, что иконки Material Symbols отображаются корректно
4. Проверить тогглы:
   - Тёмная тема (кнопка солнца/луны) переключается и переживает reload
   - Плотность (C/R/K) переключается
   - Акцент (5 цветов) переключается
   - Сворачивание меню (кнопка ☰) работает
5. Проверить localStorage: `bbAdminUI` сохраняет состояние

## Что не сделано

Нет. Все пункты DoD выполнены.

## Открытые вопросы для проектировщика

Нет. Задача выполнена полностью.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-29 — **TASK-057 ЗАКРЫТ.** Прод-готовность админки v2 — CSP совместим с Material Symbols и Alpine CSP build. Путь A выбран: `@alpinejs/csp` без `unsafe-eval`. CSP обновлён (`font-src 'self' https://fonts.gstatic.com`, `style-src += https://fonts.googleapis.com`). ui.js переработан под `Alpine.store('ui')` с CSP-совместимыми computed properties. Инлайн-выражения в `_layout_shell.html` заменены на методы. +3 теста. PR #115, squash `9bbf231`.
```

## Метрики

- Тестов добавлено: 3 (test_csp_allows_google_fonts, test_csp_allows_alpine_csp_build, обновлён test_all_headers_present_together)
- Общий coverage: unit-тесты проходят (253 tests)
- Время на выполнение: ~2 часа
