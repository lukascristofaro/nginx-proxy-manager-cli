"""Access lists (basic auth users and IP rules)."""

from __future__ import annotations

import argparse

from ._common import Context, add_crud_commands, group, leaf

ACCESS_LIST_COLUMNS = [
    ("ID", lambda a: a.get("id")),
    ("Name", lambda a: a.get("name")),
    ("Users", lambda a: len(a.get("items") or [])),
    ("Rules", lambda a: len(a.get("clients") or [])),
    ("Satisfy", lambda a: "any" if a.get("satisfy_any") else "all"),
    ("Pass auth", lambda a: bool(a.get("pass_auth"))),
]


def user_pass(value: str) -> dict:
    username, sep, password = value.partition(":")
    if not sep or not username:
        raise argparse.ArgumentTypeError("expected USER:PASSWORD")
    return {"username": username, "password": password}


def access_list_create(ctx: Context, args) -> None:
    clients = [{"address": a, "directive": "allow"} for a in args.allow]
    clients += [{"address": a, "directive": "deny"} for a in args.deny]
    payload = {
        "name": args.name,
        "satisfy_any": args.satisfy_any,
        "pass_auth": args.pass_auth,
        "items": args.users,
        "clients": clients,
    }
    obj = ctx.client.access_lists.create(payload)
    ctx.out.created("access list", obj, ACCESS_LIST_COLUMNS)


def register(root) -> None:
    sub = group(root, "access-list", "manage access lists", aliases=["access-lists", "acl"])
    add_crud_commands(sub, "access_lists", "access list", ACCESS_LIST_COLUMNS,
                      expand=("owner", "items", "clients"), toggle=False)

    p = leaf(sub, "create", access_list_create, "create an access list", aliases=["add"])
    p.add_argument("--name", required=True)
    p.add_argument("--user", dest="users", type=user_pass, action="append", default=[],
                   metavar="USER:PASSWORD", help="basic auth user (repeatable)")
    p.add_argument("--allow", action="append", default=[], metavar="ADDRESS",
                   help="allowed IP or CIDR (repeatable)")
    p.add_argument("--deny", action="append", default=[], metavar="ADDRESS",
                   help="denied IP or CIDR (repeatable), e.g. --deny all")
    p.add_argument("--satisfy-any", action="store_true",
                   help="grant access if either auth or IP rule matches (default: both)")
    p.add_argument("--pass-auth", action="store_true", help="forward the Authorization header upstream")
