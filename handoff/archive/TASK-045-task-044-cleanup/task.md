---
id: TASK-045
created: 2026-05-26
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - handoff/archive/TASK-044.md
  - handoff/inbox/TASK-044-dashboard-counters-semantics.md
  - .github/workflows/handoff-consistency.yml
  - state/DECISIONS.md
priority: high
estimate: S
---

# TASK-045: Cleanup нарушений конвенций TASK-044

## Контекст

При cowork-ревью TASK-044 (2026-05-26) обнаружено 3 нарушения workflow:

1. **Archive convention violated** — задача в архиве лежит как flat-файл `handoff/archive/TASK-044.md`, а должна быть директория `handoff/archive/TASK-044-dashboard-counters-semantics/` с `task.md` внутри. Точно такой же кейс, который мы фиксили в TASK-032 hotfix и под который расширили CI-check (см. [DECISIONS.md](../../state/DECISIONS.md) 2026-05-25 «Archive convention»).

2. **Inbox orphan** — `handoff/inbox/TASK-044-dashboard-counters-semantics.md` остался в inbox параллельно с архивной копией. Blob-хеши идентичны. Локальный агент не сделал `git rm` исходного inbox-файла перед `chore(handoff): archive` коммитом. Та же ошибка преследовала TASK-028..032.

3. **Mixed concerns в feature-PR** — коммит `73cde65` (TASK-044) содержит 3 Windows deploy-скрипта (`scripts/deploy-to-vps-plink.bat`, `scripts/deploy-to-vps.ps1`, `scripts/deploy-vps.bat`), которые не относятся к TASK-044. По прецеденту 2026-05-26 в DECISIONS («Owner direct-commit для прод-инфры») они должны были идти отдельным owner-direct коммитом. **Эту часть переделывать не будем** — git-history не переписываем после push в main. Просто записать как пример «как НЕ делать» в DECISIONS (см. артефакт ниже).

**Бонус-вопрос:** CI workflow `handoff-consistency.yml` сконфигурирован на `push: main` + `pull_request: main` и должен был блочить оба нарушения 1 и 2. Видимо проверка не запустилась или была force-push'нута. Нужно выяснить.

## Цель

Привести `handoff/inbox/` и `handoff/archive/` в консистентное состояние по convention. Расследовать, почему CI-check не сработал. Зафиксировать прецедент в DECISIONS.

## Definition of Done

- [ ] **Archive переименован в директорию:**
  - `git mv handoff/archive/TASK-044.md handoff/archive/TASK-044-dashboard-counters-semantics/task.md`
  - (`mkdir -p` parent сделает сам через mv в новый путь — в git это просто rename)
- [ ] **Inbox orphan удалён:**
  - `git rm handoff/inbox/TASK-044-dashboard-counters-semantics.md`
- [ ] **Расследование CI-check:**
  - Открыть GitHub Actions tab для коммитов `73cde65` и `20365aa` (PR #86 если был, иначе на push)
  - Записать в отчёт: запускался ли workflow `handoff-consistency`, какой был статус (зелёный/красный/skipped), и если зелёный — приложить ссылку на run + краткий анализ почему конкретные проверки не словили нарушения. Это ценная диагностика.
- [ ] Локально прогнать ту же проверку, что в CI-workflow, на текущем main — она должна давать **0 нарушений** после cleanup:
  ```bash
  # mini-репрод проверки
  find handoff/archive -maxdepth 1 -type f -name 'TASK-*.md'   # должно быть пусто
  for d in handoff/archive/TASK-*; do
      id=$(basename "$d" | grep -oE '^TASK-[0-9]+')
      find handoff/inbox -maxdepth 1 -name "${id}*.md"          # должно быть пусто для каждого
  done
  ```
- [ ] `ruff check`, `mypy src/shared` — чисты (тут код не трогается, но запусти для проверки HEAD).
- [ ] PR открыт: `TASK-045: cleanup TASK-044 convention violations + CI check investigation`.
- [ ] Отчёт в `handoff/outbox/TASK-045-report.md` с **обязательной секцией** «CI-check investigation» (см. ниже).
- [ ] **🚨 Move-семантика inbox→archive** для самой TASK-045: после закрытия `git rm handoff/inbox/TASK-045-task-044-cleanup.md` И `git mv` в `archive/TASK-045-task-044-cleanup/task.md`.

## Артефакты

- `D handoff/inbox/TASK-044-dashboard-counters-semantics.md` — удаление orphan
- `R handoff/archive/TASK-044.md → handoff/archive/TASK-044-dashboard-counters-semantics/task.md` — rename в директорию
- `+ handoff/outbox/TASK-045-report.md` — новый отчёт + investigation секция

## Секция «CI-check investigation» в отчёте (обязательно)

Опиши:

1. Запустился ли workflow `handoff-consistency` на коммитах `73cde65` и `20365aa`? (да/нет, ссылки на runs)
2. Был ли он зелёным? Если да — это баг проверки, нужно понять какой. Если красный — кто и как обошёл блокировку?
3. Если красный/skipped — это организационная проблема (force-push, прямой merge в main, missing branch protection). Зафиксируй.
4. **Не правь** сам workflow в рамках TASK-045 — это отдельная задача. Просто описание выводов.

## Подсказки исполнителю

- Эта задача — чисто handoff-housekeeping, без кода. Не должно быть никаких изменений в `src/` или `tests/`.
- **Не** меняй `state/DECISIONS.md` — cowork обновит сам после ревью отчёта.
- **Не** трогай git-history существующих коммитов (`73cde65`, `20365aa`) — пушим cleanup как отдельный коммит сверху. Conventional commit message: `chore(handoff): TASK-045 cleanup — fix TASK-044 archive convention + inbox orphan`.
- Когда сам TASK-045 будешь архивировать — сделай **правильно**: директория `archive/TASK-045-task-044-cleanup/`, `task.md` внутри, `git rm` inbox-файла. Покажи делом, что инвариант понятен.
