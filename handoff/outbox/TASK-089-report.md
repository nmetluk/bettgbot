---
task: TASK-089
completed: 2026-05-31
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/165
branch: feature/TASK-089-broadcasts-new-500
commits:
  - 81a505b fix(admin): resolve 500 on GET /broadcasts/new by standardizing csrf_token to request.state pattern
---

# Отчёт по TASK-089: Починить форму создания рассылки — `/broadcasts/new` отдаёт HTTP 500

## Сводка

Исправлена критическая 500-ошибка на `GET /broadcasts/new`, из-за которой форма создания рассылок была недоступна в проде (в то время как список `/broadcasts` работал, и весь функционал рассылок (TASK-061) был заблокирован).

Корневая причина: `broadcasts.py` + `form.html` были **единственным** местом в админке, использовавшим устаревший/нестандартный способ работы с CSRF — прямой доступ `request.state.csrf_token` в хендлере (с передачей в контекст) + голый `{{ csrf_token }}` в шаблоне. Все остальные формы используют защитный паттерн `{{ request.state.csrf_token if request.state and request.state.csrf_token is defined else '' }}` (гарантируется `CsrfTokenMiddleware` для GET под auth).

Привели broadcasts в соответствие с остальной админкой (TASK-022+), убрали потенциальную точку падения. HTMX-превью (`/preview-count`) и остальная логика формы не затронуты.

## Изменённые файлы

```
R  handoff/inbox/TASK-089-broadcasts-new-500.md -> handoff/inbox/TASK-089-broadcasts-new-500.in-progress.md
* src/admin/routes/broadcasts.py            # убраны 2 unsafe доступа к request.state.csrf_token (new + error path)
* src/admin/templates/broadcasts/form.html  # csrf input теперь использует безопасный guard (как в _layout_shell.html)
* tests/unit/admin/test_broadcast_routes.py # добавлен regression-тест test_new_broadcast_form_renders_200 (проверяет отсутствие 5xx + safe pattern)
```

## Как воспроизвести / запустить

```bash
# после мерджа
git checkout main && git pull

# поднять infra (если нужно)
make up

# запустить админку
make admin   # uvicorn на :8000

# в браузере (или curl с валидной bb_admin_session-кукой):
# GET http://127.0.0.1:8000/broadcasts/new → 200 + форма с сегментами, категориями, csrf input, #preview-count

# тесты
uv run pytest tests/unit/admin/test_broadcast_routes.py -q -k "broadcast"
```

## Что не сделано (если применимо)

Ничего не урезано. Полностью закрыт скоуп (воспроизведение, фикс, тест, зелёные проверки, PR+report+archive по протоколу).

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-31 — **TASK-089 закрыт:** починили 500 на `GET /broadcasts/new` (причина — нестандартный доступ к csrf_token в handler'е broadcasts; приведено к единому безопасному паттерну `request.state` + guard в шаблоне). Добавлен регресс-тест. PR #165.
```

## Метрики (опционально)

- Тестов добавлено: 1 (регресс + smoke рендера формы)
- Время на выполнение: ~1.5ч (включая диагностику без полного стека в sandbox)
