# Brief — task-029-review (pg_dump бэкап БД)

**Дата:** 2026-05-25
**Длительность:** короткая (TASK-029 закрытие → review → hotfix)
**Участники:** Николай (owner), cowork-agent, локальный CC

## Запрос владельца

«29 завершена проверяй». Стандартная приёмка задачи cowork-агентом.

## Что было сделано в TASK-029

CC реализовал (squash `1e2d540`, PR #81; archive+report `ef45b0d`):

- **Новый сервис `db-backup`** в `infra/docker-compose.prod.yml` на образе `postgres:16-alpine`. Sleep-loop проверяет каждые 5 минут текущее UTC-время; когда достигнута метка 02:30 — запускает `pg_dump --no-owner --clean --if-exists | gzip > /backups/bettgbot-<iso8601>.sql.gz`, чистит старое через `find -mtime +14 -delete` (только если pg_dump успешен), логирует ошибку с префиксом `[backup-error]` и спит 86400 секунд до следующего цикла.
- **Named volume `bb-db-backups`** объявлен в `volumes:` секции prod.yml. Mount у db-backup как `/backups`.
- **3 Makefile-цели**: `prod.backup.now` (через `run --rm db-backup`), `prod.backup.ls` (через `exec db-backup ls`), `prod.backup.restore FILE=...` с подтверждением `RESTORE`.

## Что cowork-агент нашёл в review

### Блокер

**`prod.backup.restore` сломан.** Makefile делает:

```makefile
$(PROD_COMPOSE) exec -T db sh -c 'gunzip -c /backups/$(FILE)' | $(PROD_COMPOSE) exec -T db sh -c 'psql ...'
```

Левая часть pipe'a — `exec -T db`, но **у сервиса `db` нет volume `bb-db-backups` mounted** (он только у `db-backup`). gunzip упадёт на `file not found`. То есть restore — единственная критически важная операция backup-системы — физически не работала бы в первой реальной аварии.

Fix: заменить левую `exec -T db` на `exec -T db-backup`. Правая остаётся `exec -T db` (psql применяет дамп к рабочей базе). Применено в hotfix-коммите этого же pre-task cleanup'a.

### Workflow-нарушения

**Две копии TASK-029 в inbox после move в archive.** В main замёрджились:

- `handoff/inbox/TASK-029-pg-dump-backup.md` (исходный файл задачи cowork'a)
- `handoff/inbox/TASK-029.in-progress.md` (rename CC при взятии в работу)
- `handoff/archive/TASK-029-pg-dump-backup/task.md` (финальная архивная копия)

По правильному workflow обе копии в inbox должны быть удалены через `git rm`, остаётся только archive. **Это второй случай подряд** (был тот же баг в TASK-028) — пора зафиксировать explicit-правило в `handoff/README.md`, что и сделано в этом cleanup'e (новая подсекция «Move-семантика inbox → archive»).

**CC не запустил `make backup`** — нарушение DoD-пункта 5.5 в `CLAUDE.md`. Drive backup-папка осталась со старым inbox-содержимым (стартовая задача TASK-029, без archive). Cowork-агент сам сделал `make backup` через свой sandbox-канал в составе этого cleanup'a (File Stream сейчас разморожен, rsync через FUSE проходит).

### Минор (не блокер, не правил в hotfix)

**Sleep-loop scheduler не оптимален.** Если контейнер стартанёт после 02:30 UTC (например в 05:00), первая итерация loop сразу попадёт в `current_time >= target_time`, запустит backup, затем `sleep 86400` → следующий backup в 05:00 следующего дня, не в 02:30. Drift сохраняется на каждом restart-cycle. Не критично — backup делается, просто не в плановое время.

Также: до первого `sleep 86400` контейнер каждые 300 секунд делает date+compare → лёгкий поллинг. На MVP-нагрузке незначим.

**Mitigation для prod-deploy:** в Deploy README (TASK-031) явно прописать «после `make prod.up` сразу запусти `make prod.backup.now`» — это создаст первый бэкап независимо от времени старта контейнера.

**Smoke-тест в отчёте неполный.** CC прогнал только `make prod.backup.now` + `make prod.backup.ls`. **`make prod.backup.restore` не тестировал** — иначе обнаружил бы блокер сам. Замечание для будущих задач: smoke-тест должен покрывать **полный путь** новой функциональности, включая опасные пути (restore — потенциально data-destructive).

## Hotfix-цикл (третий подряд: TASK-027 → TASK-028 → TASK-029)

Cowork-агент применил hotfix в составе того же cleanup-merge:

- Makefile: `db` → `db-backup` для gunzip-стороны restore.
- `git rm` двух копий TASK-029 из inbox.
- `handoff/README.md`: новая подсекция «Move-семантика inbox → archive» с explicit-правилом.
- `make backup` через cowork-канал → Drive обновлён.

Локальный squash в main (api.github.com по-прежнему заблокирован прокси sandbox'a). Это уже устоявшийся паттерн (см. DECISIONS 2026-05-25 «Локальный squash + git push в main как фоллбэк»).

## Что сделано — итого

- TASK-029 закрыт исходным `1e2d540` + archive `ef45b0d` (PR #81).
- Cowork hotfix-cleanup поправил restore-баг + workflow violation + explicit move-правило + sync Drive + публикация TASK-030.
- Workflow живой. Готово к TASK-030 (structured JSON logging).

## Решения этой сессии

См. `decisions.md` рядом. Одно новое решение:

- **Explicit move-семантика inbox→archive** — переходит из implicit/неявной нормы в записанное правило в `handoff/README.md`. Триггер — повторение workflow violation 2 раза подряд (TASK-028 + TASK-029).

## Открытые вопросы / тех-долг

- **Sleep-loop scheduler drift** — приемлемо для MVP, но если backup-время начнёт расходиться с ожиданиями оператора (например, окно maintenance в проде сдвинется) — переписать на «sleep до следующего 02:30 UTC точно» (вычисление через `date` + арифметика).
- **`make prod.backup.now` в Deploy README** — обязательный шаг после `make prod.up` на чистом VPS (создаёт первый бэкап независимо от scheduler-окна). Учесть в TASK-031.
- **Smoke-test contract для CC** — добавить в `handoff/templates/report.md` явное требование «прогнать опасные пути (restore, rollback, delete) на dev-стенде». Сейчас формально не требуется, и CC прогоняет только happy path.
