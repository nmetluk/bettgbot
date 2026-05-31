---
id: TASK-094
created: 2026-06-01
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/admin/templates/base.html
  - src/admin/app.py
  - src/admin/static/js/ui.js
  - src/admin/static/css/app.css
  - src/admin/static/css/tokens.css
  - handoff/archive/TASK-093-csp-incompatible-click-handlers/task.md
  - handoff/inbox/TASK-088-design-conformance-to-mockup.md
priority: high
estimate: S
---

# TASK-094: Cache-busting статики админки (`ui.js`/`app.css`/`tokens.css`)

## Контекст

При проверке TASK-093 на проде (2026-06-01, cowork) всплыл реальный продакшен-баг деплоя:
после выката новые контролы (тёмная тема/плотность/акцент/меню) **не работали**, потому что
браузер исполнял **старый закэшированный `/static/js/ui.js`** (`setDensity(val)` прокидывал
event вместо чтения `data-*`), хотя сервер уже отдавал новую версию. Заработало только после
`Cmd+Shift+R`. Подтверждено: `fetch('/static/js/ui.js?cb=...')` возвращал новый код, а
загруженный страницей — старый.

Причина — статика подключается **без версии/хэша**:

```html
<!-- src/admin/templates/base.html -->
<link rel="stylesheet" href="/static/css/tokens.css">
<link rel="stylesheet" href="/static/css/app.css">
<script defer src="/static/js/ui.js"></script>
```

и `StaticFiles` смонтирован без управления кэшем (`src/admin/app.py`). Имена файлов не содержат
хэша → браузер держит старую копию после деплоя.

**Почему это важно сейчас:** TASK-088 (дизайн-конформанс) — это **большой деплой CSS**
(`app.css`/`tokens.css`). Без cache-busting пользователи, заходившие раньше, увидят старые
стили до ручного hard-reload — ровно как сейчас с `ui.js`. То есть каждый фронт-фикс будет
«работает после Ctrl+Shift+R, но не у пользователей».

## Цель

После деплоя браузеры автоматически подхватывают новые `ui.js`/`app.css`/`tokens.css` без
ручного сброса кэша, при этом неизменные ассеты по-прежнему кэшируются (без лишних повторных
загрузок).

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-094-report.md`.** Без отчёта CI handoff-consistency красный, PR не мёрджится.
> 🚨 Не закрыто, пока CI зелёный, PR смёрджен **и подтверждено на проде**: после деплоя
> новый ассет грузится без hard-reload.

- [ ] Версионировать **свои** ассеты (`css/tokens.css`, `css/app.css`, `js/ui.js`) — добавить
      busting-параметр `?v=<token>`. Источник `<token>` (на выбор, описать в отчёте):
      - per-file content hash (лучший — бьётся только изменённый файл), **или**
      - единый build-id из системы build-метаданных (см. PR #148 «build metadata / deploy
        observability» — если там уже есть commit SHA/build id, переиспользовать), **или**
      - mtime файла на старте приложения.
      Реализовать через Jinja-хелпер (напр. `static_url('css/app.css')` → `/static/css/app.css?v=...`)
      и заменить захардкоженные пути в `base.html` (и в `_layout_shell.html`, если там есть свои).
- [ ] Cache-заголовки на `/static`: версионированные ассеты можно отдавать с долгим
      `Cache-Control: max-age=…, immutable`; HTML-страницы — НЕ кэшировать агрессивно
      (`no-cache`/`must-revalidate`), чтобы свежий HTML всегда тянул свежий `?v=`.
- [ ] Vendor-файлы (`bootstrap-5.3.3.min.css`, `htmx-2.0.4.min.js`, `alpine-csp-3.14.1.min.js`)
      уже версионированы именем — их можно не трогать (или тоже завести под хелпер для единообразия).
- [ ] Не сломать CSP (TASK-057/079): `?v=` в пути не влияет на `script-src`/`style-src 'self'`.
- [ ] Тест/проверка: рендер `base.html` подставляет `?v=` в пути своих ассетов; токен меняется
      при изменении файла/билда.
- [ ] `ruff`/`mypy src/shared`/`pytest` зелёные.
- [ ] PR открыт `TASK-094: <subject>`, CI зелёный, PR смёрджен, локальная `main` синхронизирована.
- [ ] **После выката на прод** — открыть админку в браузере, который раньше кэшировал старьё:
      новый `ui.js`/CSS должен подтянуться **без** `Cmd+Shift+R`. Зафиксировать в отчёте.
- [ ] Отчёт `handoff/outbox/TASK-094-report.md` написан.
- [ ] **Move-семантика inbox→archive** — оставить директорию `handoff/archive/TASK-094-<slug>/task.md`,
      без залипших `.in-progress` (см. практику 092/093 — закрывать lifecycle чисто).

## Артефакты

- `* src/admin/templates/base.html` — пути ассетов через busting-хелпер
- `* src/admin/app.py` — Jinja-хелпер `static_url` (глобал шаблонов) + Cache-Control на /static
- `* src/admin/templates/_layout_shell.html` — если в нём есть прямые ссылки на свои ассеты
- `* tests/...` — проверка подстановки `?v=`

## Подсказки исполнителю

- Минимально достаточный набор для busting — **только свои** изменяемые файлы: `ui.js`,
  `app.css`, `tokens.css`. Vendor с версией в имени не критичны.
- Координация с **TASK-088** (она сейчас в работе и меняет `app.css`/`tokens.css`): идеально,
  чтобы 094 **смёрджился и задеплоился раньше** деплоя 088 — тогда новые стили 088 подхватятся
  без hard-reload. Если 088 выкатится первой — потребуется разовый Ctrl+Shift+R у пользователей,
  и 094 закроет проблему на будущее. Конфликта по файлам нет: 094 трогает `base.html`/`app.py`,
  088 — `_layout_shell.html` + содержимое CSS.
- Не выключать кэш полностью (`no-store` на всё) — это убьёт смысл; цель именно версионирование.
