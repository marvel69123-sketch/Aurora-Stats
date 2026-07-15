"""
Temporary deploy identity for production audits.

Exposes backend_commit / frontend_commit only — does NOT change
fixture integrity, markets, or MatchHeader logic.

Remove after the version audit is complete.
"""

from __future__ import annotations

import logging
import os
import subprocess
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


def _short_sha(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    # Allow full SHA or already-short; keep first 7 for readability
    if all(c in "0123456789abcdefABCDEF" for c in text) and len(text) >= 7:
        return text[:7].lower()
    return text[:64]


def _git_rev_parse() -> str | None:
    try:
        # Prefer repo root: artifacts/aurora/src/core → parents[4] = workspace
        here = Path(__file__).resolve()
        candidates = [
            here.parents[4] if len(here.parents) > 4 else None,  # workspace
            here.parents[3] if len(here.parents) > 3 else None,  # artifacts
            Path.cwd(),
        ]
        for root in candidates:
            if root is None or not (root / ".git").exists():
                continue
            out = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(root),
                stderr=subprocess.DEVNULL,
                timeout=2,
                text=True,
            )
            return _short_sha(out)
    except Exception as exc:
        logger.debug("deploy_identity: git rev-parse skipped (%s)", exc)
    return None


def _read_ui_build_file() -> str | None:
    """Best-effort read of aurora-ui-build.txt when co-located on disk."""
    here = Path(__file__).resolve()
    roots: list[Path] = []
    try:
        roots.append(here.parents[4])  # workspace
    except IndexError:
        pass
    roots.append(Path.cwd())
    env_root = os.environ.get("AURORA_WORKSPACE") or os.environ.get("REPL_HOME")
    if env_root:
        roots.insert(0, Path(env_root))

    rels = (
        "artifacts/web/dist/public/aurora-ui-build.txt",
        "artifacts/web/public/aurora-ui-build.txt",
        "aurora-ui-build.txt",
    )
    for root in roots:
        for rel in rels:
            path = root / rel
            try:
                if path.is_file():
                    return path.read_text(encoding="utf-8").strip() or None
            except OSError:
                continue
    return None


@lru_cache(maxsize=1)
def get_backend_commit() -> str:
    for key in (
        "AURORA_BACKEND_COMMIT",
        "BACKEND_COMMIT",
        "GIT_COMMIT",
        "REPLIT_GIT_SHA",
        "GITHUB_SHA",
    ):
        short = _short_sha(os.environ.get(key))
        if short:
            return short
    short = _git_rev_parse()
    return short or "unknown"


@lru_cache(maxsize=1)
def get_frontend_commit() -> str:
    for key in ("AURORA_UI_BUILD", "FRONTEND_COMMIT", "AURORA_FRONTEND_COMMIT"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val[:128]
    file_val = _read_ui_build_file()
    if file_val:
        return file_val[:128]
    return "unknown"


def deploy_identity_dict() -> dict[str, str]:
    return {
        "backend_commit": get_backend_commit(),
        "frontend_commit": get_frontend_commit(),
    }
