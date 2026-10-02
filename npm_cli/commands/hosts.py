"""Proxy hosts, redirection hosts, 404 hosts and streams."""

from __future__ import annotations

from typing import Sequence

from ..client import NpmError
from ..output import Column
from ._common import (Context, add_crud_commands, bool_flag, build_payload, enabled_status,
                      group, leaf, text_or_file)
from .certificates import request_letsencrypt

HOST_EXPAND = ("owner", "certificate", "access_list")

SSL_FIELDS = ("certificate_id", "ssl_forced", "http2_support", "hsts_enabled", "hsts_subdomains")

PROXY_FIELDS = ("domain_names", "forward_scheme", "forward_host", "forward_port", "access_list_id",
                "allow_websocket_upgrade", "block_exploits", "caching_enabled", "advanced_config") + SSL_FIELDS

REDIRECT_FIELDS = ("domain_names", "forward_scheme", "forward_domain_name", "forward_http_code",
                   "preserve_path", "block_exploits", "advanced_config") + SSL_FIELDS

DEAD_FIELDS = ("domain_names", "advanced_config") + SSL_FIELDS

STREAM_FIELDS = ("incoming_port", "forwarding_host", "forwarding_port", "tcp_forwarding", "udp_forwarding")


def _ssl(host: dict) -> str:
    if not host.get("certificate_id"):
        return "no"
    return "forced" if host.get("ssl_forced") else "yes"


PROXY_COLUMNS = [
    ("ID", lambda h: h.get("id")),
    ("Domains", lambda h: h.get("domain_names")),
    ("Forward", lambda h: f"{h.get('forward_scheme')}://{h.get('forward_host')}:{h.get('forward_port')}"),
    ("SSL", _ssl),
    ("Access list", lambda h: h.get("access_list") or None),
    ("Status", enabled_status),
]


def _redirect_target(h: dict) -> str:
    scheme = h.get("forward_scheme")
    prefix = "" if scheme in (None, "auto", "$scheme") else f"{scheme}://"
    return f"{h.get('forward_http_code')} -> {prefix}{h.get('forward_domain_name')}"


REDIRECT_COLUMNS = [
    ("ID", lambda h: h.get("id")),
    ("Domains", lambda h: h.get("domain_names")),
    ("Redirect", _redirect_target),
    ("Preserve path", lambda h: bool(h.get("preserve_path"))),
    ("SSL", _ssl),
    ("Status", enabled_status),
]

DEAD_COLUMNS = [
    ("ID", lambda h: h.get("id")),
    ("Domains", lambda h: h.get("domain_names")),
    ("SSL", _ssl),
    ("Status", enabled_status),
]


def _protocols(s: dict) -> str:
    protocols = [name for name, key in (("tcp", "tcp_forwarding"), ("udp", "udp_forwarding")) if s.get(key)]
    return "/".join(protocols) or "-"


STREAM_COLUMNS = [
    ("ID", lambda s: s.get("id")),
    ("Incoming port", lambda s: s.get("incoming_port")),
    ("Forward", lambda s: f"{s.get('forwarding_host')}:{s.get('forwarding_port')}"),
    ("Protocols", _protocols),
    ("Status", enabled_status),
]


# --- options ----------------------------------------------------------------

def add_domain_option(p, update: bool) -> None:
    help = "domain name (repeatable)" + ("; replaces the current list" if update else "")
    p.add_argument("-d", "--domain", dest="domain_names", action="append", required=not update,
                   metavar="DOMAIN", help=help)


def add_ssl_options(p, update: bool) -> None:
    g = p.add_argument_group("SSL options")
    g.add_argument("--certificate-id", type=int, help="use an existing certificate (0 = no SSL)")
    g.add_argument("--ssl", action="store_true", help="request a new Let's Encrypt certificate for the domains")
    g.add_argument("--email", help="Let's Encrypt account email (with --ssl)")
    bool_flag(g, "--force-ssl", "ssl_forced", False, update, "redirect HTTP to HTTPS")
    bool_flag(g, "--http2", "http2_support", False, update, "enable HTTP/2")
    bool_flag(g, "--hsts", "hsts_enabled", False, update, "enable HSTS")
    bool_flag(g, "--hsts-subdomains", "hsts_subdomains", False, update, "include subdomains in HSTS")


def add_advanced_option(p) -> None:
    p.add_argument("--advanced-config", type=text_or_file,
                   help="custom nginx configuration (use @file to read it from a file)")


def add_proxy_options(p, update: bool) -> None:
    add_domain_option(p, update)
    p.add_argument("--forward-host", required=not update, help="upstream host or IP")
    p.add_argument("--forward-port", type=int, required=not update, help="upstream port")
    p.add_argument("--scheme", "--protocol", dest="forward_scheme", choices=["http", "https"],
                   default=None if update else "http", help="upstream scheme")
    p.add_argument("--access-list-id", type=int, help="protect with an access list (0 = public)")
    bool_flag(p, "--websockets", "allow_websocket_upgrade", True, update, "allow websocket upgrades")
    bool_flag(p, "--block-exploits", "block_exploits", True, update, "block common exploits")
    bool_flag(p, "--caching", "caching_enabled", False, update, "cache static assets")
    add_advanced_option(p)
    add_ssl_options(p, update)


def add_redirect_options(p, update: bool) -> None:
    add_domain_option(p, update)
    p.add_argument("--to", dest="forward_domain_name", required=not update, metavar="DOMAIN",
                   help="destination domain (may include a path)")
    p.add_argument("--scheme", dest="forward_scheme", choices=["auto", "http", "https"],
                   default=None if update else "auto", help="destination scheme")
    p.add_argument("--code", dest="forward_http_code", type=int, choices=range(300, 309), metavar="CODE",
                   default=None if update else 301, help="HTTP status code, 300-308")
    bool_flag(p, "--preserve-path", "preserve_path", True, update, "keep the request path")
    bool_flag(p, "--block-exploits", "block_exploits", True, update, "block common exploits")
    add_advanced_option(p)
    add_ssl_options(p, update)


def add_dead_options(p, update: bool) -> None:
    add_domain_option(p, update)
    add_advanced_option(p)
    add_ssl_options(p, update)


def add_stream_options(p, update: bool) -> None:
    p.add_argument("--incoming-port", type=int, required=not update, help="port NPM listens on")
    p.add_argument("--forward-host", dest="forwarding_host", required=not update, help="upstream host or IP")
    p.add_argument("--forward-port", dest="forwarding_port", type=int, required=not update, help="upstream port")
    bool_flag(p, "--tcp", "tcp_forwarding", True, update, "forward TCP")
    bool_flag(p, "--udp", "udp_forwarding", False, update, "forward UDP")


# --- handlers ---------------------------------------------------------------

def _apply_ssl(ctx: Context, args, payload: dict, domains: Sequence[str]) -> None:
    if not getattr(args, "ssl", False):
        return
    if args.certificate_id is not None:
        raise NpmError("Use either --ssl or --certificate-id, not both.")
    cert = request_letsencrypt(ctx, list(domains), args.email)
    payload["certificate_id"] = cert["id"]


def make_create(attr: str, label: str, fields: Sequence[str], columns: Sequence[Column]):
    def handler(ctx: Context, args) -> None:
        payload = build_payload(args, fields)
        _apply_ssl(ctx, args, payload, payload.get("domain_names", ()))
        payload["meta"] = {}
        obj = getattr(ctx.client, attr).create(payload)
        ctx.out.created(label, obj, columns)
    return handler


def make_update(attr: str, label: str, fields: Sequence[str], columns: Sequence[Column]):
    def handler(ctx: Context, args) -> None:
        resource = getattr(ctx.client, attr)
        payload = build_payload(args, fields)
        if getattr(args, "ssl", False):
            domains = payload.get("domain_names") or resource.get(args.id)["domain_names"]
            _apply_ssl(ctx, args, payload, domains)
        if not payload:
            raise NpmError("Nothing to update: pass at least one option (see --help).")
        obj = resource.update(args.id, payload)
        ctx.out.created(label, obj, columns, verb="Updated")
    return handler


HOST_TYPES = [
    # (command, aliases, client attribute, label, fields, columns, add_options, expand, help)
    ("proxy", ["proxy-host", "proxy-hosts"], "proxy_hosts", "proxy host",
     PROXY_FIELDS, PROXY_COLUMNS, add_proxy_options, HOST_EXPAND, "manage proxy hosts"),
    ("redirect", ["redirection", "redirection-host", "redirection-hosts"], "redirection_hosts", "redirection host",
     REDIRECT_FIELDS, REDIRECT_COLUMNS, add_redirect_options, HOST_EXPAND[:2], "manage redirection hosts"),
    ("dead", ["404", "dead-host", "dead-hosts"], "dead_hosts", "404 host",
     DEAD_FIELDS, DEAD_COLUMNS, add_dead_options, HOST_EXPAND[:2], "manage 404 hosts"),
    ("stream", ["streams"], "streams", "stream",
     STREAM_FIELDS, STREAM_COLUMNS, add_stream_options, ("owner",), "manage TCP/UDP streams"),
]


def register(root) -> None:
    for name, aliases, attr, label, fields, columns, add_options, expand, help in HOST_TYPES:
        sub = group(root, name, help, aliases=aliases)
        add_crud_commands(sub, attr, label, columns, expand=expand)

        p = leaf(sub, "create", make_create(attr, label, fields, columns), f"create a {label}", aliases=["add"])
        add_options(p, update=False)

        p = leaf(sub, "update", make_update(attr, label, fields, columns),
                 f"update a {label} (only the given options change)", aliases=["edit"])
        p.add_argument("id", type=int)
        add_options(p, update=True)
