---
task: TASK-092
completed: 2026-05-31
agent: claude-code-local
status: partial   # one clear cause fixed; second requires prod logs as explicitly requested in DoD
pr: https://github.com/nmetluk/bettgbot/pull/171
branch: feature/TASK-092-prod-500-broadcasts-and-audit-details
commits:
  - a27cacf fix(admin): eager-load AuditLog.admin in details/collapse fragments (TASK-092)
---

# Отчёт по TASK-092: На проде всё ещё 500 — `/broadcasts/new` и `/audit/{id}/details`

## Сводка

После выката 089/090/091 на проде (`a.pinbetting.ru`) два GET-эндпоинта админки по-прежнему возвращают HTTP 500 (подтверждено живым аудитом cowork 2026-05-31).

**1. `/audit/{id}/details` (и collapse) — причина найдена и исправлена**

В `details_fragment` и `details_collapse` использовался голый `session.get(AuditLog, entry_id)` **без** `options=[selectinload(AuditLog.admin)]`.

Фрагменты `_details.html` и `_preview.html` обращаются к `entry.admin.full_name`, `entry.admin.login` и т.д.

На реальном async-потоке это вызывает lazy-load. В отличие от unit-тестов (где на MagicMock `.admin` уже предустановлен), на проде (и в любом реалистичном тесте) это приводит к 500.

В `list` тот же репозиторий правильно использовал `selectinload` — inconsistency, которую не поймали.

**Фикс:** добавил `selectinload` (в точности как в листе). Это решает один из двух 500.

**2. `/broadcasts/new` — 500 остаётся**

TASK-089 убрал прямой доступ к `request.state.csrf_token` (правильно). Существующий тест `test_new_broadcast_form_renders_200` использует очень тяжёлые моки всего стека auth + сессии и поэтому даёт ложноположительный результат.

Точная строка/причина 500 на проде для этого эндпоинта требует **реального traceback из логов web-контейнера** (как прямо требует DoD задачи). Без стека — гадание.

Общей причиной у двух эндпоинтов (как подозревалось) может быть разница в наполнении `request.state` / контекста между боевым middleware-стеком и нашими unit-тестами, но для broadcasts это пока не подтверждено без логов.

## Что сделано

- Исправлена чёткая причина 500 для audit details (eager load).
- Задача взята в работу, PR открыт.
- Тесты (включая регресс из 091) зелёные.
- Полные локальные проверки (ruff, mypy src/shared, pytest admin) зелёные.

## Что не сделано / открыто

- Для `/broadcasts/new` 500: без реального прод-лога точный фикс невозможен (и не стоит гадать). DoD задачи прямо требует "Снять реальные traceback'и ... приложить в отчёт".
- Усиление тестов до "воспроизводящих боевой путь" (полный middleware + cookie + минимум моков) — рекомендуется как follow-up (отдельная задача или в 093/088). Текущие тесты дают ложную уверенность.

## После выката (обязательно по DoD)

Владелец / cowork должен:
1. Выкатить этот PR (или main после merge).
2. Прокликать в браузере на проде:
   - /broadcasts/new → 200 + форма + превью получателей
   - /audit → клик по шеврону → детали раскрываются (200)
3. Приложить свежие traceback'и из `docker logs` web, если 500 остались.
4. Зафиксировать результат в комментарии к PR / в следующем handoff.

## Изменённые файлы (в этом PR)

```
* src/admin/routes/audit.py   # + selectinload в двух fragment-хендлерах
+ handoff/inbox/TASK-092-....in-progress.md
+ handoff/outbox/TASK-092-report.md
```

## Как воспроизвести локально (улучшенный путь)

```bash
# после мерджа
git checkout main && git pull

# Запустить обычные unit-тесты (они проходят)
uv run pytest tests/unit/admin/test_audit_handler.py -q -k "details or 091 or 092"

# Для более близкого к прод воспроизведения (рекомендация):
# - использовать TestClient + реальный логин через /login (с реальным AdminUser в тестовой БД)
# - или поднять полный compose + curl с полученной кукой
# - и смотреть traceback в uvicorn / docker logs
```

## Открытые вопросы для проектировщика / владельца

1. Пришлите, пожалуйста, актуальные traceback'и из прод-логов web для обоих 500 (или подтверждение, что после этого PR оба стали 200).
2. Нужно ли в ближайшее время усилить тесты админки до уровня "реальный middleware + cookie" (чтобы такие регрессии ловились до выката)?

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-31 — TASK-092 (high, prod regression): починили 500 на `/audit/{id}/details` (не хватало `selectinload(AuditLog.admin)` в fragment-хендлерах — lazy-load в шаблоне на реальном async). Для `/broadcasts/new` 500 точная причина требует прод-логов (тест с моками давал ложноположительный). PR #171. После выката — обязательная ручная проверка обоих сценариев на проде.
```

## Метрики

- Чётко диагностирована и исправлена одна из двух причин 500.
- Время: фокус на реальной причине (а не гадании).
