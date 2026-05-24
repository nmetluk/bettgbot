# Brief — task-025-review

**Дата:** 2026-05-24

## Запрос владельца

Прочитать отчёт по TASK-025 и подготовить TASK-026 — финал Этапа 3.

## Контекст

Локальный CC закрыл TASK-025 за 4 коммита (squash `5696147`), 50 минут. PR [#73](https://github.com/nmetluk/bettgbot/pull/73), pre-task cleanup [#72](https://github.com/nmetluk/bettgbot/pull/72), archive [#74](https://github.com/nmetluk/bettgbot/pull/74).

Раздел «Пользователи» работает:
- `UserRepository.list_for_admin_with_prediction_counts` — LEFT JOIN + GROUP BY + COUNT.
- `PredictionRepository.list_all_by_user_for_admin` — `selectinload(Prediction.event)` + `selectinload(Prediction.outcome)` (eager fetch, active+archived в одной выборке).
- 4 handlers: list (search+pagination), detail (профиль+прогнозы+статистика), block/unblock POST.
- 2 шаблона: list с `table-secondary` строкой для заблокированных + бэйджи; detail с двумя колонками (профиль+block-form vs прогнозы).
- Sidebar «Пользователи» активирован.

**15 новых тестов** (6 integration + 9 unit). **335 тестов** (220+115). CI 4 зелёных.

## Что сделано в этой сессии

5 open questions исполнителя — **все 5 keep** + **1 паттерн зафиксирован**:

- **(Q1, keep)** `UserService(session)` без явного `registry=None` — конструктор уже принимает default None (TASK-010 review). Чистее не указывать default явно.

- **(Q2, паттерн)** **`GET /login` для CSRF в тестах** — convention: вместо `/events/new` или `/categories/new` (требует service-mock'ов для прохождения handler-logic) используем `/login` (public, без service-зависимостей). Уменьшает связанность теста с handler'ом. **Зафиксировать в DECISIONS**. Старые тесты (test_categories/events_handler) можно постепенно перевести, новые сразу пишутся на `/login`.

- **(Q3, keep)** `is_correct is none` в Jinja vs `not p.is_correct` — `is none` правильнее, потому что `False` — валидное значение ≠ `None`. Без явного `is none` шаблон считал бы `is_correct=False` как «нет данных».

- **(Q4, keep)** Сортировка `Event.starts_at DESC, Prediction.id DESC` — хронологический порядок без разделения active/archived. Если админ захочет «сначала активные» — отдельная задача. На MVP keep.

- **(Q5, keep)** `func.count(Prediction.id)` через outer join возвращает 0 для пользователей без прогнозов. Корректное поведение. Не используем `selectinload(User.predictions)` чтобы избежать загрузки тысяч Prediction-объектов на admin-list-странице.

Обновлены:

- [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) — закрытие TASK-025, последняя задача Этапа 3 — TASK-026.
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — 1 паттерн (test pattern `/login` для CSRF).
- Сформирована задача [`handoff/inbox/TASK-026-admin-audit.md`](../../handoff/inbox/TASK-026-admin-audit.md) — финал Этапа 3.

## Темп серии TASK-021..025

| TASK | Что | Время |
|---|---|---|
| TASK-021 | CRUD категорий | 60 мин |
| TASK-022 | CRUD событий + CSRF middleware | 75 мин |
| TASK-023 | CRUD исходов через HTMX | 30 мин |
| TASK-024 | Фиксация итога | 30 мин |
| TASK-025 | Пользователи + блок | 50 мин |

Средний темп Этапа 3: ~50 минут на задачу. TASK-022 — самая длинная (новые middleware-паттерны). TASK-023/024 — самые короткие (готовый сервис + изолированный UI).

## Следующие шаги

1. Локальный CC берёт **TASK-026** (UI аудит-лога — финал Этапа 3). Использует отложенный `AuditLogRepository.list_with_admin` (тех-долг из TASK-007). Размер L.
2. После TASK-026 → **Этап 3 закрыт**, **8/8 задач**.
3. Стартует **Этап 4 — production** (TASK-027..031): docker-compose override+prod, бэкап, structured logs+ротация, deploy README, smoke-тесты после деплоя.
