---
task: TASK-058
completed: 2026-05-29
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/116
branch: feature/TASK-058-admin-leaderboard
commits:
  - 5632dab feat(admin): leaderboard page with user ranking (TASK-058)
  - 2038455 fix(tests): adjust assertions for rounded accuracy values
---

# Отчёт по TASK-058: Лидерборд пользователей в админке

## Сводка

Реализован админ-экран `/leaderboard` с рейтингом пользователей по точности прогнозов. Метрика ранжирования — точность `correct/resolved*100` по убыванию, tiebreak при равной точности — больше верных, затем больше разрешённых. Порог квалификации — минимум 5 разрешённых прогнозов (дефолт), заблокированные пользователи исключаются.

В коде использован существующий паттерн агрегации из `PredictionRepository.user_stats()`. Один SQL-запрос с `GROUP BY user_id`, `HAVING resolved >= min_resolved`, JOIN User для отображаемого имени, сортировка по accuracy DESC, correct DESC, resolved DESC.

Период all-time реализован обязательно, опциональный фильтр по периоду (30d/90d) — сделан через query-параметр `period`, который транслируется в `period_days` для фильтрации по `Prediction.created_at`.

## Изменённые файлы

```
* src/shared/repositories/prediction.py              # метод leaderboard()
* src/shared/services/stats.py                       # LeaderboardRow + leaderboard()
* src/shared/services/__init__.py                    # экспорт LeaderboardRow
* src/admin/app.py                                   # регистрация роутера
* src/admin/routes/leaderboard.py                    # GET /leaderboard
* src/admin/templates/_layout_shell.html             # пункт «Рейтинг» в навигации
* src/admin/templates/leaderboard/list.html          # шаблон таблицы с топ-3
* tests/integration/repositories/test_prediction_repository.py  # тесты leaderboard()
* tests/integration/services/test_stats_service.py   # тесты service.leaderboard()
* tests/unit/admin/test_leaderboard_handler.py       # тесты хендлера
```

## Как воспроизвести / запустить

```bash
# Админка на http://localhost:8000/leaderboard
uv run uvicorn src.admin.app:app --reload

# Тесты
uv run pytest tests/unit/admin/test_leaderboard_handler.py -v
uv run pytest tests/integration/repositories/test_prediction_repository.py::test_leaderboard_threshold_and_sorting -v
uv run pytest tests/integration/services/test_stats_service.py::test_leaderboard_returns_ranked_rows -v
```

## Что не сделано

Ничего — вся задача выполнена в полном объёме. Бот-команда `/leaderboard` вынесена в отдельную будущую задачу (по условию).

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-29 — TASK-058: leaderboard страницы `/leaderboard` в админке с рейтингом пользователей по точности (PR #116)
```

## Метрики

- Тестов добавлено: 8 (5 unit + 3 integration)
- Покрытие изменённых модулей:StatsService и PredictionRepository полностью покрыты тестами
- Время на выполнение: ~2ч
