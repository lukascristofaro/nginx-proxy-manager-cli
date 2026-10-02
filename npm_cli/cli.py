"""Entry point: `npm-cli` / `python -m npm_cli`."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .client import ApiError, NpmError
from .commands import register_all
from .commands._common import COMMON, GLOBAL_DEFAULTS, Context

EPILOG = """examples:
  npm-cli login --url http://192.168.1.10:81
  npm-cli proxy list
  npm-cli proxy create -d app.example.com --forward-host 10.0.0.5 --forward-port 8080 --ssl --force-ssl
  npm-cli proxy update 3 --forward-port 9000
  npm-cli cert list --json
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="npm-cli",
        description="Command line client for Nginx Proxy Manager.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[COMMON],
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    register_all(sub)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    for key, value in GLOBAL_DEFAULTS.items():
        if not hasattr(args, key):
            setattr(args, key, value)

    try:
        args.func(Context(args), args)
    except ApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if exc.status == 401:
            print("Hint: your session may have expired, run `npm-cli login`.", file=sys.stderr)
        return 1
    except NpmError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
