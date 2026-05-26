---
task: TASK-045
completed: 2026-05-26
---

# TASK-045: Cleanup нарушений конвенций TASK-044

## Что сделано

1. **Archive convention fixed:**
   - `handoff/archive/TASK-044.md` → `handoff/archive/TASK-044-dashboard-counters-semantics/task.md`

2. **Inbox orphan removed:**
   - `git rm handoff/inbox/TASK-044-dashboard-counters-semantics.md`

3. **Расследование CI-check:**
   - CI запускался на PR #86 — SUCCESS (archive/TASK-044.md ещё не существовало)
   - CI запускался на push 20365aa — **FAILURE** (нарушения были найдены!)
   - Run: https://github.com/nmetluk/bettgbot/actions/runs/26472372914
   - Коммит 20365aa был запушен **напрямую в main**, обойдя branch protection
   - **Вывод:** Проверка работает корректно, проблема в organisational (прямой push в main)

## CI-check investigation (подробно)

**1. Запустился ли workflow?**
- Да, на обоих коммитах (PR #86 и push 20365aa)

**2. Был ли он зелёным?**
- На PR #86: SUCCESS — нарушений ещё не было (archive/TASK-044.md не создан)
- На push 20365aa: **FAILURE** — CI нашёл violations!

**3. Почему нарушение попало в main?**
- Коммит 20365aa был запушен **напрямую в main** (не через PR)
- Это обошло branch protection, которая блокирует только PR-merge с красным CI
- Организационная проблема: нужен запрет на прямой push в main или enable branch protection для push

**4. Не исправлять workflow?**
- Верно, workflow работает корректно. Проблема не в коде проверки, а в процессах.

## Что не сделано

Ничего — задача выполнена полностью.

## Открытые вопросы

Нет.

## Команды для воспроизведения

```bash
# Локальная проверка (из задачи)
find handoff/archive -maxdepth 1 -type f -name 'TASK-*.md'   # должно быть пусто
for d in handoff/archive/TASK-*; do
    id=$(basename "$d" | grep -oE '^TASK-[0-9]+')
    find handoff/inbox -maxdepth 1 -name "${id}*.md"          # должно быть пусто
done
```

## Diff-сводка

- `R handoff/archive/TASK-044.md → handoff/archive/TASK-044-dashboard-counters-semantics/task.md`
- `D handoff/inbox/TASK-044-dashboard-counters-semantics.md`

## Артефакты

- PR: https://github.com/nmetluk/bettgbot/pull/87
- Squash-коммит: `TASK-045: cleanup TASK-044 convention violations`
- CI run failure: https://github.com/nmetluk/bettgbot/actions/runs/26472372914
