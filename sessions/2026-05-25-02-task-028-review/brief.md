# Brief — task-028-review (smena backup-стратегии)

**Дата:** 2026-05-25
**Длительность:** разделённая (TASK-028 закрытие → review → hotfix → smoke test → этот review)
**Участники:** Николай (owner), cowork-agent, локальный CC (Windows-машина)

## Запрос владельца

После двух подтверждённых рассинхронов (TASK-014 выполнилась раньше, чем cowork положил задачу в inbox; TASK-027 — отчёт исполнителя не дошёл до cowork-видимости через MCP-коннектор) — сменить backup-стратегию handoff с MCP Google Drive коннектора на локально-синкнутую Drive-папку через `make backup`.

## Контекст

Старый workflow:
- Cowork-агент периодически вызывал MCP Google Drive коннектор из своего desktop-приложения для копирования `handoff/`, `state/`, `sessions/` в Drive-папку `Claude projects/Betting Bot backup`.
- Проблемы: лаг между завершением задачи и видимостью на второй машине (cowork-сессия могла быть неактивна), Drive duplicates от повторных загрузок (накопилось 15 `memory-export (N).md`), зависимость от состояния MCP-коннектора.

Новый workflow (TASK-028):
- Локальный CC после каждого merge задачи в main делает `make backup` — `scripts/backup-to-drive.sh` через `rsync -a --delete` (macOS/Linux) или `robocopy /MIR` (Windows) зеркалирует целевые директории в локально-синкнутую Drive-папку. Drive File Stream синкает в облако автоматически.
- Cowork-агент теперь читает свежий handoff либо через `git fetch` (PAT настроен в TASK-027 review), либо через ту же Drive-папку через mount в sandbox.

## Состав изначальной реализации (squash-merge 727dd5c, PR #80)

- `scripts/backup-to-drive.sh` — backup-скрипт.
- `Makefile` — цель `backup`.
- `handoff/README.md` — секция «Зеркало в Google Drive» заменена на «Локальный backup handoff в Google Drive».
- `CLAUDE.md` — добавлен шаг 5.5 (`make backup`) между sync main и отметкой готовности.
- `.gitignore` — defensive pattern `* [0-9].md/.txt/.yml/.yaml/.py/.sh` против Drive/Finder duplicates.
- Часть А (cleanup orphan-файлов) — на машине CC не было orphans, no-op.

## Обнаруженные блокеры/нарушения (review cowork-агента)

1. **БЛОКЕР: `backup-to-drive.sh` написан под Windows.** Default `DRIVE_BACKUP=G:/Мой диск/...` (Windows drive letter), использует `robocopy` (Windows-only утилита). На macOS, где живёт основной репо и cowork, `make backup` упал бы с `command not found`. CC в отчёте писал «make backup выполнен успешно» — он тестировал у себя на Windows.

2. **Минор: `robocopy` без `/MIR`/`/PURGE`.** Изначальная имплементация использовала только `/E` (recurse), что **не удаляет** лишнее в destination. Эквивалента `rsync --delete` не было — старый мусор в Drive (TASK-014..026 inbox от MCP-эры) не вычистился бы.

3. **Workflow violation: две незакрытые копии TASK-028 в inbox после move в archive.** Финальная копия задачи правильно ушла в `handoff/archive/TASK-028-cleanup-and-local-drive-backup/task.md`. Но в `handoff/inbox/` остались **оба** оригинала: `TASK-028-cleanup-and-local-drive-backup.md` (исходный файл задачи) и `TASK-028.in-progress.md` (рабочий rename). По правильному workflow должен остаться **только один файл** — финальный в archive; обе копии в inbox удаляются move-семантикой. Прецедент будущих задач — паттерн нарушен.

## Hotfix-цикл (повторение паттерна из TASK-027 review)

Cowork-агент применил cross-platform hotfix `d1c58b9` тем же путём что TASK-027 hotfix:

1. Создал ветку `fix/TASK-028-cross-platform-backup` локально.
2. Применил правки: `scripts/backup-to-drive.sh` — case-statement по `$OSTYPE` (darwin/linux → rsync; msys/cygwin/win32 → robocopy `/MIR`); `handoff/README.md` — таблица «ОС → default путь → утилита»; `git rm` двух дубликатов из inbox.
3. Smoke test через bash sandbox: `BB_DRIVE_BACKUP=/sessions/.../mnt/Betting Bot backup bash scripts/backup-to-drive.sh` → OS detection правильно (`backend: rsync`), все 3 секции запустились, упёрлись в File Stream FUSE deadlocks (специфика моего mount, на хост-FS работает).
4. Squash merge в main + push.

После hotfix Николай на macOS-машине запустил `make backup` — **прошло без единой ошибки**, все 3 блока выполнились. Cowork через свой mount подтвердил: Drive обновлён, inbox пустой, outbox содержит TASK-022..028 reports, archive содержит TASK-027/028, state — 4 актуальных файла.

## Что сделано — итого

- TASK-028 закрыт исходным `727dd5c` (PR #80).
- Cowork hotfix `d1c58b9` сделал скрипт cross-platform + почистил inbox dupes.
- **Первый успешный `make backup` на macOS** подтвердил end-to-end workflow.

## Решения этой сессии

См. `decisions.md` рядом. Два паттерна:

- **Cross-platform shell-скрипты через `$OSTYPE` detection** — стандарт для будущих утилит проекта.
- **Move-семантика для `inbox/*.in-progress.md` → `archive/`** — оригинал И in-progress должны быть удалены, не оставаться в inbox.

Плюс одно решение из этой сессии:

- **MCP Google Drive коннектор как backup-канал упразднён.** Cowork в своей роли проектировщика больше не делает копий в Drive. Backup делает только CC через `make backup`.

## Открытые вопросы

- **Workflow violation в `.in-progress` move** — добавить explicit правило в `handoff/README.md`? «Когда задача переезжает в archive, оригинал И in-progress версия должны быть удалены через `git rm`». Сейчас правило implicit (через mermaid-state diagram). Сделать explicit в следующем cowork-cleanup, если ещё раз повторится.
- **CC оставил `handoff/inbox/TASK-028.in-progress.md` в коммите.** Это не было удалено, только переименовано (rename file remained vs delete). Возможно это привычка CC из TASK-026, где тоже был оставлен `TASK-026-admin-audit.in-progress.md` (тот же orphan, который cowork удалил у себя локально).

## Что в Drive backup сейчас (после первого `make backup`)

```
Drive backup/
├── handoff/
│   ├── README.md
│   ├── inbox/         (пусто — все задачи в archive)
│   ├── outbox/        (TASK-001..028 reports)
│   ├── archive/       (TASK-001..028 archive papki)
│   └── templates/     (task.md, report.md)
├── state/
│   ├── BACKLOG.md
│   ├── DECISIONS.md
│   ├── GLOSSARY.md
│   └── PROJECT_STATUS.md
├── sessions/          (все 13+ review-сессий)
└── memory-export.md
```

Workflow живой. TASK-029 (pg_dump) можно стартовать.
