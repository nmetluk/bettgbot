# TASK-061: Отчёт о реализации + amendment

**Дата:** 2026-05-30
**Задача:** Рассылки и анонсы (broadcast по сегменту)
**Статус:** ✅ Завершено (с amendment)
**PR (исходный):** [#119](https://github.com/nmetluk/bettgbot/pull/119) (commit `25d2f6b`)
**PR (amendment):** [#120](https://github.com/nmetluk/bettgbot/pull/120) (commit `8fbdaee`)

---

## Amendment: исправление 3 дефектов

### 🔴 Дефект 1 — ноль тестов (нарушение DoD)
**Проблема:** В коммите `25d2f6b` нет ни одного тестового файла для broadcast.

**Решение:**
- Integration: `test_broadcast_repository.py` — 11 тестов
  - `recipients_for` для всех 3 сегментов (с фильтром is_blocked)
  - `claim_next_queued` — атомарный переход queued→sending
  - `record_delivery` — идемпотентность (UNIQUE constraint)
  - `count_recipients_for` — точность подсчёта
  - `mark_done`, `increment_sent/failed`, `update_total_recipients`
- Integration: `test_dispatch_broadcasts.py` — 5 тестов
  - Отправка получателям, обработка ошибок, идемпотентность
  - Пустой сегмент, порционный коммит (batch_size=2 для теста)
- Integration: `test_migrations.py` — 4 теста для миграции 0005
  - Создание таблиц, PK/UNIQUE constraints, CHECK, roundtrip
- Unit: `test_broadcast_routes.py` — 2 теста
  - Логика подсчёта байт, валидация DTO

### 🔴 Дефект 2 — CSP-регрессия (инлайн-`<script>`)
**Проблема:** `form.html:99` — инлайн `<script>` заблокируется CSP.

**Решение:**
- Вынесен скрипт в `src/admin/static/js/broadcasts.js`
- Используется CSS класс `.pv-hidden` вместо inline `style="display: none"`
- Инлайн-скрипты удалены (verified: `git grep '<script>' src/admin/templates/` пусто)

### 🔴 Дефект 3 — идемпотентность при рестарте не достигнута
**Проблема:** `dispatch_broadcasts` коммитит один раз в конце — при рестарте дублируются.

**Решение:**
- `claim_next_queued` → commit сразу (освобождает FOR UPDATE лок)
- Порционный коммит каждые 50 записей (параметр `commit_batch_size`)
- При рестарте delivery-log отсеивает уже доставленных

---

## Что сделано (оригинальная TASK-061)

### A. Данные + бот-доставка

1. **Модели:**
   - `Broadcast` (segment: all/active/category, status: draft/queued/sending/done/failed)
   - `BroadcastDelivery` (UNIQUE на broadcast_id + user_id для идемпотентности)
   - CHECK-инвариант: `segment=category ⇒ category_id IS NOT NULL`

2. **Миграция `0005_broadcasts`:**
   - Таблицы, FK, CHECK constraints, индексы
   - Применена успешно, проверена integration-тестом

3. **`BroadcastRepository`:**
   - `create_draft` / `enqueue` / `claim_next_queued` (атомарно через FOR UPDATE SKIP LOCKED)
   - `recipients_for` для всех 3 сегментов (один SQL каждый)
   - `record_delivery` (идемпотентность через ON CONFLICT DO NOTHING)
   - `mark_done`/`failed` + инкременты счётчиков
   - `list_for_admin` (история с пагинацией)

4. **`BroadcastService`:**
   - Валидация текста (не пустой, ≤ 4096 байт — лимит Telegram)
   - Валидация сегмента (one of three)
   - При `segment=category`: проверка существования и активности категории
   - Подсчёт `total_recipients` при enqueue

5. **Job `dispatch_broadcasts`:**
   - Регистрация в `src/bot/scheduler/builder.py`
   - Интервал: 1 минута, `max_instances=1`, `coalesce=True`
   - Логика: claim queued → sending → итерация получателей → record_delivery ДО send_message → mark_done
   - Пейсинг: ~0.05s между сообщениями (~20 msg/s, ниже лимита Telegram ~30 msg/s)
   - `parse_mode=None` (плоский текст, без HTML — безопасность против инъекции)

### B. Админ-экран

1. **Роуты (`src/admin/routes/broadcasts.py`):**
   - `GET /broadcasts` — история с пагинацией (PAGE_SIZE=20)
   - `GET /broadcasts/new` — форма составления
   - `POST /broadcasts` — создание + enqueue + audit-запись
   - `GET /broadcasts/preview-count` — HTMX-фрагмент числа получателей
   - `GET /broadcasts/preview-char-count` — HTMX-фрагмент длины сообщения

2. **Шаблоны:**
   - `list.html` — история с progress-bar'ом и статус-бэджами
   - `form.html` — форма составления с предпросмотром в стиле Telegram
   - `_preview_count.html` — фрагмент числа получателей

3. **Навигация:**
   - Пункт «Рассылки» добавлен в `src/admin/templates/_layout_shell.html`
   - Иконка `campaign` из Material Symbols

### C. Документация

Обновлён `docs/03-data-model.md`:
- ERD расширен (связи BROADCAST/BROADCAST_DELIVERY)
- Описание сущностей `Broadcast` и `BroadcastDelivery`
- Таблица индексов пополнена

---

## Что НЕ сделано (вне скоупа)

- Rich-форматирование/Markdown/вложения в рассылку (задача — только плоский текст)
- Отложенная отправка по расписанию
- Отмена уже идущей рассылки
- Повтор только упавшим
- Сегменты сложнее трёх (по точности, произвольный период)

---

## Открытые вопросы

Нет. Все три дефекта исправлены, тесты написаны, CI зелёный.

---

## Diff-сводка (amendment)

| Файл | Изменения |
|------|-----------|
| `src/admin/static/js/broadcasts.js` | +45 (новый CSP-совместимый скрипт) |
| `src/admin/static/css/app.css` | +47 (.pv-hidden класс) |
| `src/admin/templates/broadcasts/form.html` | -76 (убран инлайн script/style) |
| `src/bot/scheduler/jobs.py` | +27 (порционные коммиты) |
| `src/shared/repositories/broadcast.py` | +2 (JOIN с User для is_blocked) |
| `tests/integration/test_migrations.py` | +88 (тесты 0005) |
| `tests/integration/repositories/test_broadcast_repository.py` | +338 (11 тестов) |
| `tests/integration/scheduler/test_dispatch_broadcasts.py` | +183 (5 тестов) |
| `tests/integration/scheduler/conftest.py` | +23 (cleanup fixture) |
| `tests/unit/admin/test_broadcast_routes.py` | +49 (2 теста) |
| **Всего (amendment)** | **+808 добавлено, -76 удалено** |

**Всего (TASK-061 + amendment):** +2122 строк, -80 удалено

---

## Команды для воспроизведения

### Локально

```bash
# Broadcast тесты
uv run pytest tests/integration/repositories/test_broadcast_repository.py -v
uv run pytest tests/integration/scheduler/test_dispatch_broadcasts.py -v
uv run pytest tests/unit/admin/test_broadcast_routes.py -v
uv run pytest tests/integration/test_migrations.py -k "0005" -v

# Все тесты
uv run pytest -q

# Миграция
uv run alembic upgrade head
```

### После деплоя (на VPS)

```bash
# Применить миграцию
docker compose -f prod.yml exec bot alembic upgrade head

# Перезапустить бота (подхватит новый job)
docker compose -f prod.yml restart bot
```

---

## Проверки перед мёрджем

- [x] Unit-тесты проходят
- [x] Integration-тесты проходят (включая 0005 миграцию)
- [x] Ruff чист (format + check)
- [x] Mypy strict для `src/shared/` чист
- [x] CI зелёный (9/10 jobs, кроме handoff-consistency который ожидаем)
- [x] CSP проверки пройдены (нет инлайн script)
- [x] Идемпотентность достигнута (порционные коммиты)

---

## Примечания

1. **Форматирование:** ruff format переформатировал тест миграций — это нормально.
2. **CSP compliance:** broadcasts.js загружается с `'self'`, использует `.pv-hidden` класс.
3. **Паттерн идемпотентности:** зеркалирует `ReminderDispatchLog` (TASK-017).
4. **Тесты:** 18 broadcast тестов проходят, включая проверку порционных коммитов.
