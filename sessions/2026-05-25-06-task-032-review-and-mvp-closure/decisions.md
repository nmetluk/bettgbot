# Решения — task-032-review + MVP closure

## Новые решения

1. **Archive convention: ВСЕГДА директория `handoff/archive/TASK-NNN-<slug>/`** с `task.md`/`report.md`/`amendments/` внутри. Файл `TASK-NNN.md` прямо в `handoff/archive/` — нарушение, блокируется CI-check'ом. Convention неявно была в `handoff/README.md` секция «Где история» (с примером структуры), но без явного запрета на файл-вариант. CC в TASK-032 нарушил convention, обойдя при этом первую версию CI-check'a. Теперь правило **enforced**.

2. **CI-check `handoff-consistency` расширен:** добавлены две проверки.
   - **(A) Archive format:** glob `handoff/archive/TASK-*.md` — если что-то нашлось как файл, fail с explicit-сообщением «должно быть директорией».
   - **(B) Inbox vs archive consistency (расширено):** собирает archived TASK-IDs из обоих источников (директории через `find -type d` + orphan-файлы через `find -type f`), затем проверяет, что в `handoff/inbox/` нет соответствующих `TASK-NNN*` для всех найденных IDs. До этого фикса итерация только по директориям пропускала TASK-NNN-файлы.

## Подтверждённые keep (review TASK-032)

| # | Решение | Обоснование |
|---|---|---|
| 1 | `BB_COMPOSE_ARGS` env для dev/prod переключения | Один скрипт работает в любом compose-окружении. Дефолт — prod. |
| 2 | retry-loop 12×5s для `/healthz` | Покрывает миграции + uvicorn startup на холодном стенде (~30-40s). |
| 3 | `running` или `healthy` принимаются для service state | `db-backup` не имеет healthcheck (state остаётся `running`); сервисы с healthcheck могут быть `healthy`. Оба принимаются. |
| 4 | grep вместо jq для парсинга `ps --format json` | Хрупко, но работает на стандартном compose v2 output. На VPS jq обычно установлен, но fallback без него — приемлемо. |
| 5 | `alembic current` через grep '^[a-f0-9]+' | Берёт первую hex-строку из output. Корректно для типового `<revision_id> (head)`. |

## Hotfix-правки от cowork-агента

1. **Archive convention:** `mkdir handoff/archive/TASK-032-smoke-tests && git mv handoff/archive/TASK-032.md handoff/archive/TASK-032-smoke-tests/task.md`.
2. **Inbox cleanup:** `git rm handoff/inbox/TASK-032-smoke-tests.md` (5-й случай move-violation подряд).
3. **CI-check расширение:** два новых блока проверок (см. новое решение №2 выше).
4. **`make backup`** через cowork-канал — Drive синкнут после финального состояния.

## Закрытие Этапа 4 + MVP

| Задача | Реализация | Cowork hotfix |
|---|---|---|
| TASK-027 | Prod compose, Dockerfile.bot/web, nginx, certbot | nginx envsubst + Makefile override + alembic race |
| TASK-028 | Handoff backup workflow (rsync/robocopy + `make backup`) | Cross-platform скрипт + inbox cleanup |
| TASK-029 | pg_dump cron-бэкап + retention 14 дней | Restore-баг (`exec -T db` → `exec -T db-backup`) + inbox cleanup |
| TASK-030 | Structured JSON logging | Inbox cleanup + усиление move-правила в template |
| TASK-031 | Deploy README + admin-bootstrap.conf | Certbot entrypoint (`--entrypoint=""`) + inbox cleanup + CI-check |
| TASK-032 | Smoke-тесты | Archive convention fix + inbox cleanup + CI-check расширение |

**Hotfix rate Этапа 4 = 100%** (6 из 6 задач). Это паттерн качества CC, который должен учитываться в следующих больших итерациях. Mitigations уже в коде: 🚨-DoD в template, explicit-секции в README, CI-check (теперь полноценный после TASK-032 фикса). Если в пост-MVP цикле rate останется 100% — рассмотреть branch protection (требует GitHub Pro для private repo).

## Тех-долг

- **`handoff/templates/report.md`** — добавить требование «обязательный прогон новой функциональности на dev-stack». В последних 2 задачах (TASK-031, TASK-032) CC признал, что не тестировал реально. Для TASK-032 (smoke-тесты) это особенно ironично.
- **`scripts/smoke_test.sh`** — улучшить парсинг: использовать `jq` если установлен, fallback на grep. Минор.
- **Branch protection на main** — отложен (требует GitHub Pro для private). Митигация — CI-check + дисциплина.

## 🎉 Итог

Этап 4 закрыт. **MVP завершён.** Проект готов к выкатке на VPS по `docs/07-deployment.md`. См. `brief.md` секция «Что дальше — за MVP» для пост-MVP backlog'a.
