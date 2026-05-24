# Решения — task-031-review

## Новое решение

1. **CI-check `handoff-consistency.yml` как server-side enforcement** инварианта move-семантики inbox→archive. Триггер: **4 случая подряд** workflow violation (TASK-028..031), несмотря на explicit-секцию в `handoff/README.md` и 🚨-DoD-пункт в `handoff/templates/task.md`. Локальные напоминания не работают — CC их игнорирует или не видит. CI-check блочит merge в main: для каждой папки `handoff/archive/TASK-NNN-*/` проверяет, нет ли `TASK-NNN*` в `handoff/inbox/`. Если есть — fail с явным сообщением «git rm handoff/inbox/TASK-NNN-<slug>.md» и ссылкой на README.

## Подтверждённые keep (review TASK-031)

| # | Решение | Обоснование |
|---|---|---|
| 1 | `admin-bootstrap.conf` — отдельный http-only config для bootstrap | Чище, чем менять admin.conf.template туда-сюда. |
| 2 | `admin.create.prod` через `exec -T web python scripts/create_admin.py` | uv не нужен в prod, прямой python в running web-контейнере. |
| 3 | README реорганизация — высокоуровневое описание сверху, пошаговый walkthrough снизу в одном файле `docs/07-deployment.md` | Один источник, без путаницы «где смотреть». |
| 4 | Двухфазный bootstrap certbot (http-only → certonly → full-TLS) | Стандартное решение курицы-яйца. Альтернатива (certbot DNS challenge) требует API ключей провайдера DNS — за MVP. |

## Hotfix-правки от cowork-агента

1. **Makefile `prod.certbot.init`:** добавлен `--entrypoint=""`. Без него `run --rm certbot certonly ...` уходил аргументами к существующему entrypoint (бесконечный renew-loop), а не вызывал certbot certonly. Без фикса первый сертификат не выпустился бы на VPS.
2. **Inbox cleanup:** `git rm handoff/inbox/TASK-031-deploy-readme.md` + `git rm handoff/inbox/TASK-031.in-progress.md` (4-й повтор подряд).
3. **`.github/workflows/handoff-consistency.yml`:** см. новое решение №1 выше.
4. **`make backup`** через cowork-канал — Drive обновлён.

## Тех-долг

- **`handoff/templates/report.md`** — добавить требование «прогон опасных команд на dev-stack» (не просто «walkthrough пройден мысленно»). Если CC снова поставит блокер из-за неполного теста — реализовать.
- **README-validation тест** для `docs/07-deployment.md` — можно сделать в TASK-032 (или отдельной micro-задачей): bash-скрипт, который парсит README и проверяет, что упомянутые команды существуют в Makefile.
