---
id: TASK-067
created: 2026-05-30
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - handoff/outbox/bugs-found-during-update.md
  - docs/08-conventions.md
  - src/shared/repositories/event.py
  - src/admin/app.py
  - src/shared/models/broadcast.py
priority: normal
estimate: M
---

# TASK-067: Единая timezone-стратегия (убрать naive/aware-разнобой и deprecated utcnow) + чек-листы

## Контекст

При обновлении прода исполнитель словил два 500 на `GET /events` из-за сравнения naive и aware
datetime (см. `handoff/outbox/bugs-found-during-update.md`, баги №3 и №4) и закрыл их хотфиксами
`1894033`/`34b8ead`, переведя `now()` и сравнения на **naive** `datetime.utcnow()`. Это band-aid с
двумя проблемами:

1. **`datetime.utcnow()` устарел (deprecated) в Python 3.12** — проект на 3.12, это будущие warnings/слом.
2. **Направление фикса (naive) противоречит схеме БД.** Колонки времени в `0001_init` объявлены
   **timezone-aware**: `sa.TIMESTAMP(timezone=True)` (`starts_at`, `predictions_close_at`, `created_at`,
   `last_login_at`, `archived_at` и т.д.). При этом новые модели (напр. `Broadcast.created_at/started_at/
   finished_at`) используют bare `Mapped[datetime]` → **naive** `DateTime`. А по коду разбросано ~20
   мест с aware `datetime.now(tz=UTC)`. Итог: naive и aware смешаны и на уровне колонок, и в коде —
   отсюда хрупкие сравнения и 500-е.

Это аудит-находка уровня надёжности: нужна **одна** стратегия, применённая сквозно.

## Цель

Во всём проекте — единый, непротиворечивый подход к datetime; ноль `datetime.utcnow()`; колонки и код
согласованы; сравнения naive/aware больше не могут падать. Правила зафиксированы в `docs/08-conventions.md`.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-067-report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёржен.

### 0. Сначала выяснить факт (не угадывать)

- [ ] Определить, что **реально** возвращает рантайл для aware-колонок (`TIMESTAMP(timezone=True)`) через
      текущий SQLAlchemy+asyncpg: aware или naive объект. Зафиксировать вывод в отчёте (короткий
      integration-проб: записать и прочитать `Event.starts_at`, проверить `tzinfo`). От этого зависит,
      почему naive-хотфикс «заработал», и какой инвариант брать за истину.

### 1. Выбрать и применить ОДНУ стратегию

Рекомендация cowork (если проба №0 не покажет весомой причины против): **aware UTC везде**, т.к.
ядро схемы уже `timezone=True`.

- [ ] Все datetime-колонки — `timezone=True` (`sa.TIMESTAMP(timezone=True)` в миграциях,
      `mapped_column(DateTime(timezone=True), …)` в моделях). Привести «naive» модели к aware:
      как минимум `Broadcast.{created_at,started_at,finished_at}` (+ найти прочие bare `Mapped[datetime]`
      через ревизию `src/shared/models/`). Тип колонок выровнять **миграцией** `0006_*`
      (`ALTER COLUMN ... TYPE timestamptz`), цепочка `…→0005→0006`, покрыть `test_migrations`.
- [ ] В коде: **убрать все `datetime.utcnow()`** (`git grep -n "datetime.utcnow" src/` → пусто), заменить
      на aware `datetime.now(UTC)`. Это и `src/admin/app.py:43` (`templates.env.globals["now"]`), и
      `src/shared/repositories/event.py` (строки ~187/191). В шаблонах сравнения вести в aware (не
      `.replace(tzinfo=None)`); если где-то остался `.replace(tzinfo=None)` — убрать или обосновать.
- [ ] Завести единый helper (напр. `src/shared/time.py: def utcnow() -> datetime: return datetime.now(UTC)`)
      и использовать его, чтобы не плодить `datetime.now(tz=UTC)` по коду. mypy strict для shared.
- [ ] Если проба №0 покажет, что строго нужен naive-подход — допустимо выбрать **naive UTC везде**, но тогда:
      колонки `timezone=False`, helper `utcnow_naive()`, и **запрет** `datetime.now(tz=UTC)`. Любой выбор —
      обосновать в отчёте; главное, чтобы не осталось смешения.

### 2. Документация и чек-листы (из багов №1, №2)

- [ ] `docs/08-conventions.md` — раздел «Время и timezone»: выбранная стратегия, helper, запрет
      `datetime.utcnow()`, правило «колонки времени — единый tz-режим».
- [ ] `docs/08-conventions.md` — раздел «Миграции»: **как переименовывать ревизии безопасно**
      (баг №1: переименование файла миграции рассинхронило `alembic_version` на проде; зафиксировать —
      ревизии не переименовывать после деплоя, либо отдельной миграцией обновлять `alembic_version`).
- [ ] `docs/08-conventions.md` — чек-лист «Новое обязательное поле в Settings» (баг №2: `ADMIN_SECRET_KEY`/
      `ADMIN_CSRF_SECRET` не были проброшены в сервис `bot`): при добавлении required-поля — проверить все
      сервисы compose, обновить `.env*.example`, прогнать `docker compose config`.

### 3. Качество

- [ ] Тест(ы): сравнение «сейчас vs колонка» больше не падает ни в aware-, ни в смешанном входе;
      регресс `GET /events`-подобных сравнений покрыт. `ruff`/`mypy`/`pytest` зелёные.
- [ ] PR `TASK-067: unify timezone strategy + conventions`, CI зелёный, PR смёржен, локальная `main` синхр.
- [ ] Move-семантика inbox→archive: перед archive — `ls handoff/inbox/ | grep TASK-067`, `git rm` копии;
      archive директорией `handoff/archive/TASK-067-timezone-strategy/task.md`.

## Вне скоупа

- Изменение пользовательских таймзон/локализации времени в UI (сейчас всё в UTC — это ок).
- Глобальный рефактор форматирования дат в шаблонах сверх необходимого для устранения разнобоя.

## Артефакты

- `* src/shared/models/broadcast.py` (+ др. модели с bare `Mapped[datetime]`) — `DateTime(timezone=True)`
- `+ src/migrations/versions/0006_*.py` — выравнивание типов колонок
- `+ src/shared/time.py` — helper `utcnow()`
- `* src/admin/app.py`, `* src/shared/repositories/event.py` (+ места с `datetime.utcnow()`/`now(tz=UTC)`)
- `* docs/08-conventions.md` — разделы time/migrations/settings-checklist
- `* tests/...` — проба рантайма + регресс-тест сравнений

## Ссылки

- Первоисточник: [`handoff/outbox/bugs-found-during-update.md`](bugs-found-during-update.md) (баги №1–4)
- Aware-колонки: `src/migrations/versions/0001_init.py` (`TIMESTAMP(timezone=True)`)
- Naive-модель-пример: `src/shared/models/broadcast.py` (bare `Mapped[datetime]`)

## Подсказки исполнителю

- Не копируй слепо band-aid `datetime.utcnow()` — он deprecated и тянул проект в naive при aware-колонках.
- Сначала проба №0 (что реально в рантайме), потом выбор. Это снимет неоднозначность «почему naive-фикс
  вообще помог».
- Миграцию типов колонок делай аккуратно: `timestamptz` хранит момент времени; при конверсии из
  предполагаемого UTC используй `AT TIME ZONE 'UTC'`/`USING ... AT TIME ZONE 'UTC'` корректно, проверь на
  данных в `test_migrations`.
