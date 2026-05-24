# Решения — task-028-review

## Новые решения

1. **MCP Google Drive коннектор как backup-канал — упразднён.** Cowork-агент больше **не** делает backup handoff/state/sessions через MCP. Backup делает локальный CC через `make backup` после каждого merge задачи в main (DoD-пункт 5.5 в `CLAUDE.md`). Cowork в своей роли проектировщика читает свежий handoff либо через `git fetch` (через PAT, см. TASK-027 review решение #1), либо через mount к локально-синкнутой Drive-папке.

2. **Cross-platform shell-скрипты через `$OSTYPE` detection — стандарт.** Все будущие утилитарные скрипты в `scripts/` должны учитывать ОС, на которой их запускают: `case "$OSTYPE" in darwin*|linux*) … ;; msys*|cygwin*|win32) … ;; esac`. Default-пути и backend-утилиты выбираются по ОС. Прецедент — `scripts/backup-to-drive.sh` после TASK-028 hotfix.

3. **`rsync --delete` / `robocopy /MIR` обязательны** для backup-операций, которые должны удалять старое в destination. Без этого backup превращается в append-only, и старый мусор накапливается (доказательство — 15 `memory-export (N).md` в Drive от MCP-эры, которые `make backup` вычистил только после фикса).

## Workflow-замечания (зафиксировано)

- **Move-семантика `inbox → archive` должна удалять обе копии:** и оригинальный `TASK-NNN-<slug>.md`, и rename'нутый `TASK-NNN.in-progress.md`. После `make backup --delete` в Drive остаётся только финальный файл в `archive/TASK-NNN-<slug>/task.md`. Сейчас правило implicit (через mermaid-state diagram в `handoff/README.md`). **Если нарушение повторится в TASK-029+** — сделать explicit в `handoff/README.md` секцию «Move-семантика».

## Подтверждённые keep (review TASK-028)

| # | Решение | Обоснование |
|---|---|---|
| 1 | `BB_DRIVE_BACKUP` env override | Linux/нестандартные машины задают путь явно. macOS/Windows имеют дефолты. |
| 2 | Скрипт исключает CLAUDE.md/README.md из backup | Они в git/GitHub, не плодим две версии «источника правды». |
| 3 | `memory-export.md` копируется только если есть | Опциональный артефакт, не у всех cowork-сессий есть. |
| 4 | Defensive `.gitignore` pattern `* [0-9].md` против Drive Finder duplicates | Превентивная мера; не мешает нормальным файлам с цифрами в имени (если они без пробела перед цифрой). |
| 5 | Cowork-агент сам почистил мусор в Drive root (15 memory-export дублей + `.DS_Store`) | Через `mcp__cowork__allow_cowork_file_delete` с VM-path. Стандартный путь для cleanup'a в подключённых папках. |

## Открытые/связанные

- **Часть А TASK-028 (orphan cleanup)** — на машине CC orphan'ов не было, no-op. Cowork удалил у себя локально `handoff/inbox/TASK-026-admin-audit.in-progress.md` (был только на cowork-машине, не в git).
- **DECISIONS.md fraza** (формальная строка для журнала) собрана в этом же merge как часть pre-task cleanup перед TASK-029.
