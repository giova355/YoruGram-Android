"""Validated deployment settings shared by the API and the WireGuard worker."""

import base64
from dataclasses import dataclass
from ipaddress import ip_address
import os
from pathlib import Path
import re

TRIAL_SECONDS = 7 * 86400
IPV4_PREFIX = "10.70.0"
IPV6_PREFIX = "fd70:7952:7500"
PRICE_RUB = 149


def wireguard_key(value: str) -> str:
    try:
        key = base64.b64decode(value, validate=True)
    except ValueError:
        raise ValueError("Expected a 32-byte WireGuard key in base64") from None
    if len(key) != 32 or not any(key) or base64.b64encode(key).decode() != value:
        raise ValueError("Expected a canonical nonzero WireGuard key")
    return value


def endpoint_address(value: str) -> str:
    host, separator, port = value.rpartition(":")
    if not separator or not port.isascii() or not port.isdecimal() or len(port) > 5:
        raise ValueError("YORU_ENDPOINT must be a host and UDP port")
    if not 1 <= int(port) <= 65535:
        raise ValueError("Invalid UDP port")
    if host.startswith("[") and host.endswith("]"):
        if "%" in host or ip_address(host[1:-1]).version != 6:
            raise ValueError("Expected an unscoped IPv6 endpoint")
    elif not re.fullmatch(r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
        raise ValueError("Invalid WireGuard endpoint host")
    return value


def tunnel_addresses(slot: int) -> tuple[str, str]:
    if not 2 <= slot <= 254:
        raise ValueError("Invalid peer address slot")
    return f"{IPV4_PREFIX}.{slot}/32", f"{IPV6_PREFIX}::{slot:x}/128"


@dataclass(frozen=True)
class Settings:
    database: Path
    interface: str
    endpoint: str
    public_key: str
    region: str
    dns: str
    private_key_file: Path

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,14}", self.interface):
            raise ValueError("Invalid WireGuard interface name")
        endpoint_address(self.endpoint)
        wireguard_key(self.public_key)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]{0,39}", self.region):
            raise ValueError("Invalid region label")
        if "%" in self.dns or ip_address(self.dns).version != 4:
            raise ValueError("Use an IPv4 DNS resolver reachable through the tunnel")

    @property
    def port(self) -> int:
        return int(self.endpoint.rsplit(":", 1)[1])

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database=Path(os.environ.get("YORU_DB", "/var/lib/yoru-connect/state.sqlite3")),
            interface=os.environ.get("YORU_INTERFACE", "wg-yoru"),
            endpoint=os.environ["YORU_ENDPOINT"],
            public_key=os.environ["YORU_SERVER_PUBLIC_KEY"],
            region=os.environ["YORU_REGION"],
            dns=os.environ["YORU_DNS"],
            private_key_file=Path(os.environ.get("YORU_PRIVATE_KEY_FILE", "/etc/wireguard/yoru.key")),
        )
