---
task: TASK-025
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/73
branch: feature/TASK-025-admin-users
related-prs:
  - https://github.com/nmetluk/bettgbot/pull/72 (pre-task cleanup)
commits:
  - 15b8244 chore(handoff): take TASK-025 in progress
  - 37e5b05 feat(repositories+services): User.list_for_admin_with_prediction_counts + Prediction.list_all_by_user_for_admin
  - 4e654e4 feat(admin): users routes (list/detail/block/unblock) + list/detail templates + sidebar Пользователи active
  - d196241 test: users admin queries (6 integration) + users handler (9 unit)
---

# Отчёт по TASK-025: раздел «Пользователи» в админке

## Сводка

Седьмая бизнес-задача в админке. `UserService.block` / `unblock` / `list_for_admin` / `count_for_admin` уже были из TASK-009 — добавил только `UserService.list_admin_with_counts` (обёртка над новым `UserRepository.list_for_admin_with_prediction_counts` с COUNT через LEFT JOIN). `PredictionService.list_all_by_user_for_admin` объединяет active+archived в одной выборке через `selectinload(event)` + `selectinload(outcome)` — eager fetch для admin-таблицы без N+1.

4 handler'а в `routes/users.py`: list (search + pagination), detail (профиль + предсказания + статистика), block/unblock POST (с защитой `get_by_id → 404`). `UserService(session)` — registry-параметр опциональный с дефолтом None (already из TASK-009 review).

`list.html` — таблица с search-form, `table-secondary` строка если заблокирован, бэйджи статуса. Pagination с QS-сохранением query. `detail.html` — 2 колонки: профиль (`<dl class="row">` с ID/TG ID/phone/username/timestamps/badge) + блок-форма с confirm + статистика (correct/total/percent). Правая колонка — таблица всех прогнозов с цветовыми бэйджами (`✅ сбылся` / `❌ не сбылся` / `⏳ нет итога` / `—`). Sidebar теперь активен «Пользователи» (был disabled до TASK-025).

15 новых тестов (6 integration + 9 unit). В тестах для CSRF использую `/login` (public, не требует service-mock'ов) — паттерн, который я применю в TASK-026+.

## Изменённые файлы

```
* src/shared/repositories/user.py                # +list_for_admin_with_prediction_counts
* src/shared/repositories/prediction.py          # +list_all_by_user_for_admin (selectinload event+outcome)
* src/shared/services/user.py                    # +list_admin_with_counts
* src/shared/services/prediction.py              # +list_all_by_user_for_admin
+ src/admin/routes/users.py                      # 4 handlers (list/detail/block/unblock)
+ src/admin/templates/users/list.html            # таблица + поиск + пагинация
+ src/admin/templates/users/detail.html          # профиль + прогнозы + статистика + block-form
* src/admin/templates/base.html                  # sidebar Пользователи active
* src/admin/app.py                               # +users router
+ tests/integration/services/test_user_service_admin.py   # 4 теста
+ tests/integration/services/test_prediction_service_admin.py  # 2 теста
+ tests/unit/admin/test_users_handler.py         # 9 тестов
* handoff/inbox/TASK-025-...md → archive/TASK-025-admin-users/task.md
+ handoff/outbox/TASK-025-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    147 files already formatted
mypy src/shared src/bot src/admin   Success: no issues found in 74 source files
pytest -m "not integration"      220 passed (было 211; +9)
pytest tests/integration         115 passed (было 109; +6)

CI PR #73 — все 4 job'а зелёные:
  Lint (ruff)                              12s
  Typecheck (mypy)                         20s
  Tests (pytest, unit)                     18s
  Integration                              45s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
make up && make migrate
make admin.create LOGIN=admin PASSWORD="strong!"
make admin

# Browser flow:
# 1) Login → / → Sidebar «Пользователи» → /users (таблица).
# 2) Поиск «+7999» → отфильтровано.
# 3) Открыть карточку → профиль + прогнозы + статистика.
# 4) «Заблокировать» → confirm → success flash, badge «заблокирован», строка в списке table-secondary.
# 5) «Разблокировать» → confirm → success flash, badge «активен».
# 6) В bot: попытка `/start` → user уже зарегистрирован, но при попытке прогноз → ACCESS_DENIED (is_blocked guard в боте).
```

## Что не сделано / вынесено

1. **Pagination для прогнозов в карточке** — limit 100 жёстко, без пагинации. Спека «не нужна — обычно ≤30 у пользователя».
2. **Массовый block/unblock** — outside scope.
3. **Выгрузка в CSV** — outside scope, идея в BACKLOG.
4. **Audit-log в карточке** — TASK-026 (отдельный раздел админки).
5. **Sort by predictions count** — спека «если потом понадобится — добавим параметр». Сейчас только `created_at DESC`.

## Открытые вопросы для проектировщика

1. **`UserService(session)` без явного `registry=None`** — конструктор уже принимает `registry: ExternalUserRegistryClient | None = None` (TASK-010 review). Я не передаю явно `registry=None` — это работает по default. Чистее?
2. **`_get_csrf` через `/login`** в тестах — общий паттерн вместо `/<any-page>` (которая может требовать service-mock'ов). Это уменьшает связанность теста с handler'ом, но GET /login делает дополнительный шаг. Согласуем как convention для test patterns? Сейчас в `test_categories_handler.py` и `test_events_handler.py` использую `/events/new` или `/categories/new` — будущие тесты можно перевести на `/login`.
3. **`predictions[0].is_correct is none`** в шаблоне — используется Jinja `is none` тест. Работает, но `if not p.is_correct` иногда выглядит читабельнее. Я выбрал явный `is none` потому что `is_correct = False` — это валидное значение ≠ NULL.
4. **`PredictionService.list_all_by_user_for_admin` сортирует `Event.starts_at DESC, Prediction.id DESC`** — недавние/предстоящие наверху. Не разделяет активные/архивные явно. Если хотим сначала active, потом archived — добавить sort by `Event.is_archived ASC` первым.
5. **`func.count(Prediction.id)` через outer join** в `list_for_admin_with_prediction_counts` — для пользователей без прогнозов вернёт 0 (правильное поведение). Не использовал `selectinload(User.predictions)` чтобы избежать загрузки сотен Prediction-объектов.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-025: раздел «Пользователи» в админке. `UserRepository.list_for_admin_with_prediction_counts` (LEFT JOIN + GROUP BY + COUNT, sort `created_at DESC`). `PredictionRepository.list_all_by_user_for_admin` (selectinload event+outcome, active+archived в одной выборке). Service-wrappers. 4 handler'а в `routes/users.py` (list+search+pagination, detail+stats+predictions, block/unblock). `users/list.html` + `users/detail.html`. Sidebar «Пользователи» активирован. 15 новых тестов (220 unit + 115 integration). PR [#73](https://github.com/nmetluk/gettgbot/pull/73) → squash `5696147`. Pre-task cleanup [#72](https://github.com/nmetluk/bettgbot/pull/72).
```

## Метрики

- Файлов добавлено: 6 (route + 2 шаблона + 2 integration test + 1 unit test + report)
- Файлов изменено: 5 (app, base.html, user repo+service, prediction repo+service)
- Тестов добавлено: 15 (всего 220 unit + 115 integration; было 211+109)
- Время на выполнение: ~50 мин (compactная задача — service частично готов, шаблоны standard CRUD)
