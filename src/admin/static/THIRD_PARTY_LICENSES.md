# Third-party licenses

Все статические assets третьих сторон, включённые в `src/admin/static/`.

## Volt Bootstrap 5 Dashboard

- **Source:** https://github.com/themesberg/volt-bootstrap-5-dashboard
- **License:** MIT (см. `VOLT_LICENSE.md` в этом каталоге).
- **Used files:**
  - `js/volt.js` — взят из `src/assets/js/volt.js` репозитория (master, commit ~2024-2026).
  - `img/brand/dark.svg`, `img/brand/light.svg` — из `src/assets/img/brand/`.
- **NOT included:** скомпилированный `css/volt.css`. Themesberg публикует только SCSS источники (`src/scss/`). На MVP (TASK-019) включён только пустой placeholder `css/volt.css`; для полного Volt-styling нужно `npm install && npm run build` на Volt-репо.

## Bootstrap 5 / Bootstrap Icons / HTMX

Подключены через jsdelivr CDN из `src/admin/templates/base.html`:

- Bootstrap 5.3.3 — MIT, https://github.com/twbs/bootstrap
- Bootstrap Icons 1.11.3 — MIT, https://github.com/twbs/icons
- HTMX 2.0.4 — Zero-Clause BSD, https://github.com/bigskysoftware/htmx

В этот каталог их файлы не копировались. См. `templates/base.html`.
