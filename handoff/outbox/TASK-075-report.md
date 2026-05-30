---
task: TASK-075
completed: 2026-05-30
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/142
branch: feature/TASK-075-event-form-padding
commits:
  - 4906fda fix(admin): unify event form card padding (use card-body + spacing tokens)
---

# Отчёт по TASK-075: разнобой отступов на форме события

## Сводка

Унифицированы отступы на форме события (`events/form.html`):
- Карточки «Данные события», «Состояние», «Итоговый исход» обёрнуты в `.pv-card-body`
  для консистентного внутреннего padding (20px через `var(--pv-s-20)`)
- Хардкод px заменён на spacing токены:
  - `gap: 10px` → `var(--pv-s-10)`
  - `gap: 8px` → `var(--pv-s-8)`
  - `margin-top: 10px` → `var(--pv-s-10)`
  - `.pv-tab` padding: `10px 16px` → `var(--pv-s-10) var(--pv-s-16)`
  - `.result-opt` padding: `12px 16px` → `var(--pv-s-12) var(--pv-s-16)`
- Инлайн padding из `.pv-card-body` удалён (используется default из `app.css`)

## Изменённые файлы

```
* src/admin/templates/events/form.html
```

## Как воспроизвести / запустить

```bash
# Визуальная проверка: открыть форму события (новое и существующее)
make admin
# Перейти на /events/new и /events/{id}?tab=data,outcomes,result
```

## Что не сделано

Ничего — все требования задачи выполнены.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — TASK-075: унифицированы отступы формы события (PR #142)
```
