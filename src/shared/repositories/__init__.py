"""Тонкий query-слой над агрегатами. Сервисы (TASK-008+) используют эти классы.

Принципы:
- Один репозиторий — один агрегат.
- `AsyncSession` в конструкторе, метод не принимает её повторно.
- Транзакциями владеет сервис: репозиторий делает `add`, `flush`, `execute`, но
  не вызывает `commit`/`rollback`.
- Возвращаем ORM-инстансы; конвертация в DTO — на стороне сервиса/слоя ответа.
- Eager-loading — явно через `selectinload`/`joinedload` в методах, которые
  обещают вернуть связанные объекты.
"""

from .admin_user import AdminUserRepository
from .audit_log import AuditLogRepository
from .category import CategoryRepository
from .event import EventRepository
from .outcome import OutcomeRepository
from .prediction import PredictionRepository
from .reminder_dispatch_log import ReminderDispatchLogRepository
from .reminder_setting import ReminderSettingRepository
from .user import UserRepository

__all__ = [
    "AdminUserRepository",
    "AuditLogRepository",
    "CategoryRepository",
    "EventRepository",
    "OutcomeRepository",
    "PredictionRepository",
    "ReminderDispatchLogRepository",
    "ReminderSettingRepository",
    "UserRepository",
]
