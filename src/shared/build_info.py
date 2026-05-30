"""
Build information access with safe fallbacks.

This module provides runtime access to build metadata that was baked
into the Docker image by scripts/generate_build_info.sh before build.

Goals:
- Never break the application if the metadata file is missing (dev, tests, old images).
- Graceful degradation with clear "unknown" values.
- Support for schema evolution (new fields added over time).
- Lazy import so the module can be imported even when _build_info.py does not exist.

Usage:
    from src.shared.build_info import get_build_info, BuildInfo

    info = get_build_info()
    print(info.git_commit_short)
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BuildInfo:
    """Snapshot of build metadata captured at image creation time."""

    app_version: str
    git_commit: str
    git_commit_short: str
    git_branch: str
    git_tag: str          # empty string if HEAD was not exactly on a tag
    build_time: str       # ISO-8601 UTC or "unknown"


def get_build_info() -> BuildInfo:
    """
    Return build metadata or a safe placeholder.

    Priority (highest first):
    1. Local generated module src.shared._build_info (from generate_build_info.sh during local/CI build)
    2. BUILD_* environment variables (injected via Docker build-args in GHCR/CI images)
    3. Safe placeholder

    This ensures:
    - Local `make prod.build` path continues to work (module takes precedence).
    - Real production images from GHCR (built in build-images.yml) also get real metadata via env.
    """
    # 1. Try the generated module first (local / make prod.build path)
    try:
        module: Any = importlib.import_module("src.shared._build_info")
        return BuildInfo(
            app_version=str(getattr(module, "APP_VERSION", "") or "unknown"),
            git_commit=str(getattr(module, "GIT_COMMIT", "") or "unknown"),
            git_commit_short=str(getattr(module, "GIT_COMMIT_SHORT", "") or "dev"),
            git_branch=str(getattr(module, "GIT_BRANCH", "") or "unknown"),
            git_tag=str(getattr(module, "GIT_TAG", "") or ""),
            build_time=str(getattr(module, "BUILD_TIME", "") or "unknown"),
        )
    except ImportError:
        pass
    except Exception:
        return _placeholder()

    # 2. Fallback to environment variables (set in GHCR images via build-args)
    git_commit = os.environ.get("BUILD_GIT_COMMIT", "")
    if git_commit:
        try:
            return BuildInfo(
                app_version=os.environ.get("BUILD_APP_VERSION", "unknown"),
                git_commit=git_commit,
                git_commit_short=git_commit[:12] if len(git_commit) > 12 else git_commit,
                git_branch=os.environ.get("BUILD_GIT_BRANCH", "unknown"),
                git_tag=os.environ.get("BUILD_GIT_TAG", ""),
                build_time=os.environ.get("BUILD_TIME", "unknown"),
            )
        except Exception:
            return _placeholder()

    # 3. Nothing available
    return _placeholder()


def _placeholder() -> BuildInfo:
    return BuildInfo(
        app_version="unknown",
        git_commit="unknown",
        git_commit_short="dev",
        git_branch="unknown",
        git_tag="",
        build_time="unknown",
    )


__all__ = ["BuildInfo", "get_build_info"]
