# Решения — task-027-review

## Новые архитектурные/процессные решения

1. **Cowork-PAT для read/write доступа к репо.** Cowork-агент теперь имеет fine-grained GitHub PAT с правами Contents: write + Pull requests: write на `nmetluk/bettgbot`. Хранится локально на машине владельца в `.gh_pat` (в `.gitignore`, никогда не коммитится). Использование: `git fetch/push` через `https://x-access-token:${PAT}@github.com/...` (credential helper в sandbox). Снимает зависимость от того, что cowork «видит» репо только через MCP Google Drive коннектор. Применение — для всех будущих сессий cowork.

2. **Локальный squash + `git push origin main` как фоллбэк для merge.** Когда api.github.com заблокирован HTTPS-прокси cowork-sandbox (стандартный случай), cowork делает `git merge --squash <branch> && git commit -m '...' && git push origin main`. Branch protection на main отложен (см. DECISIONS 2026-05-22), поэтому push проходит. **Trade-off:** PR-object на GitHub не создаётся (нет страницы review, нет связанных комментариев), но git-history полная и conventional-commit message содержит ссылку на исходную ветку. **Применять только когда** (а) api.github.com недоступен И (б) изменения изолированы в инфра-зоне (`infra/`, `handoff/`, `state/`, `sessions/`, `Makefile`, `scripts/`, `.gitignore`). Для src/tests — нет, ждать обычного PR-цикла.

3. **Cowork code-fix self-service.** Cowork-агент может **сам применить hotfix-правки** в зонах не-src/не-tests когда (а) обнаружил блокер, (б) локальный CC недоступен, (в) задержка опасна (например, продовый deploy). Прецедент — TASK-027 hotfix `19552fc`. Это исключительная мера, не норма. Если повторится 2-3 раза — формализовать в `CLAUDE.md`/`handoff/README.md`.

4. **nginx envsubst через `/etc/nginx/templates/`.** Паттерн для всех nginx-конфигов с runtime-переменными: файл с суффиксом `.template`, mount в `/etc/nginx/templates/`, переменные перечислены в `environment:` блоке сервиса nginx. Образ nginx сам прогоняет через envsubst при entrypoint. Альтернатива (`/etc/nginx/conf.d/` напрямую) **не работает** — nginx не делает envsubst для conf.d. Прецедент — TASK-027 hotfix.

5. **Compose v2: `-f base.yml` отключает auto-merge override.** Если в Makefile-переменной `COMPOSE` указан явный `-f infra/docker-compose.yml`, `infra/docker-compose.override.yml` **не подхватывается автоматически**. Решения: либо `COMPOSE += -f override.yml`, либо `profiles:` дублируются в base. Прецедент — TASK-027 hotfix. Зафиксировать в `docs/07-deployment.md` при ближайшем обновлении.

## Подтверждённые keep (review TASK-027)

Эти решения остаются как есть (или встроены в hotfix):

| # | Решение | Обоснование |
|---|---|---|
| 1 | Multi-stage Dockerfile с `uv sync --no-install-project` | Code приходит через `COPY src` + `PYTHONPATH=/app`. Соответствует ADR-0004. uv-кэш в builder layer. |
| 2 | `python:3.12-slim` + `libpq5` в runtime | Минимальный образ с нужной зависимостью для psycopg2/asyncpg. |
| 3 | Non-root user `bb` | Стандартная практика безопасности. |
| 4 | `EXPOSE 8000` только в web Dockerfile | bot — long-polling, не нуждается в exposure. |
| 5 | Healthcheck bot через `from src.shared.config import get_settings; get_settings()` | Слабый (проверяет config-load, не Telegram API), но adequate для long-polling. Чище healthcheck требует подключения к Telegram, что добавляет network dep. |
| 6 | certbot в loop через `while :; do certbot renew; sleep 12h` | Стандартная схема. Bootstrap первого certs — задача TASK-031 Deploy README. |

## Тех-долг (зафиксировано)

- **`docs/07-deployment.md`** — обновить с учётом compose v2 правила про `-f override.yml` (триггер: ближайшая правка `docs/07-deployment.md`, например в TASK-031).
- **`make prod.certbot.init`** Makefile-target для первого выпуска certs (либо явное упоминание в TASK-031).
- **Формализация cowork-hotfix self-service** — если повторится 2-3 раза, прописать в `CLAUDE.md`/`handoff/README.md`.
