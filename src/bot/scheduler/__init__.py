"""APScheduler bootstrap — фоновые задачи бота (TASK-017+)."""

from .builder import build_scheduler
from .jobs import archive_stale_events, dispatch_reminders

__all__ = ["archive_stale_events", "build_scheduler", "dispatch_reminders"]
