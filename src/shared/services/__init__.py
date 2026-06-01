"""Доменные сервисы Betting Bot.

Сервисы компонуют репозитории, владеют транзакциями и поднимают доменные
исключения из `src.shared.exceptions`. Handler-слой (aiogram/FastAPI) зовёт
сервис и ловит `DomainError`-подклассы для форматирования ответа.
"""

from .admin_auth import AdminAuthService
from .audit import AuditService
from .broadcast import BroadcastSegment, BroadcastService, CreateBroadcastDraft
from .category import CategoryService
from .dashboard import DashboardService
from .event import EventService
from .prediction import PredictionService
from .reminder import ReminderCandidate, ReminderService
from .stats import (
    AnalyticsDayRow,
    AnalyticsFunnelMetrics,
    AnalyticsTopEventRow,
    CategoryAccuracyRow,
    CorrectUserRow,
    DailyAdminDigest,
    EventResultSummary,
    LeaderboardRow,
    StatsService,
)
from .user import UserService

__all__ = [
    "AdminAuthService",
    "AnalyticsDayRow",
    "AnalyticsFunnelMetrics",
    "AnalyticsTopEventRow",
    "AuditService",
    "BroadcastSegment",
    "BroadcastService",
    "CategoryAccuracyRow",
    "CategoryService",
    "CorrectUserRow",
    "CreateBroadcastDraft",
    "DailyAdminDigest",
    "DashboardService",
    "EventResultSummary",
    "EventService",
    "LeaderboardRow",
    "PredictionService",
    "ReminderCandidate",
    "ReminderService",
    "StatsService",
    "UserService",
]
