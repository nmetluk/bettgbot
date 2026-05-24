# TASK-028: Cleanup orphan handoff/sessions + смена backup-стратегии — отчёт

## Что сделано

- `.gitignore` — defensive pattern для Drive/Finder duplicates (`* [0-9].md` и т.п.)
- `scripts/backup-to-drive.sh` — robocopy-based зеркалирование handoff/state/sessions в локальную Drive-папку
- `Makefile` — добавлена цель `backup` (вызывает скрипт)
- `handoff/README.md` — обновлена секция про backup (MCP-коннектор упразднён)
- `CLAUDE.md` — добавлен шаг 5.5 `make backup` после PR merge

## Коммиты

- `9597d7e` chore(workflow): TASK-028 cleanup orphans + switch handoff backup to local Drive folder

## Часть А — Orphan-файлы

Проверено — на локальной машине orphan-файлов нет:
- `handoff/inbox/TASK-026-admin-audit.in-progress.md` — отсутствует
- `sessions/2026-05-24-12-task-025-review/brief 2.md` — отсутствует
- `sessions/2026-05-24-12-task-025-review/decisions 2.md` — отсутствует

## Часть Б — Defensive gitignore

Добавлен паттерн `* [0-9].md` (и .txt, .yml, .yaml, .py, .sh) для отлова Drive/Finder duplicates. Проверка: `touch "test 2.md" && git status` — пусто.

## Часть В — backup скрипт

`scripts/backup-to-drive.sh` использует robocopy (Windows) вместо rsync. Путь по умолчанию: `G:/Мой диск/Claude projects/Betting Bot backup`. Переопределяется через `BB_DRIVE_BACKUP`.

## Часть Г — Makefile

Цель `backup` добавлена в `.PHONY`. `make help` показывает её.

## Часть Д — handoff/README.md

Секция "Зеркало в Google Drive" заменена на "Локальный backup handoff в Google Drive" с описанием нового процесса.

## Часть Е — CLAUDE.md

Добавлен шаг 5.5 между merge и отметкой готовности. Также обновлён подпункт 5 в "Push обязателен".

## Часть Ж — Тестирование

- `make backup` выполнен успешно
- Drive-папка содержит: handoff/ (inbox, archive, outbox, templates, README.md), state/ (*.md), sessions/
- `make help` показывает `backup`

## Фраза для DECISIONS.md

> **2026-05-25 — TASK-028**: handoff backup перемещён с MCP-коннектора на локальный `make backup` (robocopy в Drive-папку). Причина: лаг между merge и видимостью на второй машине + Drive duplicates. См. `handoff/README.md` секция «Локальный backup handoff».

## PR

https://github.com/nmetluk/bettgbot/pull/80
