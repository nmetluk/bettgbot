---
id: TASK-077
created: 2026-05-30
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - .github/workflows/ci.yml
  - .github/workflows/handoff-consistency.yml
  - CLAUDE.md
priority: high
estimate: M
---

# TASK-077: полностью автоматический merge-гейт (ноль ручных действий владельца)

## Зачем

Сейчас `main` **не защищён вообще** (проверено: `gh api .../branches/main/protection` → 404
«Branch not protected»). Поэтому сломанный код мёржится под видом «зелёного CI» — именно так
TASK-074 уехал с нерабочим фиксом (см. TASK-076). `CLAUDE.md` при этом утверждает «main защищён» —
документ не соответствует реальности.

Цель — **гейт, который владелец не трогает руками вообще**. Все настройки (protection, repo
settings, secret) делает исполнитель своим PAT'ом; слияния происходят автоматически по зелёному CI.
Решение должно быть **машинно-независимым** (исполнитель работает с разных машин) — вся автоматика
живёт в GitHub (Actions + repo settings), а не в локальных скриптах.

## Ограничения, которые надо учесть

- **Архитектор (cowork-агент) не достаёт `api.github.com`** из своей песочницы (прокси отдаёт 403 на
  CONNECT). Он умеет только `git push` веток к `github.com`. PR открыть/смёржить из песочницы НЕ может.
  Значит публикация handoff-доков архитектором должна автомёржиться **серверной автоматикой**, без API
  со стороны архитектора.
- **Исполнитель** `api.github.com` достаёт (он уже открывает/мёржит PR'ы) — admin-операции делает он.
- Один и тот же owner-PAT у обоих → `enforce_admins=true` обязателен, иначе гейта по факту нет.
- Каверза GitHub: PR, открытый воркфлоу под `GITHUB_TOKEN`, **не триггерит** `pull_request`-воркфлоу.
  Для авто-PR использовать PAT-secret (см. ниже) ИЛИ обеспечить запуск нужных чеков по `push` ветки.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-077-report.md`.
> 🚨 Не закрыто, пока CI зелёный и PR смёржен.

Реализовать в таком порядке (protection — В САМОМ КОНЦЕ):

- [ ] **1. Repo settings.** Включить auto-merge:
      `gh api -X PATCH repos/nmetluk/bettgbot -F allow_auto_merge=true -F delete_branch_on_merge=true`.
- [ ] **2. PAT-secret для серверной автоматики.** Положить owner-PAT в Actions-secret (напр. `REPO_PAT`):
      `gh secret set REPO_PAT < .gh_pat` (или из переменной). Он нужен, чтобы авто-открытый PR
      триггерил CI. Проверить, что secret не светится в логах.
- [ ] **3. Авто-PR + auto-merge для handoff-веток архитектора.** Новый workflow
      `.github/workflows/auto-handoff-pr.yml`, триггер `push` на ветки `chore/handoff-**`
      (и `docs/handoff-**`, если используется). Шаги: открыть PR в `main` (если ещё нет) **под `REPO_PAT`**
      (чтобы запустился `pull_request`-CI) и включить auto-merge squash
      (`gh pr merge --auto --squash`). Тело PR — ссылка на изменённые файлы handoff.
      Итог: архитектор делает только `git push origin chore/handoff-NNN` — PR откроется и вольётся сам
      по зелёному CI, без участия человека и без API со стороны архитектора.
- [ ] **4. Исполнительский флоу — auto-merge вместо немедленного.** Обновить процесс (и `CLAUDE.md`):
      после открытия PR исполнитель делает `gh pr merge --auto --squash` (а не мгновенный merge).
      PR вольётся сам, когда required-чеки зелёные. Никаких ручных подтверждений.
- [ ] **5. Branch protection (ПОСЛЕДНИМ).** Включить на `main`:
      ```
      gh api -X PUT repos/nmetluk/bettgbot/branches/main/protection --input - <<'JSON'
      {
        "required_status_checks": {
          "strict": true,
          "contexts": [<ТОЧНЫЕ имена чеков: lint, typecheck, unit-test, integration, handoff-consistency>]
        },
        "enforce_admins": true,
        "required_pull_request_reviews": null,
        "restrictions": null
      }
      JSON
      ```
      Точные `contexts` взять из реального прогона:
      `gh api repos/nmetluk/bettgbot/commits/<sha>/check-runs --jq '.check_runs[].name'`
      (sha — коммит, где гонялся полный CI). **integration обязан быть в списке** — это главное, чего
      не хватало.
- [ ] **6. Обновить `CLAUDE.md`** (раздел про git/GitHub): `main` защищён по-настоящему; прямой push
      в `main` запрещён всем; все изменения — через PR с auto-merge; handoff-публикация архитектора —
      пушем ветки `chore/handoff-NNN` (PR и merge делает автоматика); исполнитель — `gh pr merge --auto`.
      Убрать ложное «main защищён» → заменить фактическим описанием.
- [ ] **7. Доказать E2E (в отчёт, фактическими ссылками/логами):**
      (a) PR с **падающей** integration НЕ мёржится (можно проверить на TASK-076: если бы фикс был
          неверным — auto-merge бы не сработал); привести пример «красного» auto-merge, который завис.
      (b) «Зелёный» PR вливается **сам**, без ручного merge.
      (c) Архитекторский handoff-флоу: пуш `chore/handoff-**` → авто-PR → авто-merge без человека.
- [ ] `ruff`/`mypy`/`pytest` зелёные; PR `TASK-077: hands-free merge gate (branch protection + auto-merge)`;
      смёржен (уже через новый auto-merge, если успел включиться); локальная `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Важно по порядку

Шаги 1–4 и 6 — до включения protection (шаг 5). Иначе `enforce_admins` залочит `main` раньше, чем
появится автоматика, и сам этот PR будет нечем смёржить. Если protection включился, а auto-PR ещё не
работает — это блокер, оформить `outbox/TASK-077-question.md`.

## Вне скоупа

- Менять набор CI-джоб по существу (логику тестов). Только триггеры/имена, если нужно для required-чеков.
- Разруливать path-фильтры «доки не гоняют integration» — допустимо, что handoff-PR проходит полный CI
  (он зелёный на доках). Если решишь оптимизировать — отдельным тикетом, не здесь.

## Артефакты

- `* .github/workflows/auto-handoff-pr.yml` — авто-PR + auto-merge для handoff-веток
- `* (возм.) .github/workflows/ci.yml` — триггеры/имена джоб, если нужно для required-чеков
- `* CLAUDE.md` — описание реального флоу (через PR + auto-merge)
- `* repo settings + branch protection + secret REPO_PAT` — через `gh api` (в отчёт: что выставлено)
- `* handoff/outbox/TASK-077-report.md`

## Ссылки

- Текущий CI: `push:[main]` + `pull_request:[main]`; джобы lint/typecheck/test(unit)/integration/handoff-consistency
- Дефект-первопричина: TASK-076 (фикс TASK-074 не гейтился, уехал сломанным)
