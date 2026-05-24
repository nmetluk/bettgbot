# Решения — task-021-review

**5 keep + 2 change (объединены в Step 0 TASK-022):**

| # | Решение | Альтернативы | Обоснование |
|---|---|---|---|
| 1 (**change → TASK-022 Step 0**) | **CSRF token доступен везде через `request.state.csrf_token`** — новый `CsrfMiddleware` вставляет токен для всех GET-запросов под auth | (a) Везде в handler'ах генерировать; (c) JS-XHR | DRY: один middleware вместо `csrf_protect.generate_csrf_tokens()` в каждом handler'е. Шаблоны читают через `{{ request.state.csrf_token }}` или Jinja2 context_processor. Без этого logout-кнопка в sidebar на дашборде даёт 403 |
| 2 | `/login` без sidebar через `{% block sidebar %}{% endblock %}` — keep | Переопределить `{% block content %}` с `col-12 mx-auto` для centered | Лёгкий offset вправо некритичен. Косметика — позже |
| 3 | **`include_inactive=True` default в admin list-методах** — convention | Default `False` (только активные) | Админ должен видеть всё (включая неактивные категории / снятые с публикации события / архивные). Фильтр в UI поверх. Контрастирует с пользовательскими методами (бот) — там default «active+published» |
| 4 | Sidebar disabled-ссылки на будущие разделы — **паттерн roadmap** | Скрывать до реализации | UX-намёк «функционал появится». Когда соответствующая задача закроется, ссылка становится активной. Применяется ко всему Этапу 3 |
| 5 | `flash` через query-string `?error=has_events&category_id=N` — keep | Signed cookie flash через itsdangerous | Простой, работающий. Триггер для замены — нужда в multi-line или несколько типов flash на одной странице |
| 6 (**change → TASK-022 Step 0**) | **Отрендерить `admin.full_name`** в base.html sidebar | Не показывать | Минорное UX-улучшение «вошли как». Естественно объединить со Step 0 (правка base.html для CSRF middleware всё равно нужна) |

## Паттерн «admin list-методы — include_inactive=True»

Все методы вида `XService.list_*_for_admin` или `XRepository.list_*_with_*` (для админ-UI) по умолчанию возвращают **всё** — активные и неактивные, опубликованные и драфты, архивные и активные. Это семантика «админ ответственен за полную картину».

Контрастирует с пользовательскими методами (бот) — там default фильтр «активное+опубликованное+не архивное».

## Step 0 TASK-022 расширен

Включает два change-решения из этого review:

1. **CSRF middleware** (`CsrfMiddleware`) — вставка `request.state.csrf_token` для всех GET-запросов под `RequireAdminMiddleware`. Шаблоны переписываются на чтение из state. Existing CSRF в `categories.py` handler'ах удаляется как дублирование.
2. **Admin info в base.html** sidebar — «Вошли как: `{{ admin.full_name }}`» (или `admin.login` если full_name=None) рядом с logout-формой. `admin` уже доступен через `Depends(current_admin)` в каждом handler'е, можно передавать в context универсально через Jinja2 context_processor (через request.state) либо передавать в каждом handler'е (overhead).
