---
task: TASK-077
type: amendment
created: 2026-05-30
author: cowork-agent
re: handoff/outbox/TASK-077-question.md
---

# Амендмент к TASK-077: права PAT — корректные permission'ы (fine-grained)

## Ответ на вопрос

Указанные в вопросе scopes (`repo`, `admin:org`) — это **классические** token scopes. Токен проекта —
**fine-grained** (`github_pat_…`), у него не scopes, а **repository permissions**. `admin:org` нерелевантен:
`nmetluk/bettgbot` — личный репозиторий, не организация.

Владелец одноразово добавит токену недостающие repository-permissions (значение токена при этом
**не меняется**, `.gh_pat` на всех машинах остаётся валидным — перевыкладывать не нужно).

Нужные permissions на репозитории `bettgbot`:
- **Administration: Read and write** — branch protection (`PUT …/branches/main/protection`) и
  repo settings (`PATCH repos/… allow_auto_merge`).
- **Secrets: Read and write** — `gh secret set REPO_PAT`.
- **Workflows: Read and write** — пуш изменений в `.github/workflows/*` (fine-grained токен без этого
  права отклоняет коммиты, трогающие workflow-файлы).
- Contents: R&W и Pull requests: R&W — скорее всего уже есть (ты пушишь и открываешь PR); если нет — добавить.

## Что делать исполнителю

1. **Пока ждёшь прав — сделай всё, что не требует API:** написать `.github/workflows/auto-handoff-pr.yml`,
   подготовить правку `CLAUDE.md` (шаг 6), при необходимости — правки `ci.yml` (имена/триггеры джоб).
   Закоммить в ветку `feature/TASK-077-hands-free-gate`, **не** включая пока protection.
2. **Проверка готовности прав (без гадания):** прежде чем выполнять admin-API, убедись, что права уже выданы:
   ```
   gh api -X PATCH repos/nmetluk/bettgbot -F allow_auto_merge=true   # 200 = права есть
   ```
   Если снова `403` — права ещё не применились, подожди/переспроси, **не** считай задачу заблокированной заново
   без необходимости.
3. Дальше — по основному DoD TASK-077 (шаги 1→5), protection **последним**.
4. Сними статус: переименуй `TASK-077.blocked.md` → `TASK-077.in-progress.md`, продолжай.

## Заметка по безопасности

`REPO_PAT` (шаг 2) — это тот же owner-PAT в Actions-secret. Это осознанный компромисс ради серверной
автоматики авто-PR. Убедись, что secret не печатается в логах воркфлоу (`add-mask`/не эхоить).
Если хочешь сузить риск — можно позже сделать отдельный токен только для авто-PR (Contents+PR), но это
отдельным тикетом, не блокирует 077.
