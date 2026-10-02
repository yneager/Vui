from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

from .config import ALLOW_PRIVATE_TARGETS

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "169.254.169.254",
}


def _is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def host_resolves_public(host: str, port: int) -> bool:
    """Return True only when every resolved address is public.

    Requiring every address to be public avoids mixed public/private DNS answers and
    provides a useful defense against accidental SSRF in the browser crawler.
    """
    host = host.rstrip(".").lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local"):
        return False
    try:
        return _is_public_ip(host)
    except ValueError:
        pass
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        return False
    return bool(addresses) and all(_is_public_ip(ip) for ip in addresses)


def validate_target_url(raw: str, allow_private: bool | None = None) -> str:
    allow_private = ALLOW_PRIVATE_TARGETS if allow_private is None else allow_private
    raw = raw.strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are supported.")
    if not parsed.hostname:
        raise ValueError("A valid hostname is required.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are not allowed.")

    host = parsed.hostname.rstrip(".").lower()
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not allow_private and not host_resolves_public(host, port):
        raise ValueError("Target resolves to a private, reserved, or unavailable network address.")

    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme, netloc, path, parsed.query, ""))


def same_origin(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)

    def port(p):
        return p.port or (443 if p.scheme == "https" else 80)

    return pa.scheme == pb.scheme and pa.hostname == pb.hostname and port(pa) == port(pb)


def is_obviously_private_url(raw: str) -> bool:
    """Fast literal/local-name check; DNS-aware checks are handled by RequestGuard."""
    try:
        p = urlsplit(raw)
        if p.scheme not in {"http", "https"}:
            return False
        host = (p.hostname or "").lower()
        if host in _BLOCKED_HOSTS or host.endswith(".local"):
            return True
        try:
            return not _is_public_ip(host)
        except ValueError:
            return False
    except Exception:
        return True
