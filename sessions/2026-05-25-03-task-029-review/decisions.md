# Решения — task-029-review

## Новое решение

1. **Explicit move-семантика inbox → archive в `handoff/README.md`.** Триггер — два случая подряд workflow violation (TASK-028 и TASK-029): CC оставлял в inbox и оригинал, и in-progress версию задачи после move в archive. Новая подсекция «Move-семантика inbox → archive» прямо предписывает: **(а)** исходный `TASK-NNN-<slug>.md` удалить через `git rm`; **(б)** rename `TASK-NNN.in-progress.md` удалить через `git rm`; **(в)** остаётся только `archive/TASK-NNN-<slug>/task.md`. Перед коммитом `chore(handoff): archive TASK-NNN` обязательная проверка `ls handoff/inbox/ | grep TASK-NNN`.

## Подтверждённые keep (review TASK-029)

| # | Решение | Обоснование |
|---|---|---|
| 1 | Sleep-loop вместо cron/dcron | Проще, без `apk add`, dev-friendly (видно в `docker logs db-backup`). Минор drift приемлем для MVP. |
| 2 | `pg_dump --no-owner --clean --if-exists` + gzip | Стандартные флаги для self-contained restorable dump. gzip ~5-10× compression на текстовом дампе. |
| 3 | Named volume `bb-db-backups` вместо bind-mount | Изоляция от хоста, persistent, не загромождает рабочую копию репо. |
| 4 | Retention 14 дней через `find -mtime +14 -delete` после успешного pg_dump | Защита от потери последнего рабочего бэкапа, если pg_dump упал. |
| 5 | `make prod.backup.now` через `run --rm db-backup` | Не мешает scheduled-loop в основном контейнере; `--rm` чистит за собой. |
| 6 | `make prod.backup.restore` с обязательным `read ans; [ "$$ans" = "RESTORE" ]` | По паттерну `make nuke`/`make rollback.all` — критические данные не теряются по случайному `make`. |
| 7 | Логирование `[backup-error]` префиксом | Простое — оператор grep'нет в docker logs. Полноценный alerting за MVP. |

## Hotfix-правки от cowork-агента

1. **Makefile `prod.backup.restore`:** `exec -T db` → `exec -T db-backup` для gunzip-стороны pipe'a. БЛОКЕР (volume только у db-backup). Без фикса restore физически не работал.
2. **Inbox cleanup:** `git rm handoff/inbox/TASK-029-pg-dump-backup.md` + `git rm handoff/inbox/TASK-029.in-progress.md`.
3. **handoff/README.md:** новая подсекция «Move-семантика inbox → archive» (см. новое решение №1 выше).
4. **`make backup`** через cowork-канал — Drive обновлён.

## Тех-долг (зафиксировано)

- **Sleep-loop drift** — если станет проблемой, переписать на точный sleep до следующего 02:30 UTC.
- **`make prod.backup.now` в Deploy README** — обязательный шаг после `make prod.up` (см. TASK-031 inbox).
- **Smoke-test contract** — `handoff/templates/report.md` должен требовать прогон опасных путей (restore, rollback, delete). Отложено — добавим, если CC ещё раз поставит блокер из-за неполного теста.
