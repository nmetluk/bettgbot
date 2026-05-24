# Решения — task-024-review

**Все 5 — keep:**

| # | Решение | Обоснование |
|---|---|---|
| 1 | Server-side guard в `set_result` handler не добавляем — trust UI | Admin не делает запрещённые действия через прямой URL. Service бросит соответствующее исключение, если в БД условия не выполнены. На MVP допустимо |
| 2 (info) | CHECK constraint `ck_event_result_archive_consistency` (TASK-018) совместим с `set_result` | `set_result` ставит `(has_result, archived=true, archived_at=now)` — третья валидная комбинация. Никаких регрессий |
| 3 | Flash в URL после refresh — норма для query-string подхода | `history.replaceState` для очистки — overengineering для MVP. Пользователь обычно уходит на другую вкладку после успеха |
| 4 | Read-only mode без кнопки Edit/Cancel | Спека «переопределение итога не предусмотрено в MVP» |
| 5 | Disabled tab через Bootstrap `disabled` class + `aria-disabled="true"` + tooltip | Accessibility-friendly. Tooltip показывает причину при наведении |
