"""Shared OS-standard log directory location.

Computing a log directory from `Path(__file__)` breaks under `uv`/`uvx`
distribution: the installed package can resolve inside a content-
addressed cache, so every re-resolve (version bump, cache eviction)
starts a fresh, disconnected log at a new throwaway path. One fixed,
OS-standard directory avoids that regardless of how the package was
installed or where it happens to live on disk.
"""

from pathlib import Path

from platformdirs import user_log_dir


def base_log_dir() -> Path:
    """Fixed OS-standard base directory for all server-written logs."""
    return Path(user_log_dir("legifrance-mcp"))
