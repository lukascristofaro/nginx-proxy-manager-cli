"""Human-readable tables and JSON output."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, List, Sequence, Tuple

Column = Tuple[str, Callable[[dict], Any]]


def fmt(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return ", ".join(fmt(v) for v in value) or "-"
    if isinstance(value, dict):
        if "id" in value and ("nice_name" in value or "name" in value):
            return f"#{value['id']} {value.get('nice_name') or value.get('name')}"
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def render_table(rows: Sequence[dict], columns: Sequence[Column]) -> str:
    headers = [header for header, _ in columns]
    cells = [[fmt(getter(row)) for _, getter in columns] for row in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headers)]

    def line(values: List[str]) -> str:
        return "  ".join(v.ljust(w) for v, w in zip(values, widths)).rstrip()

    lines = [line(headers), line(["-" * w for w in widths])]
    lines.extend(line(r) for r in cells)
    return "\n".join(lines)


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def info(message: str) -> None:
    """Progress/status message; goes to stderr so stdout stays parseable."""
    print(message, file=sys.stderr)


class Output:
    def __init__(self, as_json: bool = False):
        self.as_json = as_json

    def table(self, rows: Sequence[dict], columns: Sequence[Column], empty: str = "No results.") -> None:
        if self.as_json:
            print_json(rows)
        elif not rows:
            info(empty)
        else:
            print(render_table(rows, columns))

    def detail(self, obj: dict) -> None:
        if self.as_json:
            print_json(obj)
            return
        width = max((len(k) for k in obj), default=0)
        for key, value in obj.items():
            print(f"{key.ljust(width)}  {fmt(value)}")

    def created(self, label: str, obj: dict, columns: Sequence[Column], verb: str = "Created") -> None:
        if self.as_json:
            print_json(obj)
        else:
            print(f"{verb} {label} #{obj.get('id')}.")
            print(render_table([obj], columns))

    def success(self, message: str) -> None:
        if self.as_json:
            info(message)
        else:
            print(message)
