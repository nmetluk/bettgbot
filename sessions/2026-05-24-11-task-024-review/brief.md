# Brief — task-024-review

**Дата:** 2026-05-24
**Длительность:** короткая сессия cowork

## Запрос владельца

Прочитать отчёт по TASK-024 и подготовить TASK-025 (пользователи).

## Контекст

Локальный CC закрыл TASK-024 за 3 коммита (squash `9800664`), **30 минут — второй рекорд подряд**. Гипотеза из review TASK-023 подтверждена: задачи с готовым сервисом + изолированным UI делаются предельно быстро.

PR [#70](https://github.com/nmetluk/bettgbot/pull/70), pre-task cleanup [#69](https://github.com/nmetluk/bettgbot/pull/69), archive [#71](https://github.com/nmetluk/bettgbot/pull/71).

**Карточка события теперь полная**: Данные (TASK-022) / Исходы (TASK-023) / Результат (TASK-024).

Реализация:
- `POST /events/{event_id}/result` handler — CSRF + `EventService.set_result` (TASK-009 транзакционный) + flash-redirect (`?success=result_set&marked=N` или `?error=...`).
- Активирована вкладка «Результат» в `events/form.html` с условием `is_published AND predictions_close_at <= now()`. Disabled + tooltip когда не выполнено.
- Tab content в 3 режимах: **read-only** (если `result_outcome_id`), **warning** (если `< 2 outcomes`), **form** с radio + JS confirm.
- 7 новых unit-тестов (4 handler + 3 visibility).

**320 тестов** (211 unit + 109 integration). CI 4 зелёных job'а.

## Что сделано в этой сессии

5 open questions исполнителя — **все 5 keep**, никаких code changes:

- **(Q1, keep)** Server-side guard в `set_result` handler на `is_published AND predictions_close_at <= now()` — **trust UI**. Admin не должен делать запрещённые действия через прямой URL. Если соберётся — service бросит исключение (event архивный → `EventAlreadyHasResultError`; outcome не для event → `OutcomeNotForEventError`).

- **(Q2, информационное)** CHECK constraint `ck_event_result_archive_consistency` (TASK-018) разрешает 3 комбинации. `set_result` ставит `(has_result, archived, archived_at)` — третья валидная комбинация. CHECK не нарушается.

- **(Q3, keep)** Flash в URL после refresh — норма для query-string подхода. `history.replaceState` для очистки URL — overengineering для MVP.

- **(Q4, keep)** Read-only mode без кнопки Edit — спека «переопределение не предусмотрено в MVP».

- **(Q5, keep)** Disabled tab через Bootstrap `disabled` class + `aria-disabled="true"` + tooltip — accessibility-friendly.

Обновлены:

- [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) — закрытие TASK-024, новый шаг TASK-025. **Этап 3 — 6/8 задач**.
- Сформирована задача [`handoff/inbox/TASK-025-admin-users.md`](../../handoff/inbox/TASK-025-admin-users.md). Размер L.

## Темп: статистика серии TASK-021..024

| TASK | Что | Время |
|---|---|---|
| TASK-021 | CRUD категорий (первая бизнес-задача) | 60 мин |
| TASK-022 | CRUD событий (с CSRF middleware + admin info) | 75 мин |
| TASK-023 | CRUD исходов через HTMX (первая HTMX) | 30 мин ⚡ |
| TASK-024 | Фиксация итога | 30 мин ⚡ |

Темп возрос: первые две — больше инфраструктуры (новые exceptions, middleware, шаблонные паттерны). Последние две — уже готовый сервис + изолированный UI. **Гипотеза**: TASK-025 (пользователи) и TASK-026 (audit) — около 45-60 мин каждая, потому что список пользователей потребует новых repo-методов (search) и audit-UI потребует уже отложенного `list_with_admin`.

## Следующие шаги

1. Локальный CC берёт **TASK-025**: раздел «Пользователи». Список с поиском (телефон/username/имя), пагинация, колонка predictions count. Карточка пользователя с его прогнозами. POST `/users/{id}/block` / `/unblock` через `UserService.set_blocked` + audit. Размер L (новый repo-search + 2 handler + 2 шаблона).
2. **TASK-026** — UI аудит-лога с фильтрами (admin/action/датa). Закрывает Этап 3. Использует отложенный `AuditLogRepository.list_with_admin` (тех-долг из TASK-007).
3. После TASK-026 → Этап 4 production (TASK-027..031).
