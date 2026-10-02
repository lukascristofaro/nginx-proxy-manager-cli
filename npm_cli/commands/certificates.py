"""SSL certificates (Let's Encrypt and custom)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..client import ApiError, NpmError
from ..output import info
from ._common import Context, add_crud_commands, group, leaf, text_or_file

CERT_COLUMNS = [
    ("ID", lambda c: c.get("id")),
    ("Name", lambda c: c.get("nice_name")),
    ("Provider", lambda c: c.get("provider")),
    ("Domains", lambda c: c.get("domain_names")),
    ("Expires", lambda c: (c.get("expires_on") or "")[:10]),
]


def request_letsencrypt(ctx: Context, domains: List[str], email: Optional[str] = None,
                        dns_provider: Optional[str] = None, dns_credentials: Optional[str] = None,
                        propagation_seconds: Optional[int] = None) -> dict:
    meta = {"letsencrypt_agree": True, "dns_challenge": bool(dns_provider)}
    if email:
        meta["letsencrypt_email"] = email
    if dns_provider:
        meta["dns_provider"] = dns_provider
        meta["dns_provider_credentials"] = dns_credentials or ""
        if propagation_seconds is not None:
            meta["propagation_seconds"] = propagation_seconds

    info(f"Requesting a Let's Encrypt certificate for {', '.join(domains)} (this can take a minute)...")
    payload = {"provider": "letsencrypt", "domain_names": domains, "meta": meta}
    return ctx.client.certificates.create(payload, timeout=ctx.client.CERTIFICATE_TIMEOUT)


def cert_create(ctx: Context, args) -> None:
    if args.dns_credentials and not args.dns_provider:
        raise NpmError("--dns-credentials requires --dns-provider.")
    cert = request_letsencrypt(ctx, args.domain_names, args.email, args.dns_provider,
                               args.dns_credentials, args.propagation_seconds)
    ctx.out.created("certificate", cert, CERT_COLUMNS)


def _read(path: Optional[str]) -> Optional[bytes]:
    if path is None:
        return None
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise NpmError(f"Cannot read {path}: {exc.strerror}")


def cert_upload(ctx: Context, args) -> None:
    files = {"certificate": ("certificate.pem", _read(args.cert)),
             "certificate_key": ("key.pem", _read(args.key))}
    if args.intermediate:
        files["intermediate_certificate"] = ("intermediate.pem", _read(args.intermediate))

    certificates = ctx.client.certificates
    cert = certificates.create({"provider": "other", "nice_name": args.name})
    try:
        ctx.client.upload_certificate(cert["id"], files)
    except ApiError:
        certificates.delete(cert["id"])  # don't leave an empty certificate behind
        raise
    ctx.out.created("certificate", certificates.get(cert["id"]), CERT_COLUMNS)


def cert_renew(ctx: Context, args) -> None:
    info(f"Renewing certificate #{args.id}...")
    cert = ctx.client.renew_certificate(args.id)
    ctx.out.created("certificate", cert, CERT_COLUMNS, verb="Renewed")


def cert_download(ctx: Context, args) -> None:
    response = ctx.client.download_certificate(args.id)
    output = Path(args.output or f"certificate-{args.id}.zip")
    output.write_bytes(response.content)
    ctx.out.success(f"Saved certificate #{args.id} to {output}.")


def register(root) -> None:
    sub = group(root, "cert", "manage SSL certificates", aliases=["certs", "certificate", "certificates"])
    add_crud_commands(sub, "certificates", "certificate", CERT_COLUMNS, expand=("owner",), toggle=False)

    p = leaf(sub, "create", cert_create, "request a Let's Encrypt certificate", aliases=["add"])
    p.add_argument("-d", "--domain", dest="domain_names", action="append", required=True,
                   metavar="DOMAIN", help="domain name (repeatable)")
    p.add_argument("--email", help="Let's Encrypt account email")
    p.add_argument("--dns-provider", help="use a DNS challenge with this provider (e.g. cloudflare)")
    p.add_argument("--dns-credentials", type=text_or_file,
                   help="DNS provider credentials (use @file to read them from a file)")
    p.add_argument("--propagation-seconds", type=int, help="DNS propagation wait time")

    p = leaf(sub, "upload", cert_upload, "upload a custom certificate")
    p.add_argument("--name", required=True, help="display name")
    p.add_argument("--cert", required=True, help="certificate file (PEM)")
    p.add_argument("--key", required=True, help="private key file (PEM)")
    p.add_argument("--intermediate", help="intermediate certificate file (PEM)")

    p = leaf(sub, "renew", cert_renew, "renew a Let's Encrypt certificate")
    p.add_argument("id", type=int)

    p = leaf(sub, "download", cert_download, "download a certificate as a zip file")
    p.add_argument("id", type=int)
    p.add_argument("-o", "--output", help="output file (default: certificate-ID.zip)")
