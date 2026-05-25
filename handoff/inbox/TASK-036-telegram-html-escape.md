---
id: TASK-036
created: 2026-05-25
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: M
---

# TASK-036: HTML-escape всех user/admin-supplied значений в Telegram-сообщениях

## Контекст

Аудит MVP 2026-05-25, находка **C-04 (Critical, CWE-79)**. Бот глобально установлен `ParseMode.HTML` (`src/bot/main.py:42-43`). Все шаблоны в `src/bot/texts.py` (`EVENT_CARD`, `MY_ROW_ACTIVE/ARCHIVE`, `PREDICT_*`, `WELCOME_NEW_REGISTERED`, `REMINDER_NOTIFICATION`) собираются через `.format(title=event.title, label=outcome.label, first_name=user.first_name, ...)` **без `html.escape`**. Admin вводит `Match: A vs B<a href="https://evil.com">tap</a>` → массовая phishing-рассылка через офф-канал.

Дополнительный риск — DoS: title с непарным `<` валит aiogram в `Bad Request: can't parse entities`, событие пропадает из каталога и сломаны напоминания.

## Цель

Любое user/admin-supplied значение, попадающее в текст Telegram-сообщения, проходит через `aiogram.html.quote()` (или `html.escape(..., quote=False)`). Защита layered:
1. Wrapper-функция `safe_format(template, **kwargs)` экранирует значения kwargs перед `.format()`.
2. Серверная валидация формы события / outcome / категории запрещает символы `<` и `>` в текстовых полях (defense in depth, прямой пользовательский UX).

## Definition of Done

- [ ] `src/bot/_text_safety.py` (новый) экспортирует `safe_format(template: str, **values: str) -> str` — экранирует каждое значение через `html.escape(value, quote=False)` перед `template.format(...)`.
- [ ] Все handler'ы и job'ы (`src/bot/routers/{start,events,prediction,my,reminders}.py`, `src/bot/scheduler/jobs.py`) переписаны на `safe_format(...)` вместо `.format(...)` для шаблонов с `<b>`/`<a>`.
- [ ] `EventService.create_event` / `update_event` (`src/shared/services/event.py`) валидируют `title`, `description` через regex `r"[<>]"` → `EventInvalidContentError(reason: Literal["html_chars"])`.
- [ ] Аналогично `add_outcome` / `update_outcome` для `label`.
- [ ] `CategoryService.create_category` / `update_category` для `name`.
- [ ] `UserService.register_or_authenticate` — `first_name`/`last_name` из TG-контакта НЕ валидирует (приходит из Telegram, не админский ввод), но `safe_format` всё равно их экранирует.
- [ ] Admin form-handler'ы (`src/admin/routes/{events,outcomes,categories}.py`) обрабатывают `EventInvalidContentError` → re-render формы с ошибкой "Символы `<` и `>` не допускаются".
- [ ] Unit-тесты `tests/unit/bot/test_text_safety.py`:
  - `safe_format("<b>{title}</b>", title="A<b>X</b>B")` → `"<b>A&lt;b&gt;X&lt;/b&gt;B</b>"`.
  - `safe_format` с непарным `<` не падает.
- [ ] Integration-тест: создать event с `title="A<script>"` через API → 409 / валидационная ошибка.
- [ ] Unit-тест в `test_events_handler.py`: ивент с html в title рендерится как escape'нутый текст.
- [ ] PR в GitHub, имя `TASK-036: HTML-escape user content in Telegram messages`.
- [ ] Отчёт в `handoff/outbox/TASK-036-report.md`.
- [ ] **🚨 Move-семантика inbox→archive**.
- [ ] **🚨 `make backup` после merge в main**.

## Артефакты

- `+ src/bot/_text_safety.py` — новый
- `* src/bot/routers/*.py` — все, где `texts.X.format(...)`
- `* src/bot/scheduler/jobs.py` — `REMINDER_NOTIFICATION`
- `* src/shared/exceptions.py` — `EventInvalidContentError`, `OutcomeInvalidContentError`, `CategoryInvalidContentError` (один общий `InvalidContentError` с `reason: Literal["html_chars", ...]` лучше)
- `* src/shared/services/{event,category}.py` — валидация
- `* src/admin/routes/{events,outcomes,categories}.py` — обработка
- `+ tests/unit/bot/test_text_safety.py` — новый

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — секция C-04
- aiogram html utils: https://docs.aiogram.dev/en/stable/api/types/message.html

## Подсказки

- `aiogram.utils.markdown.html_decoration.quote` тоже работает, но `html.escape(s, quote=False)` из stdlib проще.
- Не экранируй `humanized` в `REMINDERS_ADDED` — это контролируемый внутренний текст, не user input.
- Описание события (`description_block`) обёрнуто в `\n\n{event.description}` — после safe_format экранирование `\n\n` не нужно, но `event.description` — нужно. Передавай в kwarg, не в template.
- При написании регулярки `r"[<>]"` — учти, что валидатор должен работать на multi-line text (`description`); `re.search` без `re.DOTALL` достаточно.
