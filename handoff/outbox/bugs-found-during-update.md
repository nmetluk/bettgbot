# Баги, найденные при обновлении продакшена (2026-05-30)

## Обновление с 889d2a7 → 97e7c88 (и далее)

### 1. **Проблема с миграциями** — ✅ ИСПРАВЛЕНО

**Симптом:** `FAILED: Can't locate revision identified by '0004_dispatch_log_indexes'`

**Причина:** Миграция была переименована из `0004_dispatch_log_indexes.py` в `0004_reminder_dispatch_log_indexes.py`, но в БД `alembic_version` всё ещё содержало старое имя.

**Решение:** Вручную обновил версию в БД:
```sql
UPDATE alembic_version SET version_num = '0004_reminder_dispatch_log_indexes' WHERE version_num = '0004_dispatch_log_indexes';
```

**Рекомендация:** При переименовании миграций нужно либо:
- Создать новую миграцию, которая обновляет `alembic_version`
- Или обеспечить, что переименование идёт через обычный путь alembic (через `downgrade` + `upgrade`)

---

### 2. **ADMIN_SECRET_KEY и ADMIN_CSRF_SECRET не передавались в bot** — ✅ ИСПРАВЛЕНО

**Симптом:** Bot не стартовал с ошибкой:
```
pydantic_core._pydantic_core.ValidationError: 2 validation errors for AdminSettings
secret_key: Field required
csrf_secret: Field required
```

**Причина:** В `docker-compose.yml` сервис `bot` не получал переменные `ADMIN_SECRET_KEY` и `ADMIN_CSRF_SECRET`, но новый код в `src/shared/config.py` начал их требовать.

**Решение:** Добавил переменные в compose-файл (коммит `5f00aec`).

**Рекомендация:** При добавлении новых обязательных полей в Settings:
- Проверить все сервисы, которые используют этот конфиг
- Добавить значения по умолчанию или сделать поля опциональными с явной ошибкой при отсутствии

---

### 3. **Naive vs Aware datetime в репозитории** — ✅ ИСПРАВЛЕНО

**Симптом:** `GET /events` возвращал 500:
```
TypeError: can't compare offset-naive and offset-aware datetimes
```

**Причина:** В `src/shared/repositories/event.py:187` сравнивались:
- `Event.starts_at` (TIMESTAMP WITHOUT TIME ZONE — naive)
- `datetime.now(tz=UTC)` (aware)

**Решение:** Заменил на `datetime.utcnow()` для naive comparison (коммит `1894033`).

**Рекомендация:** Определить стратегию работы с timezone в проекте:
- Либо везде использовать aware datetime (тогда нужно изменить тип колонок в БД)
- Либо везде naive UTC (тогда нужно запретить использование `tz=UTC` в коде)

---

### 4. **Naive vs Aware datetime в шаблонах** — ✅ ИСПРАВЛЕНО

**Симптом:** `GET /events` всё ещё 500 после исправления #3:
```
{% elif event.predictions_close_at.replace(tzinfo=None) > now() %}
TypeError: can't compare offset-naive and offset-aware datetimes
```

**Причина:** В `src/admin/app.py:43` `now()` возвращал `datetime.now(tz=UTC)` (aware), а в шаблоне сравнивали с naive datetime.

**Решение:**
- Изменил `now()` на `datetime.utcnow` (naive)
- Убрал `.replace(tzinfo=None)` из шаблона

Коммит `34b8ead`.

**Рекомендация:** См. #3 — нужна единая стратегия по timezone.

---

## Общая рекомендация

Все четыре бага связаны с отсутствием единых стандартов:
1. Работа с миграциями и их переименование
2. Передача переменных окружения между сервисами
3. Работа с datetime (naive vs aware)

Предлагаю добавить в `docs/08-conventions.md` разделы:
- Как работать с миграциями (особенно переименование)
- Как работать с datetime (выбрать одну стратегию)
- Чек-лист при добавлении новых полей в Settings

---

## Сервера после обновления

- **Admin** (5.188.88.78): https://a.pinbetting.ru — ✅ работает
- **Bot** (195.133.26.200): ✅ работает

*Временный override на Bot-сервере:* `/tmp/docker-compose.temp.yml` — web запущен с локальной БД/Redis для healthcheck-зависимости bot. Нужно решить, как убрать эту зависимость на Bot-сервере.
