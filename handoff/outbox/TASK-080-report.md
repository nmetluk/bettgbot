---
task: TASK-080
completed: 2026-05-30
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/147
branch: feature/TASK-080-handoff-consistency-guard-transient-suffixes
commits:
  - 5c5b018 feat(ci): handoff-consistency guards transient inbox suffixes on main (TASK-080)
  - <archive-sha> chore(handoff): archive TASK-080 + report
---
# Отчёт по TASK-080: handoff-consistency должен краснеть на transient-суффиксах в inbox на main

## Сводка

Реализована новая проверка (5) в CI `handoff-consistency.yml`:

- Transient-суффиксы (`.in-progress.md`, `.blocked.md`) в `handoff/inbox/` на `main` теперь вызывают fail с ясным сообщением.
- Проверка активна только на main (по `GITHUB_REF` / push event) — на feature-ветках transients легитимны (часть ЖЦ задачи, как .in-progress во время работы).
- Обновлены комментарии в yml.
- Опционально: добавлено явное правило в `handoff/README.md` (секция move-семантики) — «Transient-суффиксы на main запрещены».
- Локальная симуляция (как в DoD):
  - Чистый inbox на main → ✓ зелено.
  - Искусственный `TASK-999.in-progress.md` → ❌ красное сообщение + violations (файл удалён после теста).
- Полный ruff / pytest / mypy — без изменений в коде (только yml + md).

Это закрывает дыру, через которую transient-состояния (как TASK-076.in-progress) могли утекать в main после merge.

## Изменённые файлы

```
* .github/workflows/handoff-consistency.yml   # + check (5) + header comments
* handoff/README.md                           # (опц.) правило про transients на main
R  handoff/inbox/TASK-080-....md -> handoff/archive/TASK-080-.../task.md
+ handoff/outbox/TASK-080-report.md
```

## Как воспроизвести / запустить

```bash
# локально (симуляция проверки, как в DoD)
# 1. чистый inbox
ls handoff/inbox/TASK-*.in-progress.md handoff/inbox/TASK-*.blocked.md || echo "✓ чисто"

# 2. искусственный transient → должен "провалить"
touch handoff/inbox/TASK-999-test.in-progress.md
# (запустить логику проверки из yml — см. отчёт или yml)
rm handoff/inbox/TASK-999-test.in-progress.md

# В CI: пуш в main или PR в main — handoff-consistency job (только на main-ветке краснит на transients)
```

## Что не сделано (если применимо)

- Не менял move-семантику или другие инварианты (только новая проверка).
- Не делал "код влит ⇒ задача заархивирована" (CI не знает merge-статус, как указано в вне-скоуп).
- Не трогал другие workflow.

## Открытые вопросы для проектировщика

Нет. Проверка учитывает, что CI запускается и на PR-ветках (где transient легитимен), и только на main даёт red.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — TASK-080: handoff-consistency теперь краснит на transient .in-progress/.blocked в inbox на main (PR #147)
```

## Метрики (опционально)

- Тестов: + локальная симуляция green/red (в отчёте).
- Время: ~25 мин (XS как оценено).
- Параллельно с TASK-079 (non-overlapping files).