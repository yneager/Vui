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
    if not allow_private:
        if host in _BLOCKED_HOSTS or host.endswith(".local"):
            raise ValueError("Private/local network targets are blocked by default.")
        try:
            if not _is_public_ip(host):
                raise ValueError("Private/local network targets are blocked by default.")
        except ValueError as exc:
            if "blocked" in str(exc):
                raise
            # hostname rather than literal IP
            try:
                addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))}
            except socket.gaierror as dns_exc:
                raise ValueError(f"Could not resolve host: {host}") from dns_exc
            if not addresses or any(not _is_public_ip(ip) for ip in addresses):
                raise ValueError("Target resolves to a private/reserved network address.")

    port = parsed.port
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme, netloc, path, parsed.query, ""))


def same_origin(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    def port(p):
        return p.port or (443 if p.scheme == "https" else 80)
    return pa.scheme == pb.scheme and pa.hostname == pb.hostname and port(pa) == port(pb)


def is_obviously_private_url(raw: str) -> bool:
    """Fast request-time guard for redirects/subresources. DNS validation happens at scan start."""
    try:
        p = urlsplit(raw)
        host = (p.hostname or "").lower()
        if host in _BLOCKED_HOSTS or host.endswith(".local"):
            return True
        try:
            return not _is_public_ip(host)
        except ValueError:
            return False
    except Exception:
        return True
