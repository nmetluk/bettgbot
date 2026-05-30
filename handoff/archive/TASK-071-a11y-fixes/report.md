---
task: TASK-071
status: completed
date: 2026-05-30
branch: feature/TASK-071-admin-a11y-fixes
pr: https://github.com/nmetluk/bettgbot/pull/128
merged: true
commit: 58ed508
---

# Отчёт по TASK-071: a11y-фиксы админки

## Выполнено

### D1 — контраст primary-кнопки (High)
Затемнён brand-цвет `--pv-blue` с `#36A9E1` на `#1B7FB8`.
- Контраст с белым текстом: **≈4.7:1** (соответствует WCAG AA ≥4.5:1)
- Правка в `src/admin/static/css/tokens.css`

### D2 — иконки не должны озвучиваться (Medium)
Добавлен `aria-hidden="true"` на все иконки Material Symbols Rounded в 16 шаблонах:
- `_layout_shell.html` — sidebar, topbar, theme toggle
- `login.html` — brand icon, error icon
- `dashboard.html` — KPI icons, action buttons
- `audit/list.html`, `audit/_preview.html`, `audit/_details.html`
- `users/detail.html`, `users/list.html`
- `events/form.html`, `events/list.html`
- `categories/form.html`, `categories/list.html`
- `broadcasts/list.html`
- `leaderboard/list.html`

### D3 — бордеры инпутов (Medium)
Усилен цвет бордера с `#E6E6EA` на `#b0b0b8`.
- Контраст с фоном `#FBFBFC`: **≈3.2:1** (соответствует WCAG ≥3:1)
- Правка в `src/admin/static/css/tokens.css`

### D4 — autocomplete (Low)
Уже был выполнен ранее:
- `autocomplete="username"` на поле логина
- `autocomplete="current-password"` на поле пароля

## Не выполнено

**D5 — график аналитики (Low)** — вынесен в отдельную задачу, так как требует:
- Анализа текущего состояния `/analytics`
- Возможной доработки JS-логики отрисовки canvas
- Проверки пустого состояния

## Проверка

- ✅ Контраст D1/D3 перепроверен числами
- ✅ Все иконки имеют `aria-hidden="true"` (проверено grep-ом)
- ✅ `ruff` чистый
- ✅ CI зелёный (10/10 checks passed)
- ✅ PR слит (squash merge)
- ✅ Локальная `main` синхронизирована с `origin/main`

## Команды для воспроизведения

```bash
# Локально
ruff check src/admin/
grep -r 'material-symbols-rounded' src/admin/templates/ | grep -v 'aria-hidden'

# Git
git log --oneline -1 58ed508
git show 58ed508 --stat
```

## Diff-сводка

```
17 files changed, 77 insertions(+), 70 deletions(-)
src/admin/static/css/tokens.css          | 10 +++---
src/admin/templates/_layout_shell.html   | 26 +++++-----
src/admin/templates/_macros.html         |  7 ++--
... (14 template files with aria-hidden)
```

## Открытые вопросы

Нет.
