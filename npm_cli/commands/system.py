"""Reports, audit log and settings."""

from __future__ import annotations

from ._common import Context, leaf

AUDIT_COLUMNS = [
    ("ID", lambda e: e.get("id")),
    ("Date", lambda e: (e.get("created_on") or "").replace("T", " ")[:19]),
    ("User", lambda e: (e.get("user") or {}).get("name")),
    ("Action", lambda e: e.get("action")),
    ("Object", lambda e: f"{e.get('object_type')} #{e.get('object_id')}"),
]

SETTING_COLUMNS = [
    ("ID", lambda s: s.get("id")),
    ("Name", lambda s: s.get("name")),
    ("Value", lambda s: s.get("value")),
]

REPORT_COLUMNS = [("Type", lambda r: r["type"]), ("Count", lambda r: r["count"])]


def report(ctx: Context, args) -> None:
    data = ctx.client.host_report()
    if ctx.out.as_json:
        ctx.out.detail(data)
    else:
        ctx.out.table([{"type": k, "count": v} for k, v in data.items()], REPORT_COLUMNS)


def audit(ctx: Context, args) -> None:
    entries = ctx.client.audit_log()
    ctx.out.table(entries[: args.limit], AUDIT_COLUMNS, empty="Audit log is empty.")


def settings(ctx: Context, args) -> None:
    ctx.out.table(ctx.client.settings(), SETTING_COLUMNS)


def register(root) -> None:
    leaf(root, "report", report, "count hosts by type")
    p = leaf(root, "audit", audit, "show the audit log", aliases=["audit-log"])
    p.add_argument("-n", "--limit", type=int, default=20, help="number of entries (default: 20)")
    leaf(root, "settings", settings, "show server settings")
