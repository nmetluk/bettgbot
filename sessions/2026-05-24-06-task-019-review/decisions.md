# Решения — task-019-review

**5 keep + 1 в тех-долг + 1 в Step 0 следующей задачи:**

| # | Решение | Альтернативы | Обоснование |
|---|---|---|---|
| 1 | Volt CSS остаётся placeholder'ом + **новый пункт в тех-долг**: «скомпилировать volt.css из SCSS-источников Volt Free» | (a) npx-build на CI; (b) другой готовый шаблон (Bootswatch) | Bootstrap 5 через CDN покрывает базовую вёрстку. Фирменный Volt-стайлинг — nice-to-have, не критичен до TASK-021+ с реальными таблицами. Триггер фикса — когда реально не хватит styling'а |
| 2 | **`bcrypt` напрямую вместо `passlib[bcrypt]`** — закрепляем как архитектурный принцип | Pin `bcrypt<4.1` (старый API); ждать релиз passlib с поддержкой bcrypt 5.x | passlib 1.7.4 несовместим с bcrypt 5.0 (passlib внутри падает с «password cannot be longer than 72 bytes» из-за изменения API). `bcrypt` напрямую — проще, меньше слоёв, тот же `$2b$…` формат. Cleanup pyproject (убрать passlib из зависимостей) — в Step 0 TASK-020 |
| 3 | `scripts/` запускаются через Makefile-обёртку (`make admin.create LOGIN=… PASSWORD=…`) | `scripts/__init__.py` + `python -m scripts.create_admin`; CLI entrypoint в `pyproject.toml [project.scripts]` | Makefile нормально скрывает «уродство» `PYTHONPATH=. uv run python ...`. Если когда-то появится 3+ скрипта — рефакторим. Сейчас один |
| 4 | Bootstrap Icons CDN в `base.html` — keep | Убрать до явного запроса в задаче | Будут полезны в TASK-021+ (таблицы/формы CRUD с `bi-*` иконками). Одна строка `<link>`, минимальный вес |
| 5 | `OpenAPI полностью off` (`docs_url=None, redoc_url=None, openapi_url=None`) | Оставить `openapi_url` для возможной интеграции с внешними инструментами | Админка — internal tool, не нужно ни UI Swagger, ни самой `/openapi.json` (может утечь схему через зонды). Безопасный default |
| 6 (в тех-долг) | Compiled `volt.css` из SCSS — записать в BACKLOG | Не записывать | Если когда-то понадобится фирменный стиль — отдельная мини-задача с npm-build. Триггер — конкретная UX-нужда в TASK-021+ |
| 7 (в Step 0 TASK-020) | Убрать `passlib[bcrypt]` из `pyproject.toml` (раз уж в TASK-020 будут править pyproject под `fastapi-limiter`) | Сейчас же отдельным мелким PR | Минимизируем количество PR. `fastapi-limiter` всё равно нужно добавить в TASK-020 — заодно подчистим passlib |

## Урок для cowork (мой)

**Перед публикацией задачи с готовыми шаблонами/библиотеками — проверять availability**:

- Если task использует готовый шаблон (Volt, AdminLTE, etc.) — открыть его `dist/` директорию в репозитории и убедиться, что скомпилированные assets есть (не только SCSS-источники).
- Если task использует библиотеку/extras (`passlib[bcrypt]`, `pydantic[email]`) — проверить compatibility-matrix зависимостей.

**Прецеденты:**
- TASK-018 — конфликт с CHECK invariant из `docs/03-data-model.md` (правило родилось из этого).
- TASK-019 — Volt без compiled CSS + passlib incompat с bcrypt 5.

Записать в `handoff/README.md` секцию «Проверки перед публикацией задачи» (третий пункт) при следующем естественном касании README.
