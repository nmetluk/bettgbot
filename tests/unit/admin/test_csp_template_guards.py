"""CSP compatibility guards for admin templates (TASK-093).

Prevents re-introduction of Alpine CSP-incompatible syntax:
- @click="foo(...)" with parentheses or arguments (CSP build cannot interpret call expressions).
- Use @click="foo" (no-arg) or data-* + this.$el.dataset in the handler (see ui.js + _layout_shell.html).

This is a runtime-Alpine concern; unit tests on Python side cannot simulate the binding,
so a static grep guard + manual browser verification (DoD) are required.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "src" / "admin" / "templates"


def test_no_csp_incompatible_alpine_click_handlers_in_templates() -> None:
    """Fail if any template contains @click="..." with ( or arguments.

    This would break under alpine-csp build (adopted in TASK-057/090).
    Allowed: @click="toggleDark" or @click="setDensity" (the handler then reads dataset).
    """
    if not TEMPLATES_DIR.exists():
        pytest.skip("templates dir not found")

    bad_pattern = re.compile(r'@click\s*=\s*"[^"]*\(')  # catches foo( or foo(bar)

    offenders: list[tuple[Path, str]] = []

    for tmpl in TEMPLATES_DIR.rglob("*.html"):
        text = tmpl.read_text(encoding="utf-8")
        if bad_pattern.search(text):
            # Record the offending line(s) for helpful failure message
            for i, line in enumerate(text.splitlines(), 1):
                if bad_pattern.search(line):
                    offenders.append((tmpl, f"L{i}: {line.strip()[:120]}"))

    if offenders:
        msg = "CSP-incompatible @click handlers found (remove () and args; use data-* + handler):\n"
        for path, snippet in offenders:
            msg += f"  {path.relative_to(TEMPLATES_DIR.parent)}: {snippet}\n"
        pytest.fail(msg)

    # Also a positive sanity: at least the known controls exist in the layout
    layout = TEMPLATES_DIR / "_layout_shell.html"
    if layout.exists():
        content = layout.read_text(encoding="utf-8")
        assert '@click="toggleDark"' in content or "@click='toggleDark'" in content
        assert "data-density=" in content
        assert "data-accent=" in content or ":data-accent=" in content
