---
id: TASK-046
created: 2026-05-26
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - scripts/backup-to-drive.sh
  - Makefile
  - CLAUDE.md
  - handoff/README.md
  - handoff/templates/task.md
  - state/DECISIONS.md
priority: high
estimate: S
---

# TASK-046: Снести Drive-зеркалирование, перейти на GitHub-only обмен задачами

## Контекст

Решение владельца 2026-05-26: убрать локально-синкнутую Google Drive папку как канал обмена handoff/state/sessions между cowork-агентом и локальным CC. Обмен задачами идёт **только через GitHub**.

**Почему меняем:**

- Drive самопроизвольно откатывается к старому состоянию (кейс 2026-05-26 — папка `Betting Bot backup` спонтанно вернулась к снапшоту 2026-05-25, потеряв TASK-043 archive и inbox целиком). Не стабильный канал.
- Удвоение источников правды: и в `origin/main` есть актуальный handoff, и в Drive копия. Дубликат → рассинхрон → паника.
- File Stream FUSE-мaунт нестабилен для bulk-rsync (зафиксировано в Workflow notes PROJECT_STATUS.md).
- Cowork-агент имеет PAT для прямого `git fetch` (см. DECISIONS 2026-05-25). Ему Drive не нужен.

**Новый workflow:**

- Cowork-агент проектирует, коммитит/пушит в `origin/main` (через PAT или через делегирование пушу владельцу).
- Локальный CC в начале сессии: `git fetch origin && git pull origin main` → забирает задачу из `handoff/inbox/` → выполняет → пушит → закрывает.
- **Никаких `make backup`. Никаких локально-синкнутых Drive-папок как канала.**
- Backup данных (как защита от потери диска) — личное дело владельца, не часть workflow.

## Цель

Привести в порядок все артефакты, упоминающие Drive-зеркало, чтобы новый локальный CC и будущие cowork-сессии не наследовали мёртвый канал.

## Definition of Done

- [ ] **Удалить скрипт:**
  - `git rm scripts/backup-to-drive.sh`
- [ ] **Удалить Makefile-цель `backup:`** (~строки 122-123 на момент TASK-045):
  ```makefile
  backup: ## Зеркалирование handoff/state/sessions ...
      @./scripts/backup-to-drive.sh
  ```
- [ ] **Обновить `CLAUDE.md`:**
  - Из раздела «Push обязателен после каждой задачи» убрать п.5.5 (про `make backup`)
  - Из секции «Когда задача готова» убрать DoD-пункт 5.5 (тоже про `make backup`)
  - Из второго bullet в перечне «Это позволяет» — убрать упоминание Drive-бэкапа, оставить только GitHub как single source of truth
  - В начале (после «Прежде чем начать любую работу») **добавить** явный пункт: «Сделай `git fetch origin && git pull origin main` — handoff обновляется только через GitHub, никаких Drive-зеркал»
- [ ] **Обновить `handoff/README.md`:**
  - Удалить секцию «Локальный backup handoff» целиком (вся таблица путей по ОС, инструкции по BB_DRIVE_BACKUP, и т.п.)
  - Удалить любые упоминания зеркала в Drive в других секциях
  - В секции «Жизненный цикл задачи» или «Где брать задачи» **добавить**: «Перед работой обязательно `git pull origin main` — handoff живёт только в репо»
- [ ] **Обновить `handoff/templates/task.md`:**
  - Удалить DoD-пункт «🚨 `make backup` после merge в main» — он больше не применим
- [ ] **Не трогать `state/`** — cowork уже обновил `DECISIONS.md` и `PROJECT_STATUS.md` под новый workflow (записи от 2026-05-26 про Drive deprecation).
- [ ] **Не трогать исторические записи** в `state/DECISIONS.md` про прошлый Drive workflow (TASK-028 запись 2026-05-25 и т.п.) — они снапшоты тех решений, оставляем как есть.
- [ ] **Не удалять и не править саму Drive-папку** на машине — это файлы пользователя, не репозиторий. Просто игнорируем её существование.
- [ ] `ruff check`, `mypy src/shared` — чисты (не должно быть никаких изменений в `src/`).
- [ ] PR открыт: `TASK-046: drop Drive backup workflow, GitHub-only handoff exchange`.
- [ ] Отчёт в `handoff/outbox/TASK-046-report.md`.
- [ ] **🚨 Move-семантика inbox→archive** (см. `handoff/README.md` — секция останется, остальные секции про Drive уйдут).
- [ ] ~~`make backup` после merge~~ — больше не нужно (этого пункта в DoD теперь нет, и слава богу).

## Артефакты

- `D scripts/backup-to-drive.sh`
- `* Makefile` — удалить `backup:` target
- `* CLAUDE.md` — убрать упоминания make backup, добавить git pull в начало
- `* handoff/README.md` — удалить секцию «Локальный backup handoff» и упоминания зеркала
- `* handoff/templates/task.md` — удалить DoD-пункт `make backup`
- `+ handoff/outbox/TASK-046-report.md`

## Подсказки исполнителю

1. **Не делай этот PR широко.** Не лезь поправлять каждое историческое упоминание Drive в `sessions/*` или в архивных `handoff/archive/TASK-028*` — это снапшоты тех решений. Изменяем только живые точки workflow.

2. **Проверь grep'ом полноту:** после правок `grep -rn "make backup\|backup-to-drive\|BB_DRIVE_BACKUP" --include='*.md' --include='Makefile' --include='*.sh' --include='*.py'` должно показывать **только** упоминания в:
   - `handoff/archive/` (исторические задачи)
   - `state/DECISIONS.md` (исторические записи)
   - `state/PROJECT_STATUS.md` (Workflow notes — cowork обновит)
   - `handoff/outbox/TASK-028-report.md` и подобные (отчёты — историчны)
   - `sessions/*` (история проектирования)

3. **CLAUDE.md правки сделай аккуратно** — там нумерация пунктов в секции «Push обязателен» и «Когда задача готова». Удаление 5.5 может потребовать сдвига 5.5 → ничего (просто удалить строку с переносом), либо переименования следующих пунктов. Сохрани последовательность.

4. **Запушь нормальным PR**, не прямо в main. CI workflow `handoff-consistency` должен на этом PR показать зелёный — если красный, описать почему в отчёте.

5. После merge — **больше никакого `make backup`**. Если рука потянется — это инстинкт от старого workflow.

## Ссылки

- [`state/DECISIONS.md`](../../state/DECISIONS.md) запись 2026-05-26 «Drive backup deprecated» — обоснование.
- [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) Workflow notes — обновлённый.
- [`CLAUDE.md`](../../CLAUDE.md) — целевой документ.
- [`handoff/README.md`](../README.md) — целевой документ.
