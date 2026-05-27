---
id: TASK-040
completed: 2026-05-27
author: claude-opus-4.7
estimate: S → actual: S
related:
  - docs/audit/2026-05-25-mvp-audit.md (sec C-08)
  - handoff/inbox/TASK-040-ci-security-scans.md
---

# TASK-040: Security scanning в CI — отчёт

## Выполнено

### 1. CI workflow (`.github/workflows/ci.yml`)

Добавлены 3 parallel security job'а:

| Job | Инструмент | Проверяет | Fail условие |
|-----|-----------|-----------|--------------|
| `security-sast` | bandit | Python code на инъекции, weak crypto | HIGH/CRITICAL |
| `security-deps` | pip-audit | Зависимости на CVE | Любая уязвимость |
| `security-secrets` | gitleaks | Секреты в коде | Любой match |

Все job'ы запускаются параллельно с lint/test на каждый push/PR в `main`.

### 2. Docker image scan (`.github/workflows/security-image-scan.yml`)

- Отдельный workflow для Trivy scan Docker-образов
- Trigger: push в main, PR, weekly (воскресенье 04:00 UTC)
- Сканирует `infra/Dockerfile.web` и `Dockerfile.bot`
- Выгружает results в GitHub Security (SARIF)
- Fail на HIGH/CRITICAL severity

### 3. Dependabot (`.github/dependabot.yml`)

Настроены 3 ecosystem-а:
- **pip** (weekly, воскресенье): группирует patch/minor обновления в один PR
- **docker** (weekly, воскресенье): обновляет base images
- **github-actions** (weekly, воскресенье): обновляет workflow actions

Группировка уменьшает количество PR, security-обновления приоритетны.

### 4. Инструменты в dev-deps (`pyproject.toml`)

- `bandit>=1.7,<2` — SAST scanning
- `pip-audit>=2.0,<3` — dependency CVE scanning
- `[tool.bandit]` — конфиг bandit (skips B101/assert_used для pytest, B601/paramiko)

### 5. Baseline configs

- `.gitleaks.toml` — allowlist для тестов/fixture (расширить по мере надобности)
- `.trivyignore` — baseline для base-image CVE (документировать каждое исключение)

### 6. Документация (`docs/08-conventions.md`)

Добавлен раздел "Security scanning в CI" с:
- Описанием каждого job'а
- Процедурой reaction на findings
- Dependabot конфигурацией

## First run findings

**ВАЖНО:** Первый прогона CI может найти:
- **Base-image CVE** (python:3.12-slim, postgres:16-alpine, nginx:alpine) → ~50 expected HIGH/CRITICAL
- **False-positives** в bandit (assert в тестах, known patterns) → добавить в allowlist
- **CVE в dependencies** → открыть отдельные TASK-ы на фикс

Это **нормально** и ожидаемо. Задача этого TASK — только setup. Findings из первого прогона будут собраны в follow-up TASK-ах.

## Next steps

1. **Дождаться первого прогона CI** на GitHub Actions
2. **Собрать findings** из каждого job'а (bandit, pip-audit, trivy, gitleaks)
3. **Создать follow-up TASK-и** для реальных уязвимостей
4. **Пополнить allowlist** для документированных false-positives
5. **Настроить GitHub Secrets** для Dependabot (если нужны)

## Ссылки

- Commit: `0e91b52`
- CI workflow: [GitHub Actions](https://github.com/nmetluk/bettgbot/actions)
- Security tab: [GitHub Security](https://github.com/nmetluk/bettgbot/security)
- Dependabot alerts: [Dependabot](https://github.com/nmetluk/bettgbot/dependabot)

## Примечания

1. **Gitleaks license** — опциональна для ускорения сканирования больших репо. Для текущего размера не требуется.
2. **Trivy base-image CVE** — большинство приходят из `debian:bookworm` (python-slim) и `alpine`. Принимаем как baseline, но мониторим upstream patches.
3. **pip-audit strict mode** — fail на любой уязвимости, включая LOW. Можно смягчить до `--vulnerability` если нужно.
4. **Dependabot grouping** — уменьшает inbox noise, но может упустить несовместимые обновления. Monitor PR-конфликты.
