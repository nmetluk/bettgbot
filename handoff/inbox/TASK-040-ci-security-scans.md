---
id: TASK-040
created: 2026-05-25
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: S
---

# TASK-040: Security-сканирование в CI (bandit + pip-audit + trivy + gitleaks + Dependabot)

## Контекст

Аудит MVP 2026-05-25, находка **C-08**. Текущий CI делает только lint (ruff) + typecheck (mypy) + tests + handoff-consistency. Никакого SAST (bandit), CVE-сканирования зависимостей (pip-audit), Docker image scanning (trivy), secret-scanning (gitleaks), Dependabot. Без этого новые CVE в `httpx`, `aiogram`, `bcrypt`, `pydantic` (или их transitive deps) уедут в prod молча.

## Цель

Добавить четыре security-job'а в CI и подключить Dependabot. Все job'ы блокируют merge при HIGH/CRITICAL findings.

## Definition of Done

- [ ] `.github/workflows/ci.yml` — добавлены job'ы (запускаются параллельно с существующими lint/test):
  - `security-sast`: `uv run bandit -r src/ -ll` (severity LOW и выше fail) с allowlist для известных false-positives через `pyproject.toml [tool.bandit]`.
  - `security-deps`: `uv run pip-audit --strict --desc --requirement <(uv pip freeze)` (или `uv pip compile --check`).
  - `security-secrets`: `gitleaks/gitleaks-action@v2` со scan over diff.
- [ ] Новый workflow `.github/workflows/security-image-scan.yml`:
  - Trigger: `push: branches: [main]` + weekly cron.
  - Build образ из `infra/Dockerfile.web` + `Dockerfile.bot`.
  - `aquasecurity/trivy-action@master` со `severity: HIGH,CRITICAL`, `exit-code: 1`.
- [ ] `.github/dependabot.yml`:
  - `package-ecosystem: pip` (root), weekly, with `groups: { security: { patterns: ["*"], update-types: ["patch","minor"] } }`.
  - `package-ecosystem: docker` (`infra/`), weekly.
  - `package-ecosystem: github-actions`, weekly.
- [ ] `pyproject.toml [tool.bandit]` — allowlist (если bandit ругается на `_DUMMY_HASH` или похожее).
- [ ] Все 4 новых job'а проходят зелёными на текущем main (если что-то реально найдено — это сепаратный TASK на фикс; здесь только setup).
- [ ] `docs/08-conventions.md` — добавлен раздел «Security scanning» с описанием каждого job'а и процедуры reaction (`pip-audit` red → CVE-задача).
- [ ] PR в GitHub, имя `TASK-040: add bandit/pip-audit/trivy/gitleaks to CI`.
- [ ] Отчёт в `handoff/outbox/TASK-040-report.md` — перечислены **все** findings из первого прогона (важно: они = технический долг, отдельная backlog-задача).
- [ ] **🚨 Move-семантика + `make backup`**.

## Артефакты

- `* .github/workflows/ci.yml` — 3 новых job'а
- `+ .github/workflows/security-image-scan.yml` — Trivy
- `+ .github/dependabot.yml`
- `* pyproject.toml` — `[tool.bandit]`, dev-deps: `bandit, pip-audit`
- `* docs/08-conventions.md` — раздел Security scanning

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — секция C-08
- Bandit: https://bandit.readthedocs.io/
- pip-audit: https://pypi.org/project/pip-audit/
- Trivy: https://trivy.dev/
- Gitleaks: https://github.com/gitleaks/gitleaks
- Dependabot grouping: https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#groups

## Подсказки

- Если первый run bandit/pip-audit находит CVE — НЕ фиксить в этом TASK. Открыть `TASK-040-followup-<CVE>.md` для каждой, чтобы аудит остался узкосфокусированным.
- Trivy в первый запуск может найти ~50 CVE из base image `python:3.12-slim`. Допустимо принять как baseline через `.trivyignore` файл — задокументировать каждое исключение.
- Gitleaks может ругнуться на тестовый `_DUMMY_HASH` или fixture-токены в тестах — добавь паттерны в `.gitleaks.toml` allowlist.
- Dependabot pull-requests могут переполнить inbox владельца — рекомендуется `groups:` (все pip-обновления одним PR).
