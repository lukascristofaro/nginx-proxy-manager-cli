"""NPM users."""

from __future__ import annotations

import getpass

from ..client import NpmError
from ._common import Context, add_crud_commands, group, leaf

USER_COLUMNS = [
    ("ID", lambda u: u.get("id")),
    ("Name", lambda u: u.get("name")),
    ("Email", lambda u: u.get("email")),
    ("Roles", lambda u: u.get("roles")),
    ("Disabled", lambda u: bool(u.get("is_disabled"))),
]


def ask_new_password() -> str:
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat password: "):
        raise NpmError("Passwords do not match.")
    if not password:
        raise NpmError("Password cannot be empty.")
    return password


def user_create(ctx: Context, args) -> None:
    password = args.password or ask_new_password()
    payload = {
        "name": args.name,
        "nickname": args.nickname or args.name.split()[0],
        "email": args.email,
        "roles": ["admin"] if args.admin else [],
        "is_disabled": args.disabled,
    }
    user = ctx.client.users.create(payload)
    ctx.client.set_user_password(user["id"], password)
    ctx.out.created("user", user, USER_COLUMNS)


def user_password(ctx: Context, args) -> None:
    password = args.password or ask_new_password()
    ctx.client.set_user_password(args.id, password, current=args.current)
    ctx.out.success(f"Password changed for user #{args.id}.")


def register(root) -> None:
    sub = group(root, "user", "manage users", aliases=["users"])
    add_crud_commands(sub, "users", "user", USER_COLUMNS, toggle=False)

    p = leaf(sub, "create", user_create, "create a user", aliases=["add"])
    p.add_argument("--name", required=True, help="full name")
    p.add_argument("--nickname", help="nickname (default: first name)")
    p.add_argument("--email", required=True)
    p.add_argument("--password", help="password (prompted if omitted)")
    p.add_argument("--admin", action="store_true", help="give the administrator role")
    p.add_argument("--disabled", action="store_true", help="create the account disabled")

    p = leaf(sub, "password", user_password, "change a user's password", aliases=["passwd"])
    p.add_argument("id", type=int)
    p.add_argument("--password", help="new password (prompted if omitted)")
    p.add_argument("--current", help="current password (required when changing your own)")
