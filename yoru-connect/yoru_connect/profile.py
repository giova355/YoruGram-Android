"""Create a WireGuard profile using a local key and the Yoru Connect HTTPS API."""

import argparse
from getpass import getpass
from http.client import HTTPSConnection
from ipaddress import ip_address, ip_interface
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from .config import endpoint_address, wireguard_key


def enroll(origin: str, token: str, public_key: str) -> dict:
    url = urlsplit(origin)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.path not in ("", "/") or url.query or url.fragment):
        raise ValueError("Use the HTTPS origin of your Yoru Connect service")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ValueError("Invalid Yoru Connect access token")
    connection = HTTPSConnection(url.hostname, url.port, timeout=15)
    try:
        connection.request(
            "POST", "/v1/devices", json.dumps({"public_key": public_key}),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"Enrollment returned HTTP {response.status}")
        body = response.read(8193)
        if len(body) > 8192:
            raise RuntimeError("Enrollment response exceeds 8 KiB")
        return json.loads(body)
    finally:
        connection.close()


def format_profile(key: str, device: dict) -> str:
    addresses = tuple(ip_interface(value) for value in device["addresses"])
    if len(addresses) != 2 or {address.version for address in addresses} != {4, 6}:
        raise ValueError("The profile must contain an IPv4 and IPv6 address")
    address_list = ", ".join(map(str, addresses))
    dns = ip_address(device["dns"])
    if dns.version != 4:
        raise ValueError("Expected an IPv4 DNS resolver")
    server_key = wireguard_key(device["server_public_key"])
    endpoint = endpoint_address(device["endpoint"])
    mtu = device["mtu"]
    keepalive = device["persistent_keepalive"]
    if type(mtu) is not int or not 1280 <= mtu <= 1500:
        raise ValueError("Invalid tunnel MTU")
    if type(keepalive) is not int or not 0 <= keepalive <= 60:
        raise ValueError("Invalid keepalive interval")
    return (
        f"[Interface]\nPrivateKey = {wireguard_key(key)}\nAddress = {address_list}\n"
        f"DNS = {dns}\nMTU = {mtu}\n\n[Peer]\nPublicKey = {server_key}\n"
        f"Endpoint = {endpoint}\nAllowedIPs = 0.0.0.0/0, ::/0\nPersistentKeepalive = {keepalive}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", help="HTTPS origin of the service")
    parser.add_argument("output", type=Path, help="New WireGuard .conf file")
    args = parser.parse_args()

    try:
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                       "w", encoding="ascii") as output:
            try:
                token = getpass("Yoru Connect access token: ")
                key = wireguard_key(subprocess.run(
                    ["wg", "genkey"], capture_output=True, text=True, check=True, timeout=5,
                ).stdout.strip())
                public = wireguard_key(subprocess.run(
                    ["wg", "pubkey"], input=key + "\n", capture_output=True, text=True, check=True, timeout=5,
                ).stdout.strip())
                output.write(format_profile(key, enroll(args.origin, token, public)))
            except BaseException:
                output.close()
                args.output.unlink(missing_ok=True)
                raise
    except (OSError, KeyError, TypeError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Could not create the profile ({type(error).__name__}).\n")
    print(f"Profile created: {args.output}")


if __name__ == "__main__":
    main()
