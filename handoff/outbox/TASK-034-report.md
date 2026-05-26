---
task: TASK-034
completed: 2026-05-27
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/90
branch: feature/TASK-034-prod-secrets-validation
commits:
  - 8baaad3 feat(security): validate prod secrets in Settings
---

# Отчёт по TASK-034: Валидация секретов и backend'а в `Settings` для prod-окружения

## Сводка

Закрыта критическая уязвимость C-02 (CWE-798/521) из аудита MVP. Раньше при случайном копировании dev-`.env` на prod приложение стартовало с дефолтными секретами (`dev-admin-secret`, `changeme`, и т.п.), что делало возможным forging signed-cookie сессий → захват админки.

**Решение:** `Settings` теперь содержит `@model_validator(mode="after")` который при `environment != "dev"` проверяет:
- Секреты не содержат маркеров слабости: `dev-`, `changeme`, `secret`, `test`
- Длина секретов ≥32 символов
- `telegram_bot_token` не равен `dev-bot-token` и ≥30 символов
- `external_registry.backend != "mock"`
- `log_format == "json"`

При нарушении любого правила приложение падает при старте с понятным сообщением, указывающим какое поле невалидно.

## Изменённые файлы

```
* src/shared/config.py          # _WEAK_SECRET_MARKERS, _validate_prod_secrets()
* tests/unit/test_config.py     # 9 новых тестов (все сценарии из DoD)
* infra/.env.example            # предупреждения о генерации секретов
+ infra/.env.prod.example       # новый файл с обязательными prod-полями
* docs/07-deployment.md         # раздел "Генерация сильных секретов"
* .gitignore                    # разрешён .env.prod.example
```

## Как воспроизвести / запустить

```bash
# прогнать все тесты
poetry run pytest tests/unit/test_config.py -v

# проверить валидацию вручную (должен упасть с ошибкой):
ENVIRONMENT=prod ADMIN_SECRET_KEY=dev-admin-secret poetry run python -c "from src.shared.config import Settings; Settings()"
```

## Что не сделано

Ничего — все пункты DoD выполнены.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-27 — TASK-034: валидация prod-секретов в Settings (PR #90)
```

## Метрики

- Тестов добавлено: 9
- Тестов пройдено: 242 (was 233, +9)
- Покрытие: 100% (все ветки валидатора протестированы)
- Время на выполнение: ~1.5ч
