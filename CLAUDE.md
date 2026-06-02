# Инструкции для локального Claude Code

Ты — **исполнительный агент** в двухагентной схеме проекта Betting Bot. Проектирует cowork-агент в десктоп-приложении; ты — реализуешь.

## Прежде чем начать любую работу

1. **Сделай `git fetch origin && git pull origin main`** — handoff обновляется только через GitHub, никаких Drive-зеркал.

2. Прочитай в строгом порядке:

2. [`README.md`](README.md) — карта репозитория.
3. [`state/PROJECT_STATUS.md`](state/PROJECT_STATUS.md) — где мы сейчас.
4. [`state/DECISIONS.md`](state/DECISIONS.md) — что уже решено и почему.
5. [`docs/08-conventions.md`](docs/08-conventions.md) — кодовые конвенции.
6. Свежие файлы в [`handoff/inbox/`](handoff/inbox/) — твои задачи.

Если задача отсылает к спецификациям (`docs/03-data-model.md`, `docs/04-bot-flows.md` и т. п.) — открой их и опирайся на них, не выдумывай.

## Где брать задачи

Все задачи приходят файлами в [`handoff/inbox/`](handoff/inbox/) с именами вида `TASK-NNN-краткий-slug.md`. Формат описан в [`handoff/README.md`](handoff/README.md), шаблон — [`handoff/templates/task.md`](handoff/templates/task.md).

**Брать в работу — по возрастанию номера** (TASK-001 раньше TASK-002), если в самой задаче не указано `blockedBy`. Несколько задач параллельно — только если они помечены `parallel-safe: true`.

## Что обязано быть в отчёте

- Что сделано (со ссылками на коммиты и PR).
- Что **не** сделано и почему (если что-то пришлось вынести).
- Открытые вопросы, которые требуют решения cowork-агента / владельца.
- Команды для воспроизведения локально (как запустить, как прогнать тесты).
- Diff-сводка по затронутым файлам.

Отчёт — твоё единственное окно к проектировщику. Чем подробнее и честнее — тем меньше нужно будет дораб­атывать.

Шаблон отчёта — [`handoff/templates/report.md`](handoff/templates/report.md).

**🚨 Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать `handoff/outbox/TASK-NNN-report.md`. Без отчёта CI handoff-consistency красный, PR не мёрджится.**

## Жизненный цикл задачи

```
handoff/inbox/TASK-NNN.md
        │
        │  ты берёшь в работу:
        │  переименовать в TASK-NNN.in-progress.md (atomic mv)
        ▼
handoff/inbox/TASK-NNN.in-progress.md
        │
        │  работа: код, тесты, коммиты в ветке feature/TASK-NNN-slug
        │  пуш в GitHub (PAT уже настроен)
        │
        │  готово: написать отчёт в outbox, переместить исходную задачу в archive
        ▼
handoff/outbox/TASK-NNN-report.md   +   handoff/archive/TASK-NNN.md
```

Шаблон отчёта — [`handoff/templates/report.md`](handoff/templates/report.md).

## Git и GitHub

- Branch-стратегия: `main` защищён branch protection (enforce_admins=true, required status checks: lint, typecheck, unit-test, integration, handoff-consistency), работа в ветках `feature/TASK-NNN-slug`, `fix/...`, `chore/...`.
- Commit-сообщения — [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
- Каждая задача → одна ветка → один PR в `main`. Имя PR: `TASK-NNN: <subject>`. В описании PR — ссылка на `handoff/inbox/TASK-NNN.md` и `handoff/outbox/TASK-NNN-report.md`.
- PAT для пуша уже на машине пользователя — настраивать не нужно. При первой задаче создаст GitHub-репозиторий (детали в TASK-001).
- **Auto-merge включен на репозитории.** Все PR сливаются автоматически через `gh pr merge --auto --squash` когда все required-чеки зелёные. Прямой push в `main` запрещён для всех (включая admin'ов благодаря `enforce_admins=true`).

### Push обязателен после каждой задачи

После закрытия любой задачи (фичевой, фикса, cleanup, archive) **обязательно** выполнить:

0. **`git fetch origin && git rebase origin/main`** — ветка ОБЯЗАНА быть на свежем `main`. Branch protection требует «branch up to date»; устаревшая ветка в auto-merge не встанет (типовая причина «готово, но висит на ветке» — TASK-097/099/100/101).
1. `git push origin <feature-branch>` — выложить ветку.
2. `gh pr create ...` или обновить существующий PR.
3. `gh pr merge --auto --squash` — **включить auto-merge ЯВНО.** Для `feature/**`-веток это НЕ происходит само (workflow `auto-handoff-pr.yml` срабатывает только на `chore/handoff-**`/`docs/handoff-**`). Без этого шага PR просто висит зелёным и не вливается.
4. **Проверить, что PR реально встал в очередь:** `gh pr view <PR> --json autoMergeRequest,mergeStateStatus` (или Actions/UI) — auto-merge enabled и CI идёт/зелёный. «Запушил» ≠ «влилось».
5. После merge — `git checkout main && git pull origin main`.
6. Только после этого считать задачу закрытой.

> 🚨 **DoD-прогон ОБЯЗАН включать `uv run ruff format --check src tests`, а не только `ruff check`** — это разные гейты; формат-чек уже валил CI (TASK-099 — 2 файла, TASK-100 — 1) при зелёном `ruff check`. Локально перед push: `uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src/shared && uv run pytest`.

### Handoff-публикация архитектором (cowork-агент)

Архитектор не имеет прямого доступа к GitHub API. Для публикации handoff-доков:

1. Архитектор пушит ветку `chore/handoff-NNN` (или `docs/handoff-NNN`) в `origin`.
2. Workflow `.github/workflows/auto-handoff-pr.yml` автоматически:
   - Открывает PR в `main` (если ещё не открыт).
   - Включает auto-merge (`--auto --squash`).
3. PR вливается сам по зелёному CI без участия человека.
4. Архитектор синхронизирует локальную `main`: `git pull origin main`.

Цель — на удалённом репо `nmetluk/bettgbot` всегда лежит актуальная `main` сразу после каждой задачи. Это позволяет:

- Поднять рабочее место на любой машине (текущая локальная — не единственная).
- Использовать `nmetluk/bettgbot` как single source of truth, к которому может подключиться второй экземпляр локального CC.
- Откатиться к любой точке без потерь незакоммиченной работы.

Если `git push` падает (auth, network) — это **блокер**, оформить как `outbox/TASK-NNN-question.md`, **не** оставлять локально и идти дальше.

## Кодовые правила

См. [`docs/08-conventions.md`](docs/08-conventions.md). Если кратко:

- Python 3.12, форматтер и линтер — `ruff`, типы — `mypy` (strict для `src/shared/`).
- Все новые модули — с docstring уровня модуля.
- Никакой бизнес-логики в обработчиках aiogram и в роутах FastAPI — только парсинг входа, вызов сервиса, форматирование ответа.
- ORM-сессии — через DI / контекстный менеджер, никогда глобальные.
- Внешний API — только через интерфейс `ExternalUserRegistryClient` из `src/shared/external/`; в dev-окружении подключается mock-реализация.
- Любая запись в БД — внутри транзакции.
- Все тексты бота — через i18n-словарь (`src/bot/texts.py`), а не хардкодом в обработчиках.

## Что делать с неоднозначностью

Если задача неоднозначна или ты видишь конфликт со спецификацией:

1. **Не угадывай.** Останови работу.
2. Создай файл `handoff/outbox/TASK-NNN-question.md` с вопросом, отметь задачу как `blocked` (переименовать `TASK-NNN.in-progress.md` → `TASK-NNN.blocked.md`).
3. Жди ответа cowork-агента (он положит дополнение в `handoff/inbox/TASK-NNN-amendment.md`).

## Чего делать нельзя

- Не менять `state/`, `sessions/`, `docs/`, `docs/adr/`, `README.md` без явного указания в задаче. Эти артефакты — зона проектировщика.
- Не добавлять зависимости «потому что удобно» — только то, что обосновано задачей.
- Не выкатывать на прод (этого этапа пока нет в скоупе).
- Не публиковать секреты в репозитории. `.env` всегда в `.gitignore`.

## Когда задача готова

1. Все тесты зелёные (`pytest`), линт чист (`ruff check`), типы (`mypy src/shared`).
2. **Коммиты запушены в `origin/<feature-branch>`, PR открыт, CI зелёный.**
3. Отчёт в `handoff/outbox/TASK-NNN-report.md` написан и закоммичен.
4. Исходная задача перемещена в `handoff/archive/`, тоже закоммичена.
5. **PR слит** (squash), **локальная `main` синхронизирована с `origin/main`** (`git checkout main && git pull`).
6. Если задача требовала обновления списка готового — пометил в отчёте, что строка для `state/PROJECT_STATUS.md` подготовлена (саму строку добавит проектировщик).
