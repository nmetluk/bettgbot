---
id: TASK-038
created: 2026-05-25
author: external-auditor
parallel-safe: false
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: S
---

# TASK-038: ProxyHeaders + rate-limit на nginx + slowloris-таймауты

## Контекст

Аудит MVP 2026-05-25, находки **C-06 + M-09 + M-08**. `fastapi-limiter` и `request.client.host` берут IP из непосредственного TCP-peer'а, который в prod = nginx-контейнер (`172.x.x.x`). Это значит: rate-limit на /login (5/60s) глобальный для всех админов (любой credential-stuffer ddosит логин). Логи `audit.log` теряют реальный IP атакующего. Uvicorn запущен без `--proxy-headers --forwarded-allow-ips`.

Также: nginx не имеет `limit_req_zone`, `client_body_timeout`, `client_header_timeout` — Slowloris работает.

## Цель

1. Uvicorn принимает `X-Forwarded-*` от nginx → `request.client.host` = реальный IP клиента.
2. `fastapi-limiter` лимитирует per-IP+login (не глобально).
3. nginx добавляет `limit_req_zone` для `/login` (10r/m, burst=5) и общий `app` zone (60r/m).
4. nginx закрывает slowloris через короткие client-таймауты.
5. nginx использует HTTP/1.1 keep-alive до backend.

## Definition of Done

- [ ] `infra/Dockerfile.web` — `uvicorn ... --proxy-headers --forwarded-allow-ips="*" --workers 2 --limit-concurrency 100 --limit-max-requests 10000 --timeout-keep-alive 5` (учитывает также H-23).
- [ ] `src/admin/routes/login.py` — кастомный identifier для `RateLimiter`: комбинация `request.client.host + login` (через `RateLimiter(times=..., identifier=lambda r: f"{r.client.host}:{form.get('login','')}")` или wrapper).
- [ ] `infra/nginx/admin.conf.template`:
  - В http-block: `limit_req_zone $binary_remote_addr zone=login:10m rate=10r/m; limit_req_zone $binary_remote_addr zone=app:10m rate=60r/m;`
  - В location =/login: `limit_req zone=login burst=5 nodelay;`
  - В location /: `limit_req zone=app burst=20;`
  - Slowloris-таймауты: `client_body_timeout 10s; client_header_timeout 10s; send_timeout 10s; keepalive_timeout 30s;`
  - Keep-alive до backend:
    ```
    upstream web_backend { server web:8000; keepalive 32; }
    location / {
        proxy_pass http://web_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        ...
    }
    ```
  - `client_max_body_size 256k;` (вместо 1m — у админки нет file-upload).
- [ ] Integration-test или e2e через `httpx`: POST /login 11 раз с одного IP → 11-й вернёт 429.
- [ ] PR в GitHub, имя `TASK-038: proxy-headers + nginx rate-limit + slowloris timeouts`.
- [ ] Отчёт в `handoff/outbox/TASK-038-report.md`.
- [ ] **🚨 Move-семантика + `make backup`**.

## Артефакты

- `* infra/Dockerfile.web` — uvicorn args
- `* infra/nginx/admin.conf.template` — rate-limit + timeouts + keepalive
- `* src/admin/routes/login.py` — кастомный identifier для лимитера

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — C-06, M-09, M-08, H-23
- Starlette ProxyHeaders: https://www.starlette.io/middleware/#trustedhostmiddleware
- fastapi-limiter custom identifier: https://github.com/long2ice/fastapi-limiter#identifier

## Подсказки

- `--forwarded-allow-ips="*"` — допустимо ТОЛЬКО когда uvicorn слушает за trusted nginx (то есть только внутри docker-network). Не открывать наружу.
- Алгоритм извлечения IP из `X-Forwarded-For` — берём **левый-most не trusted** (стандартный шаблон, ProxyHeaders делает это сам).
- `fastapi-limiter` API: identifier — async callable, возвращает string. Можно сделать `async def login_identifier(request): form = await request.form(); return f"{request.client.host}:{form.get('login','')}"`.
- На время теста удобно поднять отдельный Redis в conftest и сбрасывать ключи между тестами.
