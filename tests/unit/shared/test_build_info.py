"""Unit tests for build_info fallback logic (TASK-081).

These tests verify the priority:
1. Local generated module (src.shared._build_info) wins if present.
2. BUILD_* environment variables (injected in GHCR images) are used as fallback.
3. Safe placeholder when nothing is available.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest
from src.shared.build_info import BuildInfo, _placeholder, get_build_info


def test_get_build_info_no_module_no_env_returns_placeholder(monkeypatch):
    """Neither generated module nor BUILD_* env → placeholder."""
    monkeypatch.setitem(sys.modules, "src.shared._build_info", None)

    # Remove any BUILD_* that might exist in the test runner env
    for key in list(os.environ.keys()):
        if key.startswith("BUILD_"):
            monkeypatch.delenv(key, raising=False)

    import src.shared.build_info as bi_module

    importlib.reload(bi_module)

    info = bi_module.get_build_info()

    assert info == _placeholder()
    assert info.app_version == "unknown"
    assert info.git_commit_short == "dev"


def test_get_build_info_env_fallback_works(monkeypatch):
    """BUILD_* env vars are used when no generated module is present (CI/GHCR path)."""
    monkeypatch.setitem(sys.modules, "src.shared._build_info", None)

    monkeypatch.setenv("BUILD_APP_VERSION", "1.2.3")
    monkeypatch.setenv("BUILD_GIT_COMMIT", "1234567890abcdef1234567890abcdef12345678")
    monkeypatch.setenv("BUILD_GIT_BRANCH", "main")
    monkeypatch.setenv("BUILD_GIT_TAG", "v1.2.3")
    monkeypatch.setenv("BUILD_TIME", "2026-05-31T12:00:00Z")

    import src.shared.build_info as bi_module

    importlib.reload(bi_module)

    info = bi_module.get_build_info()

    # Compare by attributes (isinstance can be tricky across reloads)
    assert info.app_version == "1.2.3"
    assert info.git_commit == "1234567890abcdef1234567890abcdef12345678"
    assert info.git_commit_short == "1234567890ab"  # first 12 chars, as required
    assert info.git_branch == "main"
    assert info.git_tag == "v1.2.3"
    assert info.build_time == "2026-05-31T12:00:00Z"


def test_get_build_info_module_takes_precedence_over_env(monkeypatch):
    """Generated module always wins over BUILD_* env (preserves local make prod.build behavior)."""
    # Fake module (simulates what generate_build_info.sh produces)
    fake_module = type(sys)("src.shared._build_info")
    fake_module.APP_VERSION = "9.9.9"
    fake_module.GIT_COMMIT = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    fake_module.GIT_COMMIT_SHORT = "deadbeef"
    fake_module.GIT_BRANCH = "feature/test"
    fake_module.GIT_TAG = ""
    fake_module.BUILD_TIME = "2026-05-31T10:00:00Z"

    monkeypatch.setitem(sys.modules, "src.shared._build_info", fake_module)

    # Conflicting env (should be ignored)
    monkeypatch.setenv("BUILD_APP_VERSION", "env-version")
    monkeypatch.setenv("BUILD_GIT_COMMIT", "env-commit-123456789012")

    import src.shared.build_info as bi_module

    importlib.reload(bi_module)

    info = bi_module.get_build_info()

    assert info.app_version == "9.9.9"
    assert info.git_commit == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    assert info.git_commit_short == "deadbeef"
    assert info.git_branch == "feature/test"
    # Env must be ignored
    assert info.git_commit != "env-commit-123456789012"
