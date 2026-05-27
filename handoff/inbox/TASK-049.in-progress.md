---
id: TASK-049
created: 2026-05-27
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - src/bot/scheduler/builder.py
  - src/bot/scheduler/jobs.py
  - src/shared/services/reminder.py
priority: high
estimate: S
---

# TASK-049: `dispatch_reminders` теряет напоминания при misfire/рестарте — fix окна

## Контекст

**Новая находка ревью 2026-05-27.** Текущая логика идемпотентности правильна (`ReminderDispatchLogRepository.record(...)` ДО `bot.send_message`), но при пропуске тика scheduler-а напоминания в окне пропуска **теряются навсегда**.

Текущие настройки (`src/bot/scheduler/builder.py:26-33`):

```python
scheduler.add_job(
    dispatch_reminders,
    trigger=IntervalTrigger(minutes=5),
    misfire_grace_time=60,
)
```

И ширина окна в `ReminderService.find_candidates`:

```python
diff_minutes >= settings_unnested.c.offset_minutes,
diff_minutes < settings_unnested.c.offset_minutes + window_minutes,  # window_minutes=5
```

Сценарий потери:
1. Scheduler работает в 12:00, обрабатывает окно `[offset, offset+5)`. ОК.
2. Деплой / restart контейнера / SIGKILL OOM-killer'ом в 12:01 — scheduler уходит.
3. Контейнер поднимается в 12:06. APScheduler видит, что job `dispatch_reminders` должен был запуститься в 12:05 (опоздание 60 секунд = ровно `misfire_grace_time`). Дальше — зависит от sub-секундной точности, но обычно misfire **не выполняется** (overshoot > grace).
4. Следующий тик в 12:10. Окно `[12:10+offset, 12:15+offset)`. Напоминания, у которых дедлайн был в окне `[12:05+offset, 12:10+offset)` — **пропущены**. Пользователь не получит уведомление, даже если событие ещё актуально (close ещё впереди по основному дедлайну).

`misfire_grace_time=60s` — это **anti-pattern для idempotent jobs**: для job'а, безопасного к повтору (UNIQUE constraint в БД), нужно `misfire_grace_time=None` (или = очень большое), чтобы скорее «выполнить с опозданием» чем «пропустить». Сейчас наоборот.

Бонус-проблема: даже без misfire, окно ровно равно tick interval. Любой clock-drift или дрожание (jitter) на ~1 секунду = напоминание попадает между двумя тиками и не отлавливается ни одним. На MVP ОК (только если scheduler никогда не дёргается), но архитектурно хрупко.

## Цель

(a) Снять misfire-блок: использовать `misfire_grace_time=None` (или `=3600` = 1 час) — пропущенный тик догоняется. (b) Расширить `window_minutes` чтобы покрывало `tick_interval + safety_margin`. (c) Опционально: добавить `coalesce=True` чтобы при множественном опоздании всё равно выполнилось ровно один раз.

## Definition of Done

- [ ] В `src/bot/scheduler/builder.py` `dispatch_reminders`:
  - `misfire_grace_time=3600` (1 час — хватит на любой реалистичный restart) **ИЛИ** `=None` (без грейса).
  - `coalesce=True` — при множественном backlog'е выполняется один раз с самым актуальным `now()`.
  - `max_instances=1` — на случай если кто-то перенастроит на ещё более частый тик.
- [ ] В `src/shared/services/reminder.py:58` параметр `window_minutes`: default поднять до **10** (tick=5 + 5 запаса; идемпотентность гарантирует, что overlap безопасен — UNIQUE constraint отсечёт дубликаты).
- [ ] В `src/bot/scheduler/jobs.py`: явно передать `window_minutes=10` (или подтянуть из `Settings`).
- [ ] В `src/shared/config.py`: новое поле `reminder_window_minutes: PositiveInt = 10`, использовать в job.
- [ ] Integration-тест: создать reminder с `offset=60`, событие с `close_at = now + 67 минут`. Прогнать `find_candidates(now=now, window_minutes=10)` — кандидат должен попасть в окно `[60, 70)` (запас 7 мин). Второй прогон с тем же now — `record()` вернёт False, не отправится.
- [ ] Integration-тест: симулировать misfire — два последовательных вызова `dispatch_reminders` подряд (как catch-up + следующий тик) — каждый кандидат отправлен ровно один раз.
- [ ] PR `TASK-049: reminder dispatch misfire catchup + wider window`.
- [ ] Отчёт + Move-семантика inbox→archive.

## Артефакты

- `* src/bot/scheduler/builder.py`
- `* src/bot/scheduler/jobs.py`
- `* src/shared/services/reminder.py` (default параметра)
- `* src/shared/config.py` (новое поле)
- `* tests/integration/test_dispatch_reminders.py`

## Подсказки исполнителю

- Идемпотентность через UNIQUE — это инвариант, на котором безопасно строить overlapping window. Не бойся «лишних» вычислений: `find_candidates` дёшев, основная цена — `bot.send_message`, который **не вызывается** для уже записанных кандидатов.
- `misfire_grace_time=None` в APScheduler означает «всегда run regardless of how late» (не «без грейса»). Документация неочевидна — см. `apscheduler.job.Job.misfire_grace_time` в исходниках.
- `coalesce=True` важен в сочетании с большим grace: иначе job выполнится N раз подряд, что для нас безопасно (idempotent), но грузит CPU напрасно.
- Не путай этот fix с retry-стратегией для `send_message` — здесь только про catching misses.
