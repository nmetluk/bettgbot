---
id: TASK-047
created: 2026-05-27
author: external-auditor
parallel-safe: false
blockedBy: []
related:
  - infra/docker-compose.prod-no-domain.yml
  - infra/nginx/admin-no-domain.conf
  - state/PROJECT_STATUS.md
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: M
---

# TASK-047: 🚨 Закрыть HTTP-only прод-логин админки (5.188.88.78:8888) — пароль летит plain text

## Контекст

**Это новая находка ревью 2026-05-27, не покрытая аудитом 2026-05-25.** Auditor работал по `infra/docker-compose.prod.yml` (nginx + certbot + TLS) и принял за prod-конфигурацию её. Но реально на VPS работает другая компоновка — `infra/docker-compose.prod-no-domain.yml` + `infra/nginx/admin-no-domain.conf`, оформленная как owner direct-commit `76d895c` от 2026-05-26 (см. `state/PROJECT_STATUS.md` строка 152).

Что мы имеем сейчас на проде (`5.188.88.78:8888`):

```nginx
# infra/nginx/admin-no-domain.conf
server {
    listen 80;
    server_name _;
    ...
    location / {
        proxy_pass http://web:8000;
        proxy_set_header X-Forwarded-Proto $scheme;  # = "http"
    }
}
```

```yaml
# infra/docker-compose.prod-no-domain.yml
nginx:
    ports:
      - "8888:80"        # HTTP на 0.0.0.0:8888 в публичном интернете
```

В файле даже есть собственный комментарий-самопризнание:
> «Не содержит HTTPS — передавать логин/пароль по открытому соединению **НЕБЕЗОПАСНО!** Использовать только для тестирования или в доверительной сети.»

Но это **никак не enforce'ится**: prod уже принимает live-трафик через `5.188.88.78:8888`. Любой PCAP/MITM на пути от админа до VPS читает:
- `POST /login` с cleartext login + password в form-body.
- `bb_admin_session` cookie (без `Secure` flag, потому что `environment != "prod"` отключает Secure, либо `environment=prod` ломает cookie на http) → session hijacking.
- CSRF cookie + token (можно мгновенно реиграть на чужой сессии).

Связанная подзасада: `Settings.environment` default = `"dev"` (`src/shared/config.py:141`). Если в `.env` на VPS нет строки `ENVIRONMENT=prod`, Secure-cookie всё равно отключен — но даже если выставить prod, браузер откажется ставить Secure-cookie на http-сайт → петля логина (закрытая M-05 решением для domain-сетапа, но не для no-domain).

**Severity Critical — это активно эксплуатируемый прод-issue, не теоретический.**

## Цель

Закрыть HTTP-only канал к prod-админке. Один из трёх путей в порядке предпочтения; владелец выбирает в комментарии к задаче:

1. **Рекомендуемое:** купить домен + переехать на `infra/docker-compose.prod.yml` (certbot + Let's Encrypt). Bootstrap-процедура уже описана в `docs/07-deployment.md` (расширен TASK-031).
2. **Минимальная защита без домена:** self-signed TLS на nginx + ssh-tunnel-only access (закрыть 8888 на 0.0.0.0, открыть только на 127.0.0.1, админ ходит через `ssh -L 8888:127.0.0.1:8888`). Принимаемо для соло-VPS.
3. **Временный костыль:** Tailscale/WireGuard mesh + admin доступен только по mesh-IP. Скрывает порт из публичного интернета совсем.

После любого варианта — **сменить пароль(и) всех админов и ротировать `ADMIN_SECRET_KEY`/`ADMIN_CSRF_SECRET`**, поскольку текущие могли быть перехвачены за время работы 8888/http.

## Definition of Done

- [ ] Выбран и реализован один из путей выше (или эквивалентный).
- [ ] Порт `8888` либо закрыт совсем (`ports: ["127.0.0.1:8888:80"]`), либо обслуживает HTTPS.
- [ ] `Settings.environment = "prod"` в prod-`.env`; Secure-cookie работает.
- [ ] Все админ-пароли сменены через `scripts/create_admin.py`; `ADMIN_SECRET_KEY` и `ADMIN_CSRF_SECRET` ротированы (см. TASK-034 — там валидатор не пускает dev-значения).
- [ ] `infra/docker-compose.prod-no-domain.yml` и `infra/nginx/admin-no-domain.conf` либо удалены, либо в их шапке явный `# DEV/TESTING ONLY, NOT FOR PUBLIC PROD` + Makefile-цели `prod.nodomain.*` помечены аналогично с runtime-warning.
- [ ] `docs/07-deployment.md` дополнен явным разделом «No-domain режим — только для closed-network».
- [ ] Smoke-проверка: `curl -I http://5.188.88.78:8888/login` либо возвращает `301 → https://...`, либо connection refused.
- [ ] PR `TASK-047: close http-only admin login on prod`.
- [ ] Отчёт в `handoff/outbox/TASK-047-report.md`.
- [ ] **🚨 Move-семантика inbox→archive.**

## Артефакты

- `* infra/docker-compose.prod-no-domain.yml` — либо `127.0.0.1:8888:80`, либо удаление.
- `* infra/nginx/admin-no-domain.conf` — либо `# DANGER` баннер + 127.0.0.1, либо удаление.
- `* Makefile` — цели `prod.nodomain.*` с warning-баннером (см. правило L-07 из аудита).
- `* docs/07-deployment.md` — секция про no-domain режим и его ограничения.
- `* .env` на VPS — `ENVIRONMENT=prod` (вручную владельцем).
- (Возможно) `+ infra/docker-compose.prod.yml` поднят с certbot.

## Подсказки исполнителю

- Эта задача **частично пересекается с TASK-034** (валидация секретов): закрыть надо вместе, чтобы после поднятия HTTPS не остаться с dev-секретами.
- Auditor предлагал в `M-05/H-19` HSTS `includeSubDomains; preload`, OCSP stapling, Mozilla Intermediate cipher list — это входит в полноценный фикс пути №1, но не блокирует MVP-defence (план: tunnel-only).
- Учти, что для self-signed варианта браузер админа будет ругаться — приемлемо, но документируй.
