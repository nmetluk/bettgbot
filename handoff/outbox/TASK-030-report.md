# TASK-030: Structured JSON logging + log rotation для prod — отчёт

## Что сделано

- **`src/shared/config.py`**: `log_format` дефолт изменён на `"console"` (было `"json"`)
- **`src/shared/logging.py`**: добавлен `_get_renderer()` helper для переключения между JSONRenderer и ConsoleRenderer
- **`infra/.env.example`**: задокументирован `LOG_FORMAT=console` с комментарием про dev/prod
- **`infra/docker-compose.prod.yml`**: bot и web имеют `environment: LOG_FORMAT: json`
- **`tests/unit/test_logging.py`**: добавлены проверки processor chain для json/console форматов

## Коммиты

- `7cb6d4b` feat(logging): TASK-030 structured JSON logging + log rotation для prod

## Тесты

```bash
uv run pytest tests/unit/test_logging.py -v
# 5 passed
```

## Форматы логов

**Console (dev, LOG_FORMAT=console):**
```
2025-05-25T02:45:00Z [info] test_event value=42
```

**JSON (prod, LOG_FORMAT=json):**
```json
{"timestamp": "2025-05-25T02:45:00Z", "level": "info", "event": "test_event", "value": 42}
```

## PR

https://github.com/nmetluk/bettgbot/pull/82
