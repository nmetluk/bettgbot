<!--
Имя PR: `TASK-NNN: <subject>` (Conventional Commits — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
Один PR — одна задача из handoff/.
-->

## Ссылки

- Задача: [`handoff/archive/TASK-NNN-<slug>/task.md`](../tree/main/handoff/archive/) <!-- или handoff/inbox/, если ещё не закрыта -->
- Отчёт: [`handoff/outbox/TASK-NNN-report.md`](../tree/main/handoff/outbox/) <!-- появится при закрытии задачи -->
- Связанные спецификации / ADR: `docs/...`

## Что сделано

<!-- 1–3 абзаца: суть изменения, ключевые решения внутри задачи. -->

## Что не сделано / вынесено

<!-- Если что-то урезали относительно DoD задачи — здесь. Иначе — «нет». -->

## Открытые вопросы для проектировщика

<!-- Список или «нет». -->

## Проверки перед merge

- [ ] `ruff check` чист
- [ ] `ruff format --check` чист
- [ ] `mypy src/shared/` проходит (strict)
- [ ] `pytest` зелёный (unit + integration, по применимости)
- [ ] Обновлены затронутые `docs/` / ADR, если требовалось задачей
- [ ] Отчёт `handoff/outbox/TASK-NNN-report.md` написан и приложен
- [ ] Исходная задача перенесена в `handoff/archive/TASK-NNN-<slug>/`

## Как воспроизвести локально

```bash
# команды для запуска и тестов конкретно этого PR
```
