# TASK-031: Deploy README — пошаговая инструкция выкатки на VPS — отчёт

## Что сделано

- **`docs/07-deployment.md`** — полное руководство по выкладке на VPS:
  - Требования к VPS
  - DNS настройка
  - Установка зависимостей
  - Клонирование репо
  - `.env` настройка
  - Certbot bootstrap (двухфазный)
  - Первый запуск
  - Первый бэкап
  - Создание админа
  - Проверка
  - Регулярные операции
  - Откат
- **`infra/nginx/admin-bootstrap.conf`** — http-only конфиг для certbot bootstrap
- **Makefile** — добавлены цели:
  - `prod.certbot.init` — получение первого TLS сертификата
  - `admin.create.prod` — создание админа в prod

## Коммиты

- `3932172` docs(deploy): TASK-031 Deploy README — пошаговая инструкция выкатки на VPS

## Прогон по бумаге

README прошло мысленный walkthrough. Все команды копируемы и последовательны. Учтены известные ограничения:
- Certbot двухфазный bootstrap
- Первый бэкап вручную
- JSON-логи в prod

## PR

https://github.com/nmetluk/bettgbot/pull/83
