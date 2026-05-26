---
task: TASK-036
completed: 2026-05-27
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/92
branch: feature/TASK-036-html-escape
commits:
  - 404d7df feat(security): HTML-escape user content in Telegram messages
  - 2df0bef fix: remove duplicate update_event method
  - 87a6db1 chore(handoff): fix TASK-035 archive format to directory
---

# Отчёт по TASK-036: HTML-escape всех user/admin-supplied значений в Telegram-сообщениях

## Сводка

Исправлена **критическая уязвимость C-04 (CWE-79)** из MVP-аудита: все user/admin-supplied значения, попадающие в Telegram-сообщения, теперь экранируются через `html.escape()`.

Layered protection:
1. **Client-side**: `safe_format()` из нового `src/bot/_text_safety.py` экранирует все подставляемые значения.
2. **Server-side**: сервисы валидируют `title`, `description`, `label`, `name` на отсутствие символов `<` и `>`.
3. **Admin UI**: handler'ы показывают user-friendly ошибку при вводе запрещённых символов.

## Изменённые файлы

```
+ src/bot/_text_safety.py                         # новый helper safe_format()
+ tests/unit/bot/test_text_safety.py              # unit-тесты safe_format()
* src/bot/routers/*.py                             # все router'ы используют safe_format()
* src/bot/scheduler/jobs.py                        # REMINDER_NOTIFICATION экранирует title
* src/shared/exceptions.py                         # InvalidContentError и дочерние
* src/shared/services/event.py                     # валидация title/description/label
* src/shared/services/category.py                  # валидация name
* src/admin/routes/events.py                       # обработка EventInvalidContentError
* src/admin/routes/outcomes.py                     # обработка OutcomeInvalidContentError
* src/admin/routes/categories.py                   # обработка CategoryInvalidContentError
* tests/unit/admin/test_events_handler.py          # тесты валидации при создании/обновлении
* tests/unit/bot/routers/test_events_handler.py    # тест экранирования в карточке события
```

## Как воспроизвести / запустить

```bash
# прогнать тесты
pytest tests/unit/bot/test_text_safety.py -v
pytest tests/unit/bot/routers/test_events_handler.py -v
pytest tests/unit/admin/test_events_handler.py -v

# локально: попробовать создать событие с title="Match <script>"
# → должна появиться ошибка "Символы `<` и `>` не допускаются."
```

## Что не сделано

Нет. Все пункты DoD выполнены.

## Открытые вопросы для проектировщика

нет

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-27 — TASK-036: HTML-escape user content в Telegram-сообщениях (PR #92)
```

## Метрики

- Тестов добавлено: 9 новых тест-кейсов
- Покрытие изменённых модулей: все новые функции покрыты тестами
- Время на выполнение: ~2ч
