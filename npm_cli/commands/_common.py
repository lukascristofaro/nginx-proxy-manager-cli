"""Shared argparse helpers and generic resource commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

from .. import session
from ..client import NpmClient, NpmError
from ..output import Column, Output

# Global options are accepted both before and after the sub-command
# (`npm-cli --json proxy list` and `npm-cli proxy list --json`).
# SUPPRESS keeps a value given at the top level from being overwritten.
COMMON = argparse.ArgumentParser(add_help=False)
_globals = COMMON.add_argument_group("global options")
_globals.add_argument("--url", default=argparse.SUPPRESS,
                      help="NPM admin URL, e.g. http://192.168.1.10:81 (env: NPM_URL)")
_globals.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                      help="print raw JSON instead of tables")
_globals.add_argument("--timeout", type=float, default=argparse.SUPPRESS,
                      help="HTTP timeout in seconds (default: 30)")
_globals.add_argument("-k", "--insecure", action="store_true", default=argparse.SUPPRESS,
                      help="do not verify TLS certificates")

GLOBAL_DEFAULTS = {"url": None, "json": False, "timeout": 30.0, "insecure": False}


class Context:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.out = Output(args.json)
        self._client: Optional[NpmClient] = None

    @property
    def client(self) -> NpmClient:
        if self._client is None:
            self._client = session.open_client(self.args)
        return self._client


Handler = Callable[[Context, argparse.Namespace], None]


def group(sub, name: str, help: str, aliases: Sequence[str] = ()):
    parser = sub.add_parser(name, help=help, description=help, aliases=list(aliases))
    return parser.add_subparsers(dest="action", metavar="ACTION", required=True)


def leaf(sub, name: str, handler: Handler, help: str, aliases: Sequence[str] = ()) -> argparse.ArgumentParser:
    parser = sub.add_parser(name, help=help, description=help, aliases=list(aliases), parents=[COMMON])
    parser.set_defaults(func=handler)
    return parser


def bool_flag(parser, flag: str, dest: str, default: bool, update: bool, help: str) -> None:
    """--flag / --no-flag. On update commands the default is None (= leave unchanged)."""
    parser.add_argument(flag, dest=dest, action=argparse.BooleanOptionalAction,
                        default=None if update else default, help=help)


def text_or_file(value: str) -> str:
    """Argument type: literal text, or `@path` to read the text from a file."""
    if not value.startswith("@"):
        return value
    try:
        return Path(value[1:]).read_text(encoding="utf-8")
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"cannot read {value[1:]}: {exc.strerror}")


def build_payload(args: argparse.Namespace, fields: Iterable[str]) -> dict:
    """Arguments use the API field names as dest; keep only those that were set."""
    return {f: getattr(args, f) for f in fields if getattr(args, f, None) is not None}


def confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        raise NpmError("Confirmation required; pass --yes to run non-interactively.")
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def enabled_status(obj: dict) -> str:
    if not obj.get("enabled"):
        return "disabled"
    if (obj.get("meta") or {}).get("nginx_online") is False:
        return "error"
    return "online"


def add_crud_commands(sub, attr: str, label: str, columns: Sequence[Column],
                      expand: Sequence[str] = (), toggle: bool = True) -> None:
    """Register list/show/delete (and enable/disable) for a resource."""

    def resource(ctx: Context):
        return getattr(ctx.client, attr)

    def do_list(ctx: Context, args) -> None:
        rows = resource(ctx).list(expand=expand, query=args.search)
        ctx.out.table(rows, columns, empty=f"No {label}s found.")

    p = leaf(sub, "list", do_list, f"list {label}s", aliases=["ls"])
    p.add_argument("-s", "--search", help="only show entries matching this text")

    def do_show(ctx: Context, args) -> None:
        ctx.out.detail(resource(ctx).get(args.id, expand=expand))

    p = leaf(sub, "show", do_show, f"show a {label}", aliases=["get"])
    p.add_argument("id", type=int)

    def do_delete(ctx: Context, args) -> None:
        ids = ", ".join(f"#{i}" for i in args.ids)
        if not args.yes and not confirm(f"Delete {label} {ids}?"):
            raise NpmError("Aborted.")
        for obj_id in args.ids:
            resource(ctx).delete(obj_id)
            ctx.out.success(f"Deleted {label} #{obj_id}.")

    p = leaf(sub, "delete", do_delete, f"delete {label}s", aliases=["rm"])
    p.add_argument("ids", type=int, nargs="+", metavar="id")
    p.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")

    if not toggle:
        return

    for action in ("enable", "disable"):
        def do_toggle(ctx: Context, args, action=action) -> None:
            for obj_id in args.ids:
                getattr(resource(ctx), action)(obj_id)
                ctx.out.success(f"{action.capitalize()}d {label} #{obj_id}.")

        p = leaf(sub, action, do_toggle, f"{action} {label}s")
        p.add_argument("ids", type=int, nargs="+", metavar="id")
