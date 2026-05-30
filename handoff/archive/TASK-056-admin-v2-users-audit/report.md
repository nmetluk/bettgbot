# TASK-056 Report: Переверстать пользователей и аудит-лог в дизайн v2

## Что сделано

### Перевёрстка в дизайн v2

1. **users/list.html** — список пользователей:
   - Поиск по телефону, username или имени
   - Таблица с колонками: ID, Пользователь (с аватаром), Телефон, Telegram, Прогнозов, Регистрация, Доступ
   - Флаг is_blocked отображается бейджем (заблокирован/активен)
   - Пагинация
   - Переход на карточку пользователя по клику на строку

2. **users/detail.html** — карточка пользователя:
   - Хлебные крошки
   - Заголовок с username и статусом
   - Кнопки блокировки/разблокировки
   - Профиль: аватар, статус, поля (Телефон, Telegram ID, Username, Регистрация, Был онлайн)
   - Статистика: точность и количество прогнозов
   - Таблица прогнозов с колонками: Событие, Категория, Выбор, Статус события, Результат

3. **audit/list.html** — аудит-лог:
   - Заголовок с кнопкой «Экспорт CSV» (плейсхолдер)
   - Фильтры: админы, действия, период (since/until)
   - Таблица с колонками: Время, Администратор (с аватаром), Действие, Описание
   - Раскрытие payload по клику через HTMX
   - Пагинация

4. **audit/_preview.html, audit/_details.html** — HTMX-фрагменты для раскрытия payload в v2-стиле

### Консолидация base-шаблонов

Все экраны админки переведены на дизайн v2, поэтому:
- Старый `base.html` удалён (`git rm`)
- `base_v2.html` переименован в `base.html`
- Все `{% extends "base_v2.html" %}` обновлены на `{% extends "base.html" %}`
- В `src/admin/templates/` остаётся **один** base-шаблон

## Что НЕ сделано и почему

- **Страница roadmap** — осознанно не реализована в продакшене (как указано в задаче, это каталог пост-MVP-фич из прототипа)

## Открытые вопросы

Нет

## Команды для воспроизведения локально

```bash
# Запуск админки (после установки зависимостей)
uvicorn src.admin.app:app --reload

# Линтер
ruff check src/admin/
```

## Diff-сводка по затронутым файлам

### Новые/изменённые шаблоны

- `src/admin/templates/users/list.html` — перевёрстан в v2
- `src/admin/templates/users/detail.html` — перевёрстан в v2
- `src/admin/templates/audit/list.html` — перевёрстан в v2
- `src/admin/templates/audit/_preview.html` — адаптирован для v2
- `src/admin/templates/audit/_details.html` — адаптирован для v2

### Обновлены для консолидации base

- `src/admin/templates/base.html` — бывший base_v2.html (единый base)
- `src/admin/templates/dashboard.html` — extends обновлён
- `src/admin/templates/login.html` — extends обновлён
- `src/admin/templates/categories/list.html` — extends обновлён
- `src/admin/templates/categories/form.html` — extends обновлён
- `src/admin/templates/events/list.html` — extends обновлён
- `src/admin/templates/events/form.html` — extends обновлён

### Удалены

- `src/admin/templates/base_v2.html` — переименован в base.html
- старый `src/admin/templates/base.html` — удалён (Bootstrap 5 версия)

## Git

- Branch: `feature/TASK-056-admin-v2-users-audit`
- Commit: `e031328`
- PR: https://github.com/nmetluk/bettgbot/pull/114
