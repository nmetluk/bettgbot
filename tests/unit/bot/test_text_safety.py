"""Тесты HTML-escaping helper'ов из `src.bot._text_safety`."""

from src.bot._text_safety import safe_format


class TestSafeFormat:
    """`safe_format` экранирует все значения через html.escape."""

    def test_escapes_html_entities(self) -> None:
        """Теги <b></b> в значении должны быть экранированы."""
        template = "<b>{title}</b>"
        result = safe_format(template, title="A<b>X</b>B")
        assert result == "<b>A&lt;b&gt;X&lt;/b&gt;B</b>"

    def test_escapes_script_tag(self) -> None:
        """JavaScript должен быть экранирован."""
        template = "Hello, {name}!"
        result = safe_format(template, name="<script>alert('xss')</script>")
        # quote=False — кавычки не экранируются (для атрибутов используем другие средства)
        assert result == "Hello, &lt;script&gt;alert('xss')&lt;/script&gt;!"

    def test_escapes_unmatched_lt_gt(self) -> None:
        """Непарные < и > должны быть экранированы (защита от DoS)."""
        template = "Event: {title}"
        result = safe_format(template, title="Match <script>")
        assert result == "Event: Match &lt;script&gt;"
        result = safe_format(template, title="Match >")
        assert result == "Event: Match &gt;"

    def test_preserves_template_html(self) -> None:
        """HTML в шаблоне не должен экранироваться."""
        template = "<b>{title}</b>\n<a href='/events'>Events</a>"
        result = safe_format(template, title="Test")
        assert result == "<b>Test</b>\n<a href='/events'>Events</a>"

    def test_multiple_placeholders(self) -> None:
        """Множественные placeholder'ы должны обрабатываться корректно."""
        template = "{a} and {b}"
        result = safe_format(template, a="<x>", b="<y>")
        assert result == "&lt;x&gt; and &lt;y&gt;"

    def test_empty_value(self) -> None:
        """Пустые строки не должны ломаться."""
        result = safe_format("Value: {v}", v="")
        assert result == "Value: "

    def test_non_string_values_converted(self) -> None:
        """Числа и прочее должны преобразовываться в строку."""
        result = safe_format("Count: {n}", n=42)
        assert result == "Count: 42"
        result = safe_format("Flag: {f}", f=True)
        assert result == "Flag: True"

    def test_no_placeholder(self) -> None:
        """Шаблон без placeholder'ов не должен меняться."""
        template = "<b>Hello</b>"
        result = safe_format(template)
        assert result == template
