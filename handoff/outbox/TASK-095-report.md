---
task: TASK-095
completed: 2026-06-01
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/186
branch: feature/TASK-095-broadcasts-form-styling
commits:
  - 7992952 style(admin): bring /broadcasts/new form to v2 design system (TASK-095)
  - (follow-up) chore(handoff): archive TASK-095 and add report
---
# Отчёт по TASK-095: Привести форму рассылки `/broadcasts/new` к дизайн-системе

## Сводка

Приведена форма создания рассылки `/broadcasts/new` (и связанная мелочь по табам событий) к v2 дизайн-системе. Форма использовала несуществующие классы `pv-form-*` (остаток от TASK-061, не вошедший в скоуп TASK-088), из-за чего выглядала «голым HTML». Сегмент-выбор и preview-bubble уже имели CSS, но не были обёрнуты в card-body и консистентные field-лейблы.

Переписал на существующие классы (pv-stack + pv-field-label + pv-input/pv-textarea/pv-select + pv-field-help + pv-card-body + pv-row), в точности как в `categories/form.html` и `events/form.html`. Никаких новых CSS-классов не потребовалось. Все HTMX, id для JS, guard-выражения, тексты и тестовые ассерты сохранены.

Дополнительно (мелочь из задачи): исправил цвет активной вкладки «Данные» в карточке события — с `--pv-accent` (красный) на `--pv-fg` (тёмный текст), как требовала спека 088; подчёркивание accent осталось.

Все проверки зелёные (ruff, mypy src/shared, полный pytest).

## Изменённые файлы

```
* src/admin/templates/broadcasts/form.html     # основной перевод на v2 классы + pv-card-body
* src/admin/templates/events/form.html           # мелочь: .pv-tab.active color: accent → fg
+ handoff/outbox/TASK-095-report.md
+ handoff/archive/TASK-095-broadcasts-form-styling/task.md
```

( transient: handoff/inbox/TASK-095-....md удалён, .in-progress удалён при archive-коммите )

## Как воспроизвести / запустить

```bash
# локально (dev)
make admin
# или
uv run uvicorn src.admin.app:app --reload --port 8000

# открыть в браузере
open http://localhost:8000/broadcasts/new   # (или /login сначала)

# проверить:
# - форма использует pv-field-label, pv-input/pv-textarea/pv-select, pv-stack, pv-card-body
# - сегменты — красивые радио-карточки с hover
# - предпросмотр — bubble как в мессенджере
# - счётчик символов и получателей работают (HTMX)
# - категория показывается только при segment=category
# - submit / cancel кнопки в стиле pv-btn
# - активная вкладка на /events/{id} — тёмный текст + accent underline (не красный)

# тесты
uv run pytest tests/unit/admin/test_broadcast_routes.py tests/unit/admin/ -q
uv run ruff check src tests
uv run mypy src/shared
```

## Что не сделано (если применимо)

Ничего не урезано. Полностью по DoD.

Inline <style> в events/form.html оставлен (дублирует глобальные .pv-tab), только цвет .active поправлен — рефакторинг всего блока в отдельный CSS-файл вынесен за скоуп (YAGNI для этой задачи).

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-06-01 — **TASK-095 закрыт.** Форма `/broadcasts/new` приведена к v2 дизайн-системе (pv-stack/field-label/input/textarea/select + card-body); мелочь по цвету активной вкладки событий. PR #186. (последний артефакт дизайна из 088)
```

## Метрики (опционально)

- Тестов добавлено: 0 (шаблон, поведение покрыто существующими)
- Время на выполнение: ~35 мин (анализ + правка + полные прогоны + handoff)
- CI: ожидается зелёный (handoff-consistency включит проверку archive + report)