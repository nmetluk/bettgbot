---
id: TASK-001
created: 2026-05-22
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - README.md
  - CLAUDE.md
  - docs/08-conventions.md
priority: high
estimate: S
---

# TASK-001: Инициализация git-репозитория и GitHub-репо

## Контекст

Проектная документация и каркас проекта подготовлены cowork-агентом и лежат в рабочей папке `/Users/nmetluk/Documents/Claude/Projects/Betting Bot`. Это первая задача исполнения: завести git-репозиторий, создать GitHub-репо (PAT уже настроен на машине владельца), сделать первый коммит и пушнуть.

После этой задачи весь дальнейший workflow (см. [`../README.md`](../README.md)) опирается на наличие удалённого репо.

## Цель

В удалённом GitHub есть репозиторий с текущим состоянием проекта, ветка `main`, защищённая от прямых пушей (если позволяют права аккаунта).

## Definition of Done

- [ ] Локальный `git init` выполнен в `/Users/nmetluk/Documents/Claude/Projects/Betting Bot`.
- [ ] Согласовано с владельцем имя репозитория (owner/org + repo-name) и приватность. Если владелец недоступен — использовать значение по умолчанию: личный аккаунт владельца, имя `betting-bot`, **private**.
- [ ] GitHub-репозиторий создан (через `gh repo create` или вручную владельцем, но коммит и пуш делает агент).
- [ ] Настроен `origin` на удалённый URL (HTTPS с PAT или SSH — что уже работает на машине).
- [ ] Конфиг git: `user.name` и `user.email` — спросить у владельца, по умолчанию `nmetluk@yahoo.com`.
- [ ] Первый коммит на ветке `main`: `chore(init): bootstrap project skeleton and docs`. В коммит входят все файлы текущего состояния проекта (после применения `.gitignore`).
- [ ] Пуш в `origin/main`.
- [ ] (Если возможно) включить branch protection для `main` (require PR, require status checks once CI configured) — это **опционально**; если права не позволяют — отметить в отчёте.
- [ ] Создан PR-template (`.github/pull_request_template.md`) с разделами: ссылки на TASK и report, что сделано, чек-лист тестов и линта.
- [ ] Отчёт `handoff/outbox/TASK-001-report.md` написан по шаблону.
- [ ] Эта задача перемещена в `handoff/archive/TASK-001-init-repo/task.md` после завершения.

## Артефакты

- `+ .git/` — инициализированный репозиторий (локально)
- `+ .github/pull_request_template.md` — шаблон PR
- удалённо: `https://github.com/<owner>/<repo>` — создан

## Ссылки

- [README.md](../../README.md) — описание проекта и структуры
- [CLAUDE.md](../../CLAUDE.md) — общие инструкции исполнителю
- [docs/08-conventions.md](../../docs/08-conventions.md) — Conventional Commits и ветки
- [handoff/README.md](../README.md) — handoff-протокол
- [handoff/templates/report.md](../templates/report.md) — шаблон отчёта

## Подсказки исполнителю

- Перед `git init` пройди `ls -la` и убедись, что все файлы из brief.md последней сессии (`sessions/2026-05-22-01-project-bootstrap/brief.md`) на месте. Если чего-то нет — это сигнал спросить cowork, а не дописывать самому.
- `.gitignore` уже есть. Проверь, что `.env`, `.venv`, `infra/mock-registry.local.yml` действительно игнорируются (`git status` после `git add .` не должен их показывать).
- Если используется GitHub CLI (`gh`) — авторизация уже должна быть выполнена ранее. Проверь `gh auth status`. Если не авторизован — попроси владельца сделать `gh auth login`, не пытайся подсовывать PAT в команды.
- Branch protection через `gh` — `gh api -X PUT /repos/<owner>/<repo>/branches/main/protection ...`. Если права аккаунта не дают — спокойно зафиксируй в отчёте «branch protection не настроен, права не позволяют» и продолжай.

## Что НЕ делать

- Не коммитить `.env` ни в каком виде.
- Не добавлять зависимости и не запускать `uv sync` / `poetry install` — это TASK-002.
- Не менять `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` — даже если кажется, что нужно мелкое уточнение. Если уточнение действительно нужно — кладёшь `handoff/outbox/TASK-001-question.md`, переименовываешь задачу в `TASK-001.blocked.md` и ждёшь ответа.
