"""HTML-escaping helper'ы для Telegram-сообщений.

Все user/admin-supplied значения, попадающие в HTML-сообщения, должны
проходить через safe_format — защита от XSS (CWE-79) и DoS от непарных < >.
"""

from __future__ import annotations

import html
from string import Formatter

__all__ = ["safe_format"]


class _SafeFormatter(Formatter):
    """Formatter, который экранирует все значения через html.escape."""

    def format_field(self, value: object, format_spec: str) -> str:
        """Экранирует значение перед применением format_spec."""
        if format_spec:
            # Сначала экранируем, потом применяем спецификацию (например, :s)
            escaped = html.escape(str(value), quote=False)
            return format(escaped, format_spec)
        return html.escape(str(value), quote=False)


_safe_formatter = _SafeFormatter()


def safe_format(template: str, **values: object) -> str:
    """Форматирует шаблон, экранируя все значения через html.escape.

    Args:
        template: Строка-шаблон с placeholder'ами вида {name}
        **values: Значения для подстановки

    Returns:
        Отформатированная строка с экранированными значениями.

    Example:
        >>> safe_format("<b>{title}</b>", title="A<b>X</b>B")
        '<b>A&lt;b&gt;X&lt;/b&gt;B</b>'
        >>> safe_format("Hello, {name}!", name="<script>alert('xss')</script>")
        'Hello, &lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;!'
    """
    return _safe_formatter.format(template, **values)
