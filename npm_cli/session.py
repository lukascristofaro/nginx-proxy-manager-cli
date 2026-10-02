"""Resolve the server URL and credentials, and keep the cached token fresh."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import config
from .client import ApiError, NpmClient, NpmError, normalize_url

# Refresh the cached token when it has less than this left
REFRESH_WINDOW = timedelta(hours=12)


def parse_expiry(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def resolve_url(args, cfg: dict) -> Optional[str]:
    return args.url or os.environ.get("NPM_URL") or cfg.get("url")


def save_session(cfg: dict, client: NpmClient, token_data: dict, **extra) -> None:
    cfg.update(extra)
    cfg["url"] = client.base_url
    cfg["token"] = token_data["token"]
    cfg["expires"] = token_data.get("expires")
    config.save(cfg)


def open_client(args, authenticate: bool = True) -> NpmClient:
    cfg = config.load()
    url = resolve_url(args, cfg)
    if not url:
        raise NpmError("No server configured. Run `npm-cli login` or set NPM_URL.")

    client = NpmClient(url, timeout=args.timeout, verify=not (args.insecure or cfg.get("insecure")))
    if not authenticate:
        return client

    env_token = os.environ.get("NPM_TOKEN")
    if env_token:
        client.token = env_token
        return client

    # Only reuse the cached token if it belongs to the requested server
    same_server = cfg.get("url") == client.base_url
    token = cfg.get("token") if same_server else None
    expires = parse_expiry(cfg.get("expires"))
    now = datetime.now(timezone.utc)

    if token and (expires is None or expires > now + timedelta(minutes=1)):
        client.token = token
        if expires and expires - now < REFRESH_WINDOW:
            try:
                save_session(cfg, client, client.refresh_token())
            except ApiError:
                pass  # the current token is still valid, try again next time
        return client

    email = os.environ.get("NPM_EMAIL")
    password = os.environ.get("NPM_PASSWORD")
    if email and password:
        data = client.login(email, password)
        if same_server or not cfg.get("url"):
            save_session(cfg, client, data, email=email)
        return client

    if token:
        raise NpmError("Session expired. Run `npm-cli login` again.")
    raise NpmError(f"Not logged in to {client.base_url}. Run `npm-cli login` "
                   "or set NPM_EMAIL/NPM_PASSWORD (or NPM_TOKEN).")
