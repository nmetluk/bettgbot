---
task: TASK-087
completed: 2026-05-31
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/162
branch: feature/TASK-087-cleanup-middleware-comment-server-default-i18n
commits:
  - 585ebcf chore(cleanup): TASK-087 L1/L2/L3 from audit (middleware comment, func.now(), extract bot texts)
---

# Отчёт по TASK-087: Cleanup — комментарий middleware-ordering, func.now() в broadcast-моделях, вынос строк в texts.py

## Сводка

Закрыты три Low-находки (L1, L2, L3) из аудита 2026-05-31 одной маленькой parallel-safe задачей (S).

- **L1:** Исправлен вводящий в заблуждение комментарий в `src/admin/app.py` про порядок middleware. Реальный порядок (Starlette: последний add_middleware = outermost) теперь описан точно. Middleware-стек оставлен без изменений (минимальный риск).
- **L2:** `server_default="now()"` → `server_default=func.now()` в `Broadcast` и `BroadcastDelivery`. Единообразие с остальными моделями, безопасность для autogenerate. Миграция не нужна (DDL уже правильный).
- **L3:** Две захардкоженные строки из `events.py` вынесены в `texts.py` (`CATEGORY_PAGE_TITLE`, `PREDICTION_YOUR_CHOICE`) + подстановка через `safe_format`. Соответствует `docs/08-conventions.md` и CLAUDE.md.

Все правки независимы. Тесты events-роутера продолжают проходить (ассерты на подстроки остались валидны).

## Коммиты и PR
- PR #162 (auto-merge включён)
- Один коммит: 585ebcf

## Изменённые файлы
```
* src/admin/app.py
* src/bot/routers/events.py
* src/bot/texts.py
* src/shared/models/broadcast.py
* src/shared/models/broadcast_delivery.py
```

## Как воспроизвести / запустить
```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/shared src/bot src/admin
uv run pytest tests/unit/bot/routers/test_events_handler.py -q
# (опционально) проверить в админке, что middleware-комментарий больше не врёт
```

## Что не сделано (если применимо)
- Для L1 не стал убирать `ProxyHeadersMiddleware` (оставил только правку комментария, как рекомендовано в задаче при неуверенности). uvicorn `--proxy-headers` уже делает основную работу.

## Открытые вопросы для проектировщика
Нет.

## Предложение для PROJECT_STATUS.md
```markdown
- 2026-05-31 — **TASK-087 закрыт (parallel-safe, S):** три Low-чистки из аудита (L1: комментарий middleware в app.py; L2: func.now() в двух broadcast-моделях; L3: вынос 2 строк в texts.py). PR #162.
```

## Метрики (опционально)
- Изменено 5 файлов, +19/-11 строк
- Время: ~25 минут (идеально для параллельной задачи)
