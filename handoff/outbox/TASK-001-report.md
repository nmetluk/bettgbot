---
task: TASK-001
completed: 2026-05-22
agent: claude-code-local
status: done
pr: null  # для первого коммита PR не открывался — root-commit ушёл прямо в main, branch protection недоступен на free-плане (см. ниже)
branch: main
commits:
  - c3a31ae chore(init): bootstrap project skeleton and docs
---

# Отчёт по TASK-001: Инициализация git-репозитория и GitHub-репо

## Сводка

Локальный репозиторий проинициализирован на ветке `main`. Все артефакты текущего состояния проекта (документация, спецификации, ADR, шаблоны handoff, заготовки `src/` и `tests/`, `pyproject.toml`, `.gitignore`, `.env.example`) включены в первый коммит. Удалённый репозиторий `nmetluk/bettgbot` уже существовал, был приватным и пустым — подключён как `origin` (HTTPS), запушена ветка `main`, отслеживание настроено.

Согласовано с владельцем: имя репо — `nmetluk/bettgbot` (private), git `user.name=nmetluk`, `user.email=nmetluk@yahoo.com`. PAT, как и было заявлено в CLAUDE.md, оказался на машине, но не подключён ни к `gh`, ни к git: он лежал в macOS Keychain (internet-password, server=`github.com`, account=`nmetluk`). По согласованию с владельцем извлёк его, выполнил `gh auth login --with-token` (gh теперь хранит токен в keyring) и `gh auth setup-git` — последний прописал в глобальный git-конфиг `credential."https://github.com".helper = !/opt/homebrew/bin/gh auth git-credential`. После этого `git push` уходит на GitHub без интерактива. Это setup-шаг машины, не репозитория; для последующих задач он уже сделан.

Branch protection для `main` включить не удалось: GitHub API ответил `403 — "Upgrade to GitHub Pro or make this repository public to enable this feature."` Для приватных репозиториев на free-плане эта функция недоступна. Решение в задаче явно разрешено зафиксировать и продолжить — что и сделано. Альтернативы: (а) перевести репо в public, (б) перейти на GitHub Pro, (в) жить без protection и полагаться на дисциплину (workflow и так требует PR-only, см. CLAUDE.md). Подробности — в открытых вопросах ниже.

Создан `.github/pull_request_template.md` с разделами: ссылки на задачу/отчёт, что сделано, что вынесено, открытые вопросы, чек-лист (ruff/mypy/pytest/handoff), команды воспроизведения.

## Изменённые файлы

```
+ .git/                                           # инициализирован, ветка main
+ .github/pull_request_template.md                # новый, PR-шаблон
* handoff/inbox/TASK-001-init-repo.md             # переименован в TASK-001-init-repo.in-progress.md, затем перенесён в archive/
+ handoff/archive/TASK-001-init-repo/task.md      # исходная задача
+ handoff/outbox/TASK-001-report.md               # этот отчёт
```

(Все остальные файлы — документация, шаблоны, заготовки `src/`/`tests/`/`infra/`, `pyproject.toml` и т.д. — не менялись, они вошли в первый коммит как есть.)

## Как воспроизвести / запустить

```bash
# проверить состояние локально
cd "/Users/nmetluk/Documents/Claude/Projects/Betting Bot"
git log --oneline                  # c3a31ae chore(init): bootstrap project skeleton and docs
git remote -v                      # origin -> https://github.com/nmetluk/bettgbot.git
git branch -vv                     # * main c3a31ae [origin/main]

# проверить gh и credential helper
gh auth status                     # ✓ Logged in to github.com account nmetluk (keyring)
git config --global --get-all credential."https://github.com".helper
                                   # !/opt/homebrew/bin/gh auth git-credential

# открыть удалённый репо
gh repo view nmetluk/bettgbot --web
```

## Что не сделано (если применимо)

1. **Branch protection для `main` не включён.** Причина — GitHub free-план не поддерживает protection правил на private репозиториях. Не блокер для разработки (workflow и так PR-only через handoff), но **создаёт риск случайного прямого пуша в `main`**. Предлагаю одно из:
   - Подключить GitHub Pro владельцу (даёт protection на private).
   - Сменить репо на public (если scope позволяет).
   - Оставить как есть и зафиксировать в `state/DECISIONS.md` строкой «branch protection отложен до перехода на Pro / публичности; до тех пор — дисциплина через handoff».

2. **PR для самого TASK-001 не создавался.** Первый коммит — root-commit, он по природе уходит в `main` сразу. После включения protection (когда будет возможно) все следующие задачи пойдут через ветки `feature/TASK-NNN-*` и PR — этот порядок уже зашит в [`docs/08-conventions.md`](../../docs/08-conventions.md) и в созданный PR-template.

## Открытые вопросы для проектировщика

- **Branch protection.** Какой из трёх вариантов выше выбираем? Если Pro — это решение владельца; если public — нужно подтверждение, что spec/код можно публиковать; если оставляем — стоит ли зафиксировать решение в `state/DECISIONS.md` и обновить ADR-0003 (handoff-protocol) ссылкой на «дисциплина вместо protection»?
- **GH credential helper.** Сейчас `git push` уходит через `gh auth git-credential`. Это значит, что любая утечка `~/.config/gh` или Keychain-записи открывает доступ к репо. Менять ничего не предлагаю, но фиксирую — если cowork считает важным, можно сделать ADR про модель секретов локальной машины.
- **TASK-001 в первом коммите как `.in-progress.md`.** Первый коммит зафиксировал состояние задачи `in-progress` — это side-effect того, что коммит делается ещё внутри активной задачи (root-commit, единственно возможный порядок). После архивации задача переезжает в `handoff/archive/`, но этот переезд уже не входит в первый коммит — нужен дополнительный коммит (`chore: archive TASK-001`) сразу после написания этого отчёта. Делать его в рамках того же TASK-001 или открыть микро-задачу? Принял решение: делаю в рамках TASK-001, потому что архивация — часть DoD и без неё задача не закрыта. Отметка для cowork: это решение можно отменить, переоткрыв задачу.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-22 — TASK-001: git-репо инициализирован, root-commit `c3a31ae` запушен в `nmetluk/bettgbot` (private); подключён `gh` + git credential helper; PR-template добавлен. Branch protection отложен (GitHub free не поддерживает для private).
```

## Метрики

- Тестов добавлено: 0 (задача инфраструктурная)
- Файлов в первом коммите: 41
- Коммитов: 1 (root) + 1 запланированный (`chore: archive TASK-001`) — будет сделан сразу после этого отчёта
- Время на выполнение: ~30 мин (включая обнаружение PAT в Keychain и настройку gh)
