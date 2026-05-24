# Решения — task-025-review

**Все 5 — keep + 1 паттерн зафиксирован:**

| # | Решение | Обоснование |
|---|---|---|
| 1 (keep) | `UserService(session)` без явного `registry=None` — keep | Конструктор уже принимает default. Не дублируем |
| 2 (**паттерн**) | **`GET /login` для CSRF в admin-handler-тестах** — test convention | `/login` public, не требует service-mock'ов. Тест получает CSRF-token и проверяет POST-handler изолированно. Уменьшает coupling тестов с другими handler'ами. Применять для всех новых tests/unit/admin/* |
| 3 (keep) | `{{ p.is_correct is none }}` в Jinja (не `not p.is_correct`) | `False` — валидное значение ≠ `None`. `is none` различает «нет итога» (NULL) и «не сбылся» (False) |
| 4 (keep) | Сортировка предсказаний `Event.starts_at DESC, Prediction.id DESC` — хронологически | Без разделения active/archived. Триггер для добавления — UX-feedback админа |
| 5 (keep) | `func.count(Prediction.id)` через outer join (вместо `selectinload(User.predictions)` + Python len) | Возвращает 0 для пользователей без прогнозов. Не загружает тысячи объектов в memory на admin-list-странице |

## Test pattern: GET /login для CSRF (фиксация)

В admin-handler-unit-тестах через TestClient для получения CSRF-token используем **GET /login** вместо других routes. Логика:

- `/login` — публичный, не требует middleware-auth (whitelist в `RequireAdminMiddleware`).
- Не требует service-mock'ов (никаких `EventService` / `UserService` patch'ей).
- Получаем CSRF-token + cookie из response, используем в последующих POST'ах.

```python
def _get_csrf(client: TestClient) -> str:
    response = client.get("/login")
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.find("input", {"name": "csrf_token"})["value"]
```

Альтернатива (использовать `/events/new` или `/categories/new`) требует mock'ать `EventService` или `CategoryService`, что увеличивает coupling теста.

Применять во всех новых admin-handler-тестах. Старые тесты (test_categories_handler, test_events_handler) — оставить как есть; конвертация — отдельная мелкая задача при следующем касании.
