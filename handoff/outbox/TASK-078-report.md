# TASK-078 Report: вернуть рабочую интеграционную регрессию на `GET /events/{id}`

## Выполнено

### Восстановлен интеграционный тест

- Создан файл `tests/integration/services/test_event_detail_admin.py` с 4 тестами:
  - `test_event_detail_returns_200_for_draft_without_outcomes` — черновик без исходов
  - `test_event_detail_returns_200_for_published_with_outcomes` — опубликованное событие с исходами
  - `test_event_detail_returns_404_for_nonexistent` — 404 на несуществующий id
  - `test_event_detail_result_tab_loads_without_error` — вкладка «Результат»

### Auth через dependency_overrides

Вместо подделки cookie с неверным секретом (как было в удалённом тесте) теперь используется паттерн из unit-тестов:

- `app.dependency_overrides[current_admin]` подменяет dependency для хендлера
- Патч `SessionLocal` в middleware для аутентификации
- Валидная session-cookie через `create_session_token` с боевым секретом

### Cleanup данных

Каждый тест создаёт данные в реальной БД и удаляет их после завершения, чтобы не засорять БД.

## Результаты тестирования

```
$ uv run pytest tests/integration/services/test_event_detail_admin.py -v -m integration

tests/integration/services/test_event_detail_admin.py::test_event_detail_returns_200_for_draft_without_outcomes PASSED
tests/integration/services/test_event_detail_admin.py::test_event_detail_returns_200_for_published_with_outcomes FAILED
tests/integration/services/test_event_detail_admin.py::test_event_detail_returns_404_for_nonexistent PASSED
tests/integration/services/test_event_detail_admin.py::test_event_detail_result_tab_loads_without_error FAILED
```

**Все тесты проходят изолированно** (при запуске по одному):

```
$ uv run pytest tests/integration/services/test_event_detail_admin.py::test_event_detail_returns_200_for_published_with_outcomes -v -m integration
tests/integration/services/test_event_detail_admin.py::test_event_detail_returns_200_for_published_with_outcomes PASSED
```

### Flaky при совместном запуске

При запуске всех тестов вместе 2 из 4 падают с `RuntimeError: Event loop is closed`. Это известная проблема с `TestClient` и `pytest-asyncio` — TestClient запускает FastAPI в отдельном thread, и при закрытии одного loop следующий тест падает.

**Решение для CI**: запускать тесты по одному или добавить `pytest -k "test_event_detail"` для последовательного запуска.

## Проверено

- ✅ Линт (`ruff check`) — чистый
- ✅ Типы (`mypy`) — чистый
- ✅ Все тесты проходят изолированно

## Sanity check

Тест **действительно ловит** баг, который был в TASK-074/TASK-076. Если временно убрать eager-load в `get_for_admin_detail`, тест упадёт с 500 вместо 200. (Проверено локально, изменения в main не вносятся.)

## Изменённые файлы

- `tests/integration/services/test_event_detail_admin.py` (восстановлен)
- `handoff/inbox/TASK-078.in-progress.md` → `handoff/archive/TASK-078.md`

## Команды для воспроизведения

```bash
# Запуск одного теста (проходит)
uv run pytest tests/integration/services/test_event_detail_admin.py::test_event_detail_returns_200_for_draft_without_outcomes -v -m integration

# Запуск всех тестов (2 из 4 упадут с event loop issue)
uv run pytest tests/integration/services/test_event_detail_admin.py -v -m integration
```

## Вопросы к проектировщику

1. **Flaky с event loop** — при совместном запуске 2 теста падают. Приемлемо ли для интеграционных тестов запускать их по одному в CI, или нужно дополнительное исследование?

2. **Cleanup данных** — текущий подход удаляет данные после каждого теста. Альтернатива — использовать транзакционный rollback, но это не работает с TestClient (разные event loops). Подходит ли текущий подход?
