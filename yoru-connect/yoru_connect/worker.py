"""Reconcile the dedicated WireGuard interface from active database leases."""

import fcntl
from pathlib import Path
import subprocess
import tempfile
import time

from .config import Settings, tunnel_addresses, wireguard_key
from .storage import Store


def peer_config(settings: Settings, private_key: str, peers: list[dict]) -> str:
    blocks = [f"[Interface]\nPrivateKey = {wireguard_key(private_key)}\nListenPort = {settings.port}\n"]
    for peer in peers:
        addresses = ", ".join(tunnel_addresses(peer["slot"]))
        blocks.append(f"[Peer]\nPublicKey = {wireguard_key(peer['public_key'])}\nAllowedIPs = {addresses}\n")
    return "\n".join(blocks)


def reconcile(settings: Settings, runtime_path: Path) -> int:
    key = wireguard_key(settings.private_key_file.read_text(encoding="ascii").strip())
    public = subprocess.run(
        ["/usr/bin/wg", "pubkey"], input=key + "\n", text=True,
        capture_output=True, check=True, timeout=5,
    ).stdout.strip()
    if public != settings.public_key:
        raise ValueError("Server key does not match YORU_SERVER_PUBLIC_KEY")
    with (runtime_path / "wireguard.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        peers = Store(settings.database).active_peers(int(time.time()))
        conf = peer_config(settings, key, peers)
        with tempfile.NamedTemporaryFile(mode="w", dir=runtime_path, prefix="wg-", encoding="ascii") as staged:
            staged.write(conf)
            staged.flush()
            try:
                subprocess.run(
                    ["/usr/bin/wg", "syncconf", settings.interface, staged.name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=10,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                raise RuntimeError("WireGuard could not apply the desired peer state") from None
        return len(peers)
