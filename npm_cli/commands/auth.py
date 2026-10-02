"""login / logout / whoami / status."""

from __future__ import annotations

import getpass
import os

from .. import config, session
from ..client import ApiError, NpmClient, NpmError
from ._common import Context, leaf


def login(ctx: Context, args) -> None:
    cfg = config.load()
    url = session.resolve_url(args, cfg) or input("NPM URL (e.g. http://192.168.1.10:81): ").strip()
    email = args.email or os.environ.get("NPM_EMAIL") or input("Email: ").strip()
    password = args.password or os.environ.get("NPM_PASSWORD") or getpass.getpass("Password: ")
    if not (url and email and password):
        raise NpmError("URL, email and password are required.")

    client = NpmClient(url, timeout=args.timeout, verify=not args.insecure)
    data = client.login(email, password)
    me = client.me()
    session.save_session({}, client, data, email=email, insecure=args.insecure)
    ctx.out.success(f"Logged in to {client.base_url} as {me.get('name')} <{me.get('email')}>.")


def logout(ctx: Context, args) -> None:
    if config.delete():
        ctx.out.success("Logged out, local session removed.")
    else:
        ctx.out.success("No local session.")


def whoami(ctx: Context, args) -> None:
    ctx.out.detail(ctx.client.me())


def status(ctx: Context, args) -> None:
    cfg = config.load()
    client = session.open_client(args, authenticate=False)
    try:
        health = client.health()
    except ApiError as exc:
        health = {"status": f"unreachable ({exc})"}
    version = health.get("version") or {}
    info = {
        "url": client.base_url,
        "server": health.get("status"),
        "version": ".".join(str(version[k]) for k in ("major", "minor", "revision") if k in version) or None,
        "logged_in_as": cfg.get("email") if cfg.get("url") == client.base_url else None,
        "token_expires": cfg.get("expires") if cfg.get("url") == client.base_url else None,
        "config_file": str(config.config_file()),
    }
    ctx.out.detail(info)


def register(root) -> None:
    p = leaf(root, "login", login, "log in and store a session token")
    p.add_argument("-e", "--email", help="account email (env: NPM_EMAIL)")
    p.add_argument("-p", "--password", help="password (env: NPM_PASSWORD; prompted if omitted)")

    leaf(root, "logout", logout, "remove the stored session")
    leaf(root, "whoami", whoami, "show the logged in user")
    leaf(root, "status", status, "show server health and session info")
