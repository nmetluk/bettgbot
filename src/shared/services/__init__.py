"""Доменные сервисы Betting Bot.

Сервисы компонуют репозитории, владеют транзакциями и поднимают доменные
исключения из `src.shared.exceptions`. Handler-слой (aiogram/FastAPI) зовёт
сервис и ловит `DomainError`-подклассы для форматирования ответа.
"""

from .audit import AuditService
from .category import CategoryService
from .event import EventService
from .prediction import PredictionService
from .reminder import ReminderService
from .stats import StatsService
from .user import UserService

__all__ = [
    "AuditService",
    "CategoryService",
    "EventService",
    "PredictionService",
    "ReminderService",
    "StatsService",
    "UserService",
]
