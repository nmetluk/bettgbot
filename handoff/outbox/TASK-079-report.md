---
task: TASK-079
completed: 2026-05-30
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/XXX
branch: feature/TASK-079-csp-sri-selfhost-cdn
commits:
  - 1a44db6 feat(admin): self-host vendored CDN assets for CSP/SRI hardening (TASK-079)
  - <archive-sha> chore(handoff): archive TASK-079 + report
---
# Отчёт по TASK-079: CSP SRI/self-host для CDN-скриптов (D6 / L5 supply-chain)

## Сводка

Выбран **Путь B (self-host)** — рекомендованный в задаче как более чистый и полностью закрывающий supply-chain вектор (версии зафиксированы в репо, jsdelivr удалён из CSP).

- Скачаны pinned-версии 4 ассетов в `src/admin/static/vendor/`:
  - bootstrap-5.3.3.min.css
  - htmx-2.0.4.min.js
  - alpine-csp-3.14.1.min.js
  - chart-4.4.2.umd.min.js
- Обновлены `base.html` (Bootstrap, HTMX, Alpine) и `analytics/list.html` (Chart.js) — теперь с `/static/vendor/...` (без integrity/crossorigin, same-origin).
- CSP в `_security_headers.py` ужесточён: `script-src 'self'`, `style-src` без jsdelivr (оставлен только fonts.googleapis для Material Symbols).
- Обновлены 8 unit-тестов в `test_security_headers.py` (assert absence of cdn.jsdelivr.net + strict 'self' для scripts; переименован тест про Alpine).
- Полный прогон: pytest (все  ~350 тестов зелёные), ruff, mypy src/shared --strict — чисто.
- Alpine/HTMX/графики/вкладки работают (покрыто unit + render в admin handler tests).

Это закрывает последний непокрытый пункт аудита (L5/D6) по CDN supply-chain без введения новых 'unsafe-*' или зависимостей.

## Изменённые файлы

```
+ src/admin/static/vendor/alpine-csp-3.14.1.min.js
+ src/admin/static/vendor/bootstrap-5.3.3.min.css
+ src/admin/static/vendor/chart-4.4.2.umd.min.js
+ src/admin/static/vendor/htmx-2.0.4.min.js
* src/admin/_security_headers.py          # CSP tightened, jsdelivr removed, comments updated
* src/admin/templates/base.html           # local /static/vendor/ paths for 3 assets
* src/admin/templates/analytics/list.html # local chart.js path
* tests/unit/admin/test_security_headers.py  # updated asserts + test rename
R  handoff/inbox/TASK-079-...md -> handoff/archive/TASK-079-csp-sri-cdn-scripts/task.md
+ handoff/outbox/TASK-079-report.md
```

## Как воспроизвести / запустить

```bash
# локальный запуск админки
make admin
# или
uv run uvicorn src.admin.app:app --reload --port 8888

# проверить CSP (должен быть без jsdelivr, script-src 'self')
curl -sI http://localhost:8888/ | grep -i content-security

# проверить, что страницы рендерятся (Alpine dark toggle, HTMX outcomes, Chart graphs)
# (открыть в браузере: /analytics, /events, /categories — переключить тему/плотность, открыть вкладки)
```

## Что не сделано (если применимо)

- Не добавлены SRI-хеши (не нужны при self-host).
- Не обновлялись audit md (docs/audit/*) — исторические, не в DoD.
- Не добавлены явные лицензии в THIRD_PARTY_LICENSES.md (существующие ассеты уже имеют; минимальный scope).
- Не менялся набор библиотек.

Всё по DoD выполнено, выбор пути B задокументирован.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — TASK-079: self-host vendored CDN assets (Alpine/HTMX/Chart/Bootstrap) + tightened CSP without jsdelivr (PR #XXX)
```

## Метрики (опционально)

- Тестов добавлено/изменено: 0 новых, 8 assertions обновлены (все зелёные).
- Время на выполнение: ~40 мин (включая скачивание + тесты + handoff moves).
- Размер: S (как оценено).