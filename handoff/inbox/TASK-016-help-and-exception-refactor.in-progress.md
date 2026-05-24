---
id: TASK-016
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md (раздел «Справка»)
  - src/shared/exceptions.py
  - src/shared/services/reminder.py
  - src/bot/routers/reminders.py
  - src/bot/texts.py (HELP уже готов)
priority: normal
estimate: M
---

# TASK-016: `/help` handler + рефакторинг `InvalidReminderOffsetsError.reason`

## Контекст

Шестой и предпоследний пользовательский handler — `/help`. Текст справки `texts.HELP` уже готов с TASK-010 ([`src/bot/texts.py`](../../src/bot/texts.py)). Осталось:

1. Подключить handler в [`src/bot/routers/help.py`](../../src/bot/routers/help.py) — сейчас там пустой скелет с комментарием «реальные handler'ы в TASK-016».
2. Заодно сделать рефакторинг `InvalidReminderOffsetsError` под review TASK-015 — добавить `reason: Literal[...]` чтобы handler в `reminders.py` не делал fragile подстрочный match (open question Q1 → change).

Размер задачи **M**: основная работа — Step 0 (рефакторинг), Step 1 (cmd_help) тривиален.

Источники:

- [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) — раздел «Справка» (статический текст, без edge cases).
- [`src/shared/exceptions.py`](../../src/shared/exceptions.py) — `InvalidReminderOffsetsError`. Пример паттерна с `reason: Literal` уже есть в `EventNotPredictableError(reason: Literal["not_found", "not_published", "archived"])` из TASK-009.
- [`src/shared/services/reminder.py`](../../src/shared/services/reminder.py) — `_validate_offsets` поднимает `InvalidReminderOffsetsError` тремя `raise`-ветками.
- [`src/bot/routers/reminders.py`](../../src/bot/routers/reminders.py) — `_format_error` сейчас сопоставляет по `str(exc)` (`"too many"` / `"duplicate"` / `"below minimum"`) с текстами `REMINDERS_ERR_*`.
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — строка 2026-05-24 про этот рефакторинг.

## Перед стартом — pre-task cleanup PR

В origin/main `8c9a00d` — last commit. **Working tree этой машины (где cowork писал review-артефакты) содержит:**

- `state/PROJECT_STATUS.md` — закрытие TASK-015, новый «Следующий шаг» TASK-016.
- `state/DECISIONS.md` — 3 новых строки сверху (exception refactor, archive-check для cowork, MAX_OFFSET_MINUTES граница).
- `handoff/README.md` — новый параграф «Проверки перед публикацией задачи».
- Новая сессия `sessions/2026-05-24-01-task-015-review/`.
- `handoff/inbox/TASK-016-help-and-exception-refactor.md` — эта задача.

Branch: `chore/post-TASK-015-cowork-cleanup`, PR `chore(handoff): post-TASK-015 review by cowork`. После merge — `feature/TASK-016-help-and-exception-refactor`.

## Цель

`/help` отвечает текстом справки + клавиатурой главного меню. `InvalidReminderOffsetsError` несёт типизированный `reason`, handler ловит по reason, не по подстроке. Все 221 существующих тестов остаются зелёными.

## Definition of Done

### Step 0 — Рефакторинг `InvalidReminderOffsetsError`

- [ ] **В `src/shared/exceptions.py`** изменить `InvalidReminderOffsetsError`:
  ```python
  from typing import Literal

  InvalidReminderOffsetsReason = Literal["too_many", "duplicate", "below_minimum"]


  class InvalidReminderOffsetsError(DomainError):
      """Невалидный список offsets: > 5 / < 5 минут / дубликаты.

      `reason` — типизированный код причины, handler ловит по нему,
      а не по подстроке `str(exc)`.
      """

      def __init__(
          self,
          message: str = "invalid reminder offsets",
          *,
          reason: InvalidReminderOffsetsReason,
      ) -> None:
          super().__init__(message)
          self.reason: InvalidReminderOffsetsReason = reason
  ```
  - Сигнатура аналогична `EventNotPredictableError(reason=...)` из TASK-009.
  - Импорт `Literal` уже есть в `exceptions.py` (см. `EventNotPredictableError`).
- [ ] **В `src/shared/services/reminder.py`** обновить `_validate_offsets`:
  ```python
  @staticmethod
  def _validate_offsets(offsets: list[int]) -> None:
      if len(offsets) > _MAX_OFFSETS:
          raise InvalidReminderOffsetsError(
              f"too many offsets: {len(offsets)} (max {_MAX_OFFSETS})",
              reason="too_many",
          )
      if len(set(offsets)) != len(offsets):
          raise InvalidReminderOffsetsError("duplicate offsets", reason="duplicate")
      for value in offsets:
          if value < _MIN_OFFSET_MINUTES:
              raise InvalidReminderOffsetsError(
                  f"offset {value} below minimum {_MIN_OFFSET_MINUTES}",
                  reason="below_minimum",
              )
  ```
  - Сообщения для логов оставляем человекочитаемыми (помогают дебагу). `reason` — машинный код для handler'а.
- [ ] **В `src/bot/routers/reminders.py`** переписать `_format_error`:
  ```python
  def _format_error(exc: InvalidReminderOffsetsError) -> str:
      match exc.reason:
          case "too_many":
              return texts.REMINDERS_ERR_TOO_MANY
          case "duplicate":
              return texts.REMINDERS_ERR_DUPLICATE
          case "below_minimum":
              return texts.REMINDERS_ERR_BELOW_MINIMUM
  ```
  - `match`-выражение исчерпывающее по `Literal[...]` — mypy validate. Если в будущем добавится новый `reason`, mypy подскажет, что нужно расширить `match`.
- [ ] **Обновить `tests/unit/bot/routers/test_reminders_handler.py`** — там есть тесты на ошибки. Они моделируют `InvalidReminderOffsetsError` без `reason` — сейчас сломаются. Переписать на `InvalidReminderOffsetsError("...", reason="too_many")` (и для других веток).
- [ ] **Integration-тесты `ReminderService`** (если такие есть в `tests/integration/services/`) — проверь, что они тоже валидны под новую сигнатуру. Сообщения остались — должны пройти. `reason` integration-тесты обычно не проверяют, так что правок не понадобится.

### Step 1 — `cmd_help`

- [ ] **В `src/bot/routers/help.py`** реализовать:
  ```python
  """Router `/help` — статическая справка (TASK-016)."""

  from __future__ import annotations

  from aiogram import F, Router
  from aiogram.filters import Command
  from aiogram.types import Message
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.shared.models import User

  from .. import keyboards, texts
  from ..auth import require_active_user

  __all__ = ["router"]


  router = Router(name="help")


  @router.message(Command("help"))
  @router.message(F.text == "ℹ️ Справка")
  @require_active_user
  async def cmd_help(
      message: Message,
      user: User | None,  # noqa: ARG001  # декоратор использует
      session: AsyncSession,  # noqa: ARG001  # стандартный DI
  ) -> None:
      """Отвечает статическим текстом справки + клавиатура главного меню."""
      await message.answer(texts.HELP, reply_markup=keyboards.main_menu())
  ```
- [ ] **Опционально:** убрать `session: AsyncSession` из сигнатуры, если он не нужен и aiogram middleware не требует его наличия. Проверь: остальные handler'ы (`cmd_my`, `cmd_reminders`) принимают `session` — оставь для единообразия, даже если внутри не используется. `noqa: ARG001` для `user`+`session` подавляет ruff-предупреждение про неиспользуемые аргументы.

### Step 2 — Unit-тесты

`tests/unit/bot/routers/test_help_handler.py` — mock-based, ~3 теста:

- [ ] `test_cmd_help_unauthenticated_sends_need_start` (декоратор)
- [ ] `test_cmd_help_blocked_sends_access_denied` (декоратор)
- [ ] `test_cmd_help_active_user_sends_help_text_with_main_menu`
  - Проверяет: `message.answer.assert_awaited_once()`, `args[0] == texts.HELP`, `kwargs["reply_markup"]` — `ReplyKeyboardMarkup` (главное меню).

### Step 3 — Регресс по существующим тестам

- [ ] `tests/unit/bot/routers/test_reminders_handler.py` — после Step 0 будут падать тесты с `InvalidReminderOffsetsError("too many offsets")` без `reason`. Фикси на новую сигнатуру.
- [ ] Если в `tests/integration/services/test_reminder_service.py` (или подобном) есть тесты на исключение — проверь, что reason устанавливается правильно для каждой ветки. Желательно добавить `assert exc.reason == "too_many"` и т.д. — это закрепит контракт.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный. Особенно проверить, что `match`-выражение в `_format_error` mypy считает exhaustive.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit-тесты, включая 3 новых для help.
- [ ] `uv run pytest tests/integration -m integration` — без падений.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):** `/help` или «ℹ️ Справка» → текст справки + клавиатура. Никаких ошибок в логах.
- [ ] Ветка `feature/TASK-016-help-and-exception-refactor`, Conventional Commits:
  - `refactor(shared): InvalidReminderOffsetsError + reason: Literal`
  - `refactor(bot): reminders error handler через match-reason`
  - `feat(bot): help router — cmd_help (статический текст)`
  - `test(bot): help handler tests + регресс reminders error tests`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-016-report.md`, задача → `handoff/archive/TASK-016-help-and-exception-refactor/task.md`.

## Артефакты

```
* src/shared/exceptions.py                          # InvalidReminderOffsetsError(reason=Literal)
* src/shared/services/reminder.py                   # _validate_offsets ставит reason
* src/bot/routers/reminders.py                      # _format_error через match-reason
* src/bot/routers/help.py                           # cmd_help + декоратор
+ tests/unit/bot/routers/test_help_handler.py       # 3 теста
* tests/unit/bot/routers/test_reminders_handler.py  # регресс под reason
```

## Ссылки

- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — раздел «Справка»
- [src/shared/exceptions.py](../../src/shared/exceptions.py) — `EventNotPredictableError` (образец `reason: Literal`)
- [src/shared/services/reminder.py](../../src/shared/services/reminder.py)
- [src/bot/routers/reminders.py](../../src/bot/routers/reminders.py)
- [src/bot/routers/start.py](../../src/bot/routers/start.py) — образец паттернов handler'а
- [src/bot/texts.py](../../src/bot/texts.py) — `HELP` готов

## Подсказки исполнителю

- **`match` exhaustive проверяется mypy.** Если `reason: Literal["too_many", "duplicate", "below_minimum"]`, и в `match` все три кейса покрыты, mypy считает функцию полной (возвращает `str` без `None`). Если добавится новый reason — mypy подскажет, что match не исчерпывающий.
- **Импорт `Literal`** — `from typing import Literal`. Уже импортирован в `src/shared/exceptions.py` для `EventNotPredictableError`.
- **`# noqa: ARG001` на unused params** — стандартный ruff-suppression. Альтернатива: префикс `_user`, `_session`. Я бы предпочёл `noqa`-комментарий — он явнее показывает, что параметр ожидается контрактом DI/декоратора.
- **Метрика теста для help.** `message.answer` вызывается один раз. Проверь и текст, и `reply_markup`. Достаточно простого `isinstance(kbd, ReplyKeyboardMarkup) and len(kbd.keyboard) == 3` для главного меню.
- **`session` в сигнатуре `cmd_help` не используется**, но aiogram middleware его инжектит из `SessionMiddleware`. Можно убрать из сигнатуры — aiogram пропустит kwarg без ошибки. **Но** ruff-rule UP037 или подобный может потребовать строгого матчинга. Если убираешь — проверь, что тесты передают только реально нужные параметры. Проще оставить для единообразия.
- **`InvalidReminderOffsetsError` импорт в handler** — сейчас уже импортируется. Просто меняется сигнатура исключения. Не забудь обновить экспорт в `src/shared/exceptions.py` `__all__` (он уже там).

## Что НЕ делать

- Не делать сложного `cmd_help` с динамикой (список команд, контекстная справка, FAQ) — это статика, спека жёстко описывает текст.
- Не вынести `_validate_offsets` reasons в отдельный enum / `IntEnum` — `Literal[str]` достаточно и проще.
- Не добавлять новые reasons «на всякий случай» — только три из текущих веток валидатора.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не добавлять зависимости.
- Не зеркалить в Drive вручную — это зона cowork.
