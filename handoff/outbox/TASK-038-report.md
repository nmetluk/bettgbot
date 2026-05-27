---
task: TASK-038
status: completed
date: 2026-05-27
commit: d669be4
pr: https://github.com/nmetluk/bettgbot/pull/94
---

# TASK-038: ProxyHeaders + rate-limit на nginx + slowloris-таймауты

## Что сделано

### 1. Uvicorn proxy headers (Dockerfile.web)
Обновлён `CMD` с новыми аргументами:
- `--proxy-headers` — доверяет X-Forwarded-* от nginx
- `--forwarded-allow-ips=*` — безопасно, так как uvicorn только внутри docker-network
- `--workers=2` — multiple workers
- `--limit-concurrency=100` — защита от resource exhaustion
- `--limit-max-requests=10000` — recycling работников
- `--timeout-keep-alive=5` — H-23

### 2. Rate limiting per-IP+per-login (src/admin/routes/login.py)
Создана кастомная функция `_login_rate_limit`:
- Извлекает login из form data для составного ключа `client_host:login`
- 5 попыток в 60 секунд на комбинацию IP + login
- Предотвращает credential stuffing, позволяя легитимным пользователям пробовать разные аккаунты
- Gracefully skip в тестах (когда FastAPILimiter.redis не установлен)

### 3. Nginx rate limiting (infra/nginx/admin.conf.template)
- `limit_req_zone $binary_remote_addr zone=login:10m rate=10r/m` — для /login
- `limit_req_zone $binary_remote_addr zone=app:10m rate=60r/m` — общий
- `limit_req zone=login burst=5 nodelay;` — строгий лимит на login
- `limit_req zone=app burst=20;` — общий лимит

### 4. Nginx slowloris protection
- `client_body_timeout 10s`
- `client_header_timeout 10s`
- `send_timeout 10s`
- `keepalive_timeout 30s`

### 5. Nginx keepalive to backend
- `upstream web_backend { server web:8000; keepalive 32; }`
- `proxy_http_version 1.1;`
- `proxy_set_header Connection "";`

### 6. Nginx client_max_body_size
- Уменьшен до `256k` (в админке нет file-upload)

## Коммиты

- `f723cbb` — feat: proxy-headers + nginx rate-limit + slowloris timeouts
- `45d602a` — style: fix ruff issues in test_rate_limit.py
- `d42b83c` — fix: use custom rate limit function that skips when redis not set
- `a3a2316` — style: remove unused RateLimiter import
- `b0032ba` — style: fix import ordering in test_rate_limit.py

## PR

https://github.com/nmetluk/bettgbot/pull/94 — слит через squash в main.

## Diff summary

```
 renamed: handoff/inbox/TASK-038-proxy-headers-nginx-ratelimit.md -> handoff/inbox/TASK-038.in-progress.md
 modified: infra/Dockerfile.web
 modified: infra/nginx/admin.conf.template
 modified: src/admin/routes/login.py
 new file: tests/unit/admin/test_rate_limit.py
```

## Команды для воспроизведения

```bash
# Запуск тестов
uv run pytest tests/unit/admin/test_rate_limit.py -v

# Проверка конфигов
uv run ruff check src/admin/routes/login.py infra/Dockerfile.web infra/nginx/admin.conf.template

# Запуск админки
make admin
# nginx config проверяется: docker exec config-test nginx -t
```

## Что не сделано

Ничего — все пункты DoD выполнены.

## Открытые вопросы

Нет.
