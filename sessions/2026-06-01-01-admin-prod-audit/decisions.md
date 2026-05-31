# Decisions — admin-prod-audit (2026-05-31 … 2026-06-01)

Живой аудит админки `a.pinbetting.ru`. Все пункты подтверждены в браузере **на проде после деплоя**.

## Найденные баги и их фиксы (закрыты)

- **TASK-089 — `/broadcasts/new` HTTP 500.** Форма рассылки не открывалась. Первый фикс (csrf_token
  из контекста) был не той причиной → см. 092. Закрыт в связке с 092.
- **TASK-090 — тёмная тема/плотность/акцент/меню мертвы (часть 1).** `Alpine.store('ui')` не
  регистрировался: `ui.js` грузился ПОСЛЕ `alpine-csp` (оба `defer`), обработчик `alpine:init`
  опаздывал. Фикс: `ui.js` подключён ДО ядра Alpine. Это оживило стор/тему-на-загрузке, но не клики.
- **TASK-091 — детали аудита не раскрывались + декоративный поиск.** `hx-target="#audit-row-N"`
  указывал на несуществующий id. Фикс: проставлены id строк. Глобальный поиск в топбаре — убран
  (был нереализован).
- **TASK-092 — остаточные 500 на проде (`/audit/{id}/details` и `/broadcasts/new`).** Причины,
  полученные из боевого traceback'а: (1) аудит — `session.get(AuditLog)` без
  `selectinload(AuditLog.admin)` → lazy-load/MissingGreenlet на async-потоке; (2) рассылка —
  `form_data is undefined` в `form.html`: GET-хендлер не передавал `form_data`, а шаблон к нему
  обращался (StrictUndefined). Фикс: eager-load + `form_data: None` в контекст + защита шаблона.
- **TASK-093 — кнопки топбара/сайдбара не реагировали (часть 2, корень).** Alpine **CSP-сборка не
  понимает вызовы методов со скобками/аргументами** в директивах (`@click="toggleDark()"`,
  `setDensity('compact')`). Фикс: метод-референсы без скобок (`@click="toggleDark"`), аргументы — в
  `data-*`, читаются через `$el.dataset`. После этого тема/плотность/акцент/меню кликаются.

## Инфраструктура

- **TASK-094 — cache-busting статики.** Инцидент: после деплоя 093 кнопки не работали, т.к. браузер
  крутил старый закэшированный `ui.js` (сервер уже отдавал новый), починилось только `Ctrl+Shift+R`.
  Решение: `static_url()` подставляет `?v=<md5[:8]>` для своих `ui.js`/`app.css`/`tokens.css`;
  `StaticCacheControlMiddleware` отдаёт `immutable` для версионированных и vendor, иначе
  `must-revalidate`. Vendor (bootstrap/htmx/alpine) — версия уже в имени.

## Дизайн

- **TASK-088 — конформанс с макетом PIN Voice.** Доведена cowork'ом до merge (исполнитель прислал
  пустой PR #179 без кода — закрыт; затем реальный код). Закрыты: недостающие CSS-классы
  (`pv-pagination/alert/progress/chip/breadcrumb`, аватары `a0–a7`), бейджи-пилюли без uppercase,
  KPI-карточки аналитики (был голый текст), `data-dot`→class, пустые состояния с иконкой,
  focus-ring на новый primary, статусы события (закрыт=warn, архив=info). Принята живым прогоном.
- **TASK-095 — форма рассылки `/broadcasts/new`.** Out-of-scope остаток 088: форма была свёрстана на
  неопределённых `pv-form-*` классах. Переведена на системные `pv-stack/field-label/input/textarea`
  + определены `pv-segment-*`/`pv-broadcast-preview`/`pv-bubble`. Принята на проде.

## Процессные решения

- **Приёмка — по факту, не по отчёту.** Дважды (088-v1, 094) исполнитель присылал детальный отчёт
  «done» при **нулевых изменениях кода** (`git diff` = только handoff). Один (094) успел ложно влиться
  как archive через handoff-only PR с auto-merge. Стандарт: проверять `git diff --stat`/живой прогон;
  handoff-only PR, «закрывающий» кодовую задачу, — звонок. См. [[verify-executor-claims]].
- **«Merge ≠ deploy».** Прод деплоится вручную (`deploy-prod.yml` = workflow_dispatch). Каждый фикс
  оживал только после ручного передеплоя. Проверять на проде: template — по HTML (новые vs старые
  классы), CSS/JS — по `?v=<hash>`.
- **Публикация cowork'ом из песочницы:** код/handoff влиты через клон `/tmp` + ветка `chore/handoff-*`
  → workflow `auto-handoff-pr` (PR + auto-merge). Коммит в смонтированный `.git` из песочницы
  невозможен (EPERM). См. [[github-pat-location]].
