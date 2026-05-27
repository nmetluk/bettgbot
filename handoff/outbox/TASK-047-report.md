---
task: TASK-047
completed: 2026-05-27
agent: claude-opus-4-7
status: done
branch: main
commit: 87e101c
---

# TASK-047: Закрыть HTTP-only прод-логин админки

## Сводка

Критическая уязвabilidad безопасности — админка на `http://5.188.88.78:8888` передавала логин/пароль в открытом виде. Реализован минимальный защитный вариант (путь №2 из задачи): port 8888 ограничен до `127.0.0.1`, доступ только через ssh-tunnel.

**Выбранный вариант:** ssh-tunnel-only access (self-signed TLS не реализован в рамках этой задачи).

## Выполненные изменения

### 1. Infra изменения

**`infra/docker-compose.prod-no-domain.yml`:**
- Изменён port mapping: `127.0.0.1:8888:80` (было `8888:80`)
- Добавлен DANGER warning в шапку файла

**`infra/nginx/admin-no-domain.conf`:**
- Обновлён warning-комментарий с явным указанием на ssh-tunnel

### 2. Makefile runtime warnings

**`Makefile`:**
- Добавлен блок предупреждений перед секцией `prod.nodomain.*`
- `prod.nodomain.up` теперь показывает warning и 2-секундную паузу

### 3. Документация

**`docs/07-deployment.md`:**
- Добавлена секция "⚠️ Режим БЕЗ домена (no-domain) — только для закрытых сетей"
- Описан ssh-tunnel доступ
- Перечислены ограничения no-domain режима
- Инструкция по переходу на полноценный прод с доменом

**`docs/runbook-dr.md`:**
- Добавлена секция "Доступ к админке" с двумя вариантами (HTTPS / ssh-tunnel)

## Что НЕ сделано (по design)

1. **Self-signed TLS** — не реализован, оставлен как возможное улучшение
2. **Домен + Let's Encrypt** — требует действий владельца (покупка домена)
3. **Tailscale/WireGuard** — не реализован, оставлен как возможное улучшение
4. **Ротация секретов** — требует действий владельца (сменить пароли, ADMIN_SECRET_KEY, ADMIN_CSRF_SECRET)

## Следующие шаги для владельца

1. **Настроить домен + HTTPS** (см. `docs/07-deployment.md` Шаг 4):
   - Купить домен
   - Настроить DNS A-запись
   - Запустить `make prod.certbot.init`
   - Перейти на `make prod.up`

2. **Ротировать секреты** (пароли могли быть перехвачены до фикса):
   ```bash
   # Сменить все админские пароли
   make admin.create.prod LOGIN=admin PASSWORD="new_secure_password"

   # Ротировать ADMIN_SECRET_KEY и ADMIN_CSRF_SECRET в .env
   # (сгенерировать: python -c "import secrets; print(secrets.token_urlsafe(64))")
   make prod.up
   ```

3. **Smoke-проверка после фикса:**
   ```bash
   # Должно быть connection refused (порт закрыт для интернета)
   curl -I http://5.188.88.78:8888/login
   ```

## Безопасность

| Было | Стало |
|------|-------|
| Порт `8888` на `0.0.0.0` (публичный) | Порт `8888` на `127.0.0.1` (localhost only) |
| HTTP открыто для интернета | HTTP только через ssh-tunnel |
| Пароли в plain text для MITM | Пароли зашифрованы через SSH |

## Artefacts

- `* infra/docker-compose.prod-no-domain.yml` — `127.0.0.1:8888:80` + DANGER warning
- `* infra/nginx/admin-no-domain.conf` — обновлённый warning
- `* Makefile` — runtime warnings для prod.nodomain.* целей
- `* docs/07-deployment.md` — новая секция про no-domain режим
- `* docs/runbook-dr.md` — ssh-tunnel инструкции
- `+ handoff/outbox/TASK-047-report.md` — этот отчёт
