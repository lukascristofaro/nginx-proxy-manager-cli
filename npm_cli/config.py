"""Persistent CLI configuration (server URL and session token)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def config_dir() -> Path:
    override = os.environ.get("NPM_CLI_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "npm-cli"


def config_file() -> Path:
    return config_dir() / "config.json"


def load() -> dict:
    path = config_file()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)  # the file contains a bearer token
    except OSError:
        pass


def delete() -> bool:
    try:
        config_file().unlink()
        return True
    except FileNotFoundError:
        return False
