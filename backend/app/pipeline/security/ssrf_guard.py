"""Anti-SSRF defense in depth: scheme allowlisting, DNS pre-resolution, and CIDR blocklist.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFSecurityError(ValueError):
    """Raised when a URL or resolved IP violates anti-SSRF security policies."""


DEFAULT_BLOCKED_CIDRS = [
    # Loopback
    "127.0.0.0/8",
    "::1/128",
    # RFC 1918 Private IPv4
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    # RFC 4193 Unique Local IPv6 (ULA)
    "fc00::/7",
    # Link-Local
    "169.254.0.0/16",
    "fe80::/10",
    # Carrier-Grade NAT (RFC 6598)
    "100.64.0.0/10",
    # Broadcast / Current network
    "0.0.0.0/8",
    # IPv4-Mapped IPv6
    "::ffff:0:0/96",
    # Cloud Metadata endpoints (AWS, Azure, GCP, OpenStack)
    "169.254.169.254/32",
    "fd00:ec2::254/128",
]


class SSRFGuard:
    """Validates URLs and resolved IP addresses against SSRF attack vectors."""

    def __init__(
        self,
        blocked_cidrs: list[str] | None = None,
        allowed_schemes: tuple[str, ...] = ("http", "https"),
    ) -> None:
        self.allowed_schemes = tuple(s.lower() for s in allowed_schemes)
        cidrs = blocked_cidrs if blocked_cidrs is not None else DEFAULT_BLOCKED_CIDRS
        self._blocked_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
            ipaddress.ip_network(cidr, strict=False) for cidr in cidrs
        ]

    def is_safe_ip(self, ip_str: str) -> bool:
        """Returns True if the IP address is public and safe to connect to."""
        try:
            ip = ipaddress.ip_address(ip_str.strip("[]"))
        except ValueError:
            return False

        # Unwrap IPv4-mapped IPv6 address (e.g. ::ffff:127.0.0.1)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            mapped_ip = ip.ipv4_mapped
            if not self.is_safe_ip(str(mapped_ip)):
                return False

        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False

        for network in self._blocked_networks:
            if ip in network:
                return False

        return True

    def resolve_and_validate_host(self, hostname: str, port: int) -> list[str]:
        """Resolves hostname and verifies that all resolved IP addresses are safe.

        Returns the list of validated IP strings.
        Raises SSRFSecurityError if resolution fails or any IP is unsafe.
        """
        clean_host = hostname.strip("[]")
        try:
            direct_ip = ipaddress.ip_address(clean_host)
            is_ip = True
        except ValueError:
            is_ip = False

        if is_ip:
            if not self.is_safe_ip(str(direct_ip)):
                raise SSRFSecurityError(
                    f"Direct connection to blocked IP '{direct_ip}' is prohibited."
                )
            return [str(direct_ip)]

        try:
            addr_info = socket.getaddrinfo(
                hostname,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as e:
            raise SSRFSecurityError(f"Failed to resolve hostname '{hostname}': {e}") from e

        if not addr_info:
            raise SSRFSecurityError(f"No IP address resolved for hostname '{hostname}'.")

        safe_ips: list[str] = []
        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = str(sockaddr[0])
            if not self.is_safe_ip(ip_str):
                raise SSRFSecurityError(
                    f"Hostname '{hostname}' resolved to blocked IP '{ip_str}'."
                )
            safe_ips.append(ip_str)

        return safe_ips

    def validate_url(self, url: str) -> None:
        """Validates that a URL uses an allowed scheme and does not resolve to a blocked IP.

        Raises SSRFSecurityError if validation fails.
        """
        if not url or not isinstance(url, str):
            raise SSRFSecurityError("URL cannot be empty")

        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in self.allowed_schemes:
            raise SSRFSecurityError(
                f"Disallowed URL scheme '{scheme}'. Only {self.allowed_schemes} are permitted."
            )

        # Disallow embedded credentials in URL (e.g. http://user:pass@host)
        if parsed.username or parsed.password:
            raise SSRFSecurityError("URLs containing user credentials are not permitted.")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFSecurityError("URL does not contain a valid hostname.")

        port = parsed.port or (443 if scheme == "https" else 80)
        self.resolve_and_validate_host(hostname, port)
