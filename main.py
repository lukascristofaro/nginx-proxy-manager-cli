"""Run the CLI without installing it: `python main.py proxy list`."""

import sys

from npm_cli.cli import main

if __name__ == "__main__":
    sys.exit(main())
