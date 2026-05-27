---
id: TASK-051
created: 2026-05-28
author: cowork-agent
parallel-safe: false
blockedBy: []
blocks: [TASK-049, TASK-050]
related:
  - .github/workflows/ci.yml
  - .github/workflows/security-image-scan.yml
  - .github/workflows/handoff-consistency.yml
  - pyproject.toml
  - infra/Dockerfile.bot
  - infra/Dockerfile.web
priority: critical
estimate: M
---

# TASK-051: Сделать CI зелёным на `main` — блокирует TASK-049, TASK-050

## Контекст

При работе над TASK-049 (`feature/TASK-049-…` ветка) выяснилось: **CI на `main` красный** — PR из feature-ветки не может быть смёрджен. Из 6 CI-workflow часть упала ещё в эпоху TASK-037..042 и осталась незамеченной (direct-push в main без branch protection не блокируется красным CI).

**Что уже починено cowork-агентом до публикации этой задачи** (коммит `3efda9e`):

- `handoff-consistency.yml` — 6 flat-файлов `archive/TASK-0{37,38,39,40,41,42}*.md` переименованы в директории `archive/TASK-…/task.md`. Локальная проверка: 0 violations.

Остальное **должно быть проверено и закрыто исполнителем** — у cowork-агента нет доступа к GitHub Actions UI из песочницы.

## Цель

Все 6 workflow зелёные на `main`:

- `ci.yml` → 7 jobs: `lint`, `typecheck`, `test`, `integration`, `security-sast`, `security-deps`, `security-secrets`
- `security-image-scan.yml` → `scan-web`, `scan-bot`
- `handoff-consistency.yml` → ✅ уже зелёный после `3efda9e`
- `build-images.yml` → `build-bot`, `build-web`
- `backup-verify.yml` → еженедельный, не блокер для PR
- `deploy-prod.yml` → ручной, не блокер для PR

После того как `main` зелёный — открыть PR из `feature/TASK-049-…` и убедиться, что CI на PR тоже зелёный.

## Гипотезы по красным jobs (проверять в порядке)

> Это **гипотезы** — точную причину видно только в логах GitHub Actions UI.
> Открой `https://github.com/nmetluk/bettgbot/actions` → последний failed run на main → почитай логи каждого красного job'а **до** того как править.

### 1. `typecheck` (mypy) — после TASK-048

`src/shared/repositories/reminder_dispatch_log.py:58` — `return result.rowcount`.

`CursorResult.rowcount` в SQLAlchemy 2.0 типизирован как `int`, но если `delete().execute()` возвращает плоский `Result` (не `CursorResult`), mypy в strict-mode может ругаться на `Any` или несовпадение типа.

Если красный — два варианта фикса:

- (a) `return result.rowcount or 0` (более терпимо к `None`).
- (b) `from sqlalchemy import CursorResult` + `cast(CursorResult[Any], result).rowcount`.

### 2. `security-deps` (pip-audit --strict) — почти наверняка

```yaml
uv run pip-audit --strict --requirement requirements.txt
```

`--strict` падает на **любом** CVE в зависимостях, включая транзитивные dev-deps. С момента TASK-040 прошло ≥2 дня — новые CVE накопились. **Эту проверку нужно превратить из бинарного блокера в управляемую**:

- Снять `--strict`. Без него pip-audit возвращает 0 если все известные CVE имеют CVE-ID, но падает только если найдено что-то по-настоящему опасное. Альтернатива — keep `--strict` + добавить `--ignore-vuln <CVE-ID>` для известных-неэксплуатируемых.
- Добавить файл `.pip-audit-ignore` или `pyproject.toml` секцию `[tool.pip-audit]` с allow-list текущих CVE.
- Зафиксировать решение в DECISIONS как «P0 PR-блокер только на новые HIGH/CRITICAL, прочее — Dependabot weekly».

### 3. `security-image-scan` (Trivy HIGH,CRITICAL, exit-code 1) — почти наверняка

```yaml
severity: 'HIGH,CRITICAL'
exit-code: '1'
```

Базовый образ `python:3.12-slim` (см. `infra/Dockerfile.{bot,web}`) накапливает HIGH/CRITICAL CVE в системных пакетах (glibc/zlib/openssl) еженедельно. Прецедент в индустрии: жёсткий `exit-code=1` на любой HIGH ловит CVE в `base layer`, который проектная команда не починит — это работа upstream debian-security-tracker.

Фикс:

- Поднять базовый образ до последнего digest (`docker pull python:3.12-slim` локально → новый sha; обновить `infra/Dockerfile.{bot,web}` со `FROM python:3.12-slim@sha256:…` чтобы фиксировать конкретную проверенную версию).
- Если новые CVE остаются — добавить `.trivyignore` файл с конкретными CVE и сроком ревью (комментарий «# pending upstream fix — review 2026-06-15»).
- Альтернатива: понизить `severity` до только `CRITICAL` (HIGH без фикса терпеть), либо добавить `vuln-type: 'os'` allowlist.

### 4. `security-sast` (bandit `-ll -ii`)

`-ll -ii` = severity MEDIUM+ AND confidence MEDIUM+. Бар жёсткий. Возможные срабатывания на свежем коде:

- `try/except/pass` в `dispatch_reminders` (B110).
- `assert` в src/ кроме тестов (B101) — вряд ли, но проверь.
- Hardcoded `bind: "0.0.0.0"` в FastAPI (B104) — точно нет, у нас не так.

Запусти локально `uv run bandit -r src/ -ll -ii -f txt` — увидишь что не нравится.

Если конкретное срабатывание — false positive (например, `# nosec B110` в защищённом контексте), пометить `# nosec B110` с комментарием почему. Если реальная находка — починить код.

### 5. `build-images.yml`

Триггерится на push в main. Если упал — почитай лог. Возможно отсутствует secret `GITHUB_TOKEN` для GHCR push (вряд ли — он автоматический), или Dockerfile ломается после изменений в pyproject.toml (uv.lock прирос +24 пакетами в TASK-048 — может выходить за лимит времени или памяти).

## Definition of Done

- [ ] **Перед фиксом**: открыть `https://github.com/nmetluk/bettgbot/actions`, посмотреть последние failed runs на main, **выписать** в отчёт точный список красных jobs (имя workflow + имя job + первая красная строка лога). Без этого фиксы будут вслепую.
- [ ] Все 5 workflow на main зелёные (`ci.yml`, `security-image-scan.yml`, `handoff-consistency.yml`, `build-images.yml`, плюс верифицировать что `backup-verify.yml`/`deploy-prod.yml` нормально парсятся, даже если не запускались).
- [ ] Если правился `ci.yml` (например, отключение `--strict` у pip-audit, добавление `.trivyignore`, поднятие base image) — изменения в **отдельных commits** с понятным сообщением:
  - `ci(security-deps): drop --strict, manage CVEs via Dependabot + .pip-audit-ignore`
  - `ci(image-scan): pin base image digest + .trivyignore for known os-level CVEs`
  - `ci(sast): bandit nosec markers for justified findings`
  - `chore(deps): bump base image / regenerate lock`
- [ ] `pyproject.toml` или `.pip-audit-ignore`/`.trivyignore` коммитятся с комментариями «# CVE-XXXX-YYYY: <причина игнора>, ревью YYYY-MM-DD».
- [ ] **Записать в `state/DECISIONS.md`** строку: «CI security-gates политика — что блокирует PR, что только нотифицирует». Это снижает риск повторения «CI красный, никто не замечает».
- [ ] После того как main зелёный — открыть PR из `feature/TASK-049-…` и убедиться, что **именно его** CI тоже зелёный. Если в PR'е есть свои красные jobs (например, mypy на новом коде TASK-049) — починить в той же ветке.
- [ ] Этот TASK-051 закрыт стандартно: PR (можно сразу merge в main, поскольку src/ почти не трогается — большинство изменений в `.github/workflows/`, `pyproject.toml`, `infra/Dockerfile.*`), отчёт, **move-семантика inbox→archive с директорией `TASK-051-fix-red-ci/`**.

## Артефакты (ожидаемые)

- `* .github/workflows/ci.yml` — снят `--strict` у pip-audit или добавлен allow-list
- `+ .pip-audit-ignore` ИЛИ `[tool.pip-audit]` в `pyproject.toml` — список временно игнорируемых CVE с датами ревью
- `+ .trivyignore` — список временно игнорируемых OS-уровневых CVE
- `* infra/Dockerfile.bot`, `infra/Dockerfile.web` — base image bump или pin sha
- `* src/shared/repositories/reminder_dispatch_log.py` — фикс mypy, если упал
- `* state/DECISIONS.md` — политика CI security-gates
- `+ handoff/outbox/TASK-051-report.md`

## Подсказки исполнителю

- **Не повышай критичность фикса**: цель — green main, не «убить все security-сканы». Pip-audit/trivy/bandit остаются включёнными, просто перестают быть бинарным блокером.
- **Diagnostic first**: первый коммит должен быть «docs: capture current red-jobs state in TASK-051 report». Только после этого правим CI. Иначе ловишь shadow-failures.
- **Branch protection всё ещё выключен** — после фикса можно direct-push, но **открой PR явно** для этой задачи, чтобы убедиться, что зелёный CI действительно зелёный (а не «не запускался, потому что в main pushed direct»).
- **Что НЕ делать**: не отключать workflow полностью, не выпиливать pip-audit/trivy из pyproject, не комментировать целые jobs. Цель — найти правильный баланс «notify vs block».
