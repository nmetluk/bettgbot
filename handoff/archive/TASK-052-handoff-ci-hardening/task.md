---
id: TASK-052
created: 2026-05-28
author: cowork-agent
parallel-safe: false
blockedBy: []
blocks: []
related:
  - .github/workflows/handoff-consistency.yml
  - .github/workflows/security-image-scan.yml
  - pyproject.toml
  - src/shared/config.py
  - handoff/templates/report.md
  - CLAUDE.md
priority: high
estimate: S
---

# TASK-052: Закрыть тех-долг из TASK-051 — harden handoff-CI + откатить регрессии

## Контекст

TASK-051 закрыл красный CI, но оставил три категории тех-долга, которые нужно подобрать **до запуска TASK-049/050**, чтобы не накапливать дальше:

1. **Handoff-CI пропустил странную archive-structure** в TASK-051: исполнитель положил `handoff/archive/TASK-051-fix-red-ci-task.md/TASK-051-fix-red-ci.md` (директория с `-task.md` в имени + файл-копия имени задачи). Текущий `handoff-consistency.yml` проверяет только (a) flat-файлы наверху archive и (b) inbox-orphans, но не «внутри каждой `TASK-NNN-<slug>/` есть `task.md`».
2. **Regression по mypy strictness**: TASK-051 заменил 3 точечных `# type: ignore[arg-type]` на module-wide `disable_error_code = ["arg-type", "assignment"]` для `src.shared.config` — это масштабнее, чем требовалось.
3. **Trivy практически отключён** (`exit-code: '0'` = не падает ни на чём). `.trivyignore` allow-list — правильный паттерн, но `exit-code: 0` превращает его в decoration.
4. **Pytest 9.x bump** без явной мотивации — risky major version bump.
5. **9 случаев подряд отсутствия `handoff/outbox/TASK-NNN-report.md`.** DoD-пункт «Отчёт» систематически пропускается, cowork каждый раз восстанавливает ретроспективно. Нужно (а) усилить enforce, (б) понять корневую причину.

## Цель

Все 5 пунктов закрыть точечными изменениями; CI должен остаться зелёным после.

## Definition of Done

### (1) Расширить `handoff-consistency.yml`

В `.github/workflows/handoff-consistency.yml` добавить третью проверку:

```bash
# (3) В каждой handoff/archive/TASK-NNN-<slug>/ должен быть файл task.md
echo "→ Проверка task.md в archive-директориях..."
for dir in handoff/archive/TASK-*/; do
  [ -d "$dir" ] || continue
  if [ ! -f "${dir}task.md" ]; then
    echo "❌ Archive directory без task.md: $dir"
    echo "   Внутри должен быть файл task.md (не TASK-NNN-<slug>.md)."
    violations=$((violations + 1))
  fi
done
```

Локально проверить, что текущее состояние main проходит (все TASK-001..051 имеют `task.md` внутри).

### (2) Откатить module-wide mypy-disable на `src/shared/config.py`

В `pyproject.toml` убрать блок:

```toml
[[tool.mypy.overrides]]
module = ["src.shared.config"]
disable_error_code = ["arg-type", "assignment"]
```

Вернуть точечные `# type: ignore[arg-type]` на 3 строки `Field(default_factory=…)` в `Settings`:

```python
admin: AdminSettings = Field(default_factory=AdminSettings)  # type: ignore[arg-type]
backup: BackupSettings = Field(default_factory=BackupSettings)  # type: ignore[arg-type]
observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)  # type: ignore[arg-type]
```

Прогнать `uv run mypy src/shared src/bot src/admin` локально — должно быть зелёно. Если нет — детализировать комментарием почему именно `arg-type` (типовая pydantic-settings + Field+default_factory несовместимость).

### (3) Trivy soft-block на CRITICAL

В `.github/workflows/security-image-scan.yml` для обоих job'ов:

```yaml
severity: 'CRITICAL'
exit-code: '1'                # ← вернуть hard-block, но только на CRITICAL
trivyignores: .trivyignore
ignore-unfixed: true
```

Это значит: HIGH и LOW не блокируют, CRITICAL без фикса с upstream — блокирует, но в `.trivyignore` можно прописать allow-list (как сейчас). Текущие 5 ignored CVE остаются.

### (4) Pytest version: либо обосновать, либо откатить

В `pyproject.toml`:

- **Если** есть конкретная причина перейти на pytest 9.x (CVE, нужная фича) — оставить, но добавить комментарий с CVE-ID или ссылкой на feature, и зафиксировать в `state/DECISIONS.md` строку «Pytest 9.x adoption — обоснование такое-то».
- **Иначе** — откатить до `"pytest>=8.2,<10"` и `"pytest-asyncio>=0.23,<2"` (расширить верхнюю границу, но не форсить major bump).

### (5) Усилить DoD enforcement на «Отчёт»

Текущий статус: 9 задач подряд (TASK-043, 047, 048, 051) пропустили `handoff/outbox/TASK-NNN-report.md`. Cowork каждый раз восстанавливает ретроспективно — это не масштабируется.

Что сделать:

- **`.github/workflows/handoff-consistency.yml`**: добавить четвёртую проверку — для каждой `handoff/archive/TASK-NNN-<slug>/` должен быть либо `handoff/outbox/TASK-NNN-report.md`, либо `handoff/archive/TASK-NNN-<slug>/report.md`. Один из двух (отчёт может лежать в archive после закрытия — оба варианта валидны).
  
  ```bash
  # (4) У каждой архивной задачи должен быть report
  echo "→ Проверка отчётов..."
  for dir in handoff/archive/TASK-*/; do
    task_id=$(basename "$dir" | grep -oE '^TASK-[0-9]+')
    [ -z "$task_id" ] && continue
    outbox="handoff/outbox/${task_id}-report.md"
    archive_report="${dir}report.md"
    if [ ! -f "$outbox" ] && [ ! -f "$archive_report" ]; then
      echo "❌ $task_id: нет ни ${outbox}, ни ${archive_report}"
      violations=$((violations + 1))
    fi
  done
  ```
  
- В `handoff/templates/task.md` добавить **в самое начало** DoD-секции крупный 🚨-баннер:
  
  ```
  > 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
  > `handoff/outbox/TASK-NNN-report.md`.** Без отчёта CI handoff-consistency
  > красный, PR не мёрджится. Шаблон — `handoff/templates/report.md`.
  ```
  
- В `CLAUDE.md` (исполнитель читает каждую сессию) — поднять секцию «Что обязано быть в отчёте» выше, перенумеровать ToC.

### (6) Записать в `state/DECISIONS.md`

Одну строку: «Handoff-consistency CI расширен до 4 проверок: flat-files, inbox-orphans, `task.md` в archive-dir, `report.md` существует. Цель — закрыть pattern из 9 нарушений конвенции подряд.»

### (7) Закрытие задачи

- PR `TASK-052: harden handoff-CI + revert TASK-051 regressions` через feature-branch (есть изменения в `src/`/`pyproject.toml`, поэтому не direct-push).
- Локальный прогон `bash <(awk '/^      - name: Check archive/,/echo "✓ handoff-инварианты/' .github/workflows/handoff-consistency.yml)` (или скриптом из (1)+(5)) должен показать 0 violations.
- Все CI-jobs зелёные на PR.
- `handoff/outbox/TASK-052-report.md` — **обязательно**, новые CI-проверки тебя заблокируют, если забудешь.
- Move-семантика: `handoff/inbox/TASK-052-….md` → `handoff/archive/TASK-052-<slug>/task.md` (директория, файл `task.md`!).

## Артефакты

- `* .github/workflows/handoff-consistency.yml` — +2 проверки (task.md, report.md)
- `* pyproject.toml` — убран mypy module-disable; pytest версия (обоснована или откачена)
- `* src/shared/config.py` — возвращены точечные `# type: ignore[arg-type]`
- `* .github/workflows/security-image-scan.yml` — `exit-code: 1` назад на CRITICAL
- `* handoff/templates/task.md` — 🚨-баннер про обязательный report
- `* CLAUDE.md` — секция отчёта поднята
- `* state/DECISIONS.md` — 1 строка про расширение handoff-CI
- `+ handoff/outbox/TASK-052-report.md`

## Подсказки исполнителю

- **Сначала фикси (1) и (5)** (handoff-CI расширение) — это «защитный слой» для самой задачи. Если в ходе работы случайно нарушишь convention, новые проверки тебя предупредят локально, а не задним числом.
- **Не комбинируй с TASK-049/050.** Это отдельная гигиеническая задача, чтобы потом 049/050 проходили чище.
- **Тестируй CI-bash локально**: `cd /path/to/repo && bash -c '<скрипт из (1)+(5)>'`. На текущем main всё должно показывать 0 violations.
- **Если pytest 9.x бьёт где-то в тестах** — лучше откатиться. Стабильность тестов важнее свежей версии.
