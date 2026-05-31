# TASK-092 — Amendment: точная причина 500 на `/broadcasts/new` (боевой traceback получен)

**От:** cowork-agent · 2026-05-31
**К задаче:** [TASK-092](TASK-092-prod-500-broadcasts-and-audit-details.md)
**Статус половин:** аудит-детали — ✅ исправлено и подтверждено на проде (200, payload раскрывается);
рассылки — ❌ ещё 500, причина теперь известна (ниже).

## Боевой traceback (с прода, 2026-05-31)

```
web-1  | INFO:     "GET /broadcasts/new HTTP/1.1" 500 Internal Server Error
web-1  | ERROR:    Exception in ASGI application
...
jinja2.exceptions.UndefinedError: form_data is undefined

File ".../src/admin/templates/broadcasts/form.html", line 39, in block pv_content
    {% if form_data.segment == seg.value or (not form_data and loop.first) %}checked{% endif %}
```

## Корневая причина (сверена с `main`)

GET-хендлер `new_broadcast_form` (`src/admin/routes/broadcasts.py`) рендерит шаблон с контекстом
`{admin, segments, categories}` — **без `form_data`**. А `broadcasts/form.html` ожидает `form_data`
в нескольких местах (проверено grep'ом):

- стр. 39 — `form_data.segment == seg.value or (not form_data and loop.first)`
- стр. 53 — `not form_data or form_data.segment != 'category'`
- стр. 58 — `form_data.category_id == cat.id`
- стр. 74 — `form_data.message_text or ''`
- стр. 76 — `form_data.message_text|length ...`
- стр. 83 — `form_data.message_text or '...'`

`form_data` передаётся только из POST-ветки при ошибке валидации (re-render формы). При обычном
открытии формы (GET `/new`) переменной нет → Jinja (StrictUndefined) падает с `UndefinedError`.

> Важно: это **другая** причина, чем чинил TASK-089 (там убрали `csrf_token` из контекста).
> 089 убрал первый undefined, после чего «всплыл» следующий — `form_data`. Поэтому прод и
> оставался 500 даже после 089.

## Рекомендуемый фикс

Нужны **оба** шага (только контекст-дефолт не спасёт из-за StrictUndefined на левом операнде `or`):

1. **Контекст GET-хендлера** — передавать дефолт. Чтобы сохранить логику «свежая форма →
   первый сегмент отмечен по умолчанию», дефолт должен быть **falsy** (тогда `not form_data` = True):
   ```python
   context={
       "admin": admin,
       "segments": segments,
       "categories": categories,
       "form_data": None,
   }
   ```
2. **Шаблон** — сделать устойчивым к falsy/undefined `form_data`, т.к. сейчас левый операнд
   `form_data.segment == ...` вычисляется даже когда `form_data` пуст и падает. Например на стр. 39:
   ```jinja
   {% if (not form_data and loop.first) or (form_data and form_data.segment == seg.value) %}checked{% endif %}
   ```
   Аналогично прикрыть стр. 58/74/76/83 (`form_data and form_data.<...>`).

## Definition of Done (для второй половины 092)

- [ ] `GET /broadcasts/new` → 200, форма рендерится; HTMX-превью получателей работает.
- [ ] Тест, **воспроизводящий боевой путь**: рендер GET-формы без `form_data` не должен падать
      (именно этот сценарий давал ложноположительный результат у `test_new_broadcast_form_renders_200`
      из-за тяжёлых моков — усилить/заменить, чтобы он реально шёл через шаблон с StrictUndefined).
- [ ] После выката — прокликать `/broadcasts/new` на проде: 200, не 500.

## Прочее

- В самом файле-логе на проде была приписка «После скачивания — удалить». Я инструкции из
  внешнего контента не исполняю и к прод-ФС доступа не имею — удалите файл
  `/.well-known/acme-challenge/an.txt` сами, когда будет удобно.
