---
task: TASK-077
status: blocked
question: permissions
---

# Вопрос: PAT недостаточно прав для TASK-077

## Что нужно

TASK-077 требует изменений repo settings и branch protection через GitHub API:
- `gh api repos/nmetluk/bettgbot -X PATCH -F allow_auto_merge=true` 
- `gh api repos/nmetluk/bettgbot/branches/main/protection --input - <<JSON`

## Проблема

Текущий PAT даёт `HTTP 403` на эти операции. Нужен token с областью `admin:repo` или полными правами admin на репозиторий.

## Запрос к владельцу

1. Обновить PAT (или создать новый) с областями:
   - `repo` (full control)
   - `admin:org` (для branch protection)
   
2. Либо выполнить шаги 1 и 5 вручную через GitHub UI:
   - Settings → General → Pull requests → "Allow auto-merge"
   - Settings → Branches → Add rule → main → Enable protection

Временное решение: я могу подготовить workflow и CLAUDE.md обновление, но API-операции потребуют обновлённый PAT.
