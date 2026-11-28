#!/usr/bin/env python3
"""Operate a Yoru Connect MTProxy node."""

import argparse
import fcntl
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import tempfile
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener, urlopen


TELEGRAM = "https://core.telegram.org"
RELAY_FILES = ("proxy-secret", "proxy-multi.conf")
KEY_FILE = "client-secrets"


def port_number(value):
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def ipv4_pair(value):
    addresses = value.split(":")
    if len(addresses) != 2:
        raise argparse.ArgumentTypeError("NAT mapping must be LOCAL_IP:PUBLIC_IP")
    try:
        return ":".join(str(ipaddress.IPv4Address(address)) for address in addresses)
    except ipaddress.AddressValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def write_keys(path, keys):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        try:
            file.write(("\n".join(keys) + "\n").encode("ascii"))
            file.flush()
            os.fsync(file.fileno())
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def read_keys(path):
    keys = path.read_text(encoding="ascii").splitlines()
    if not 1 <= len(keys) <= 2 or any(not re.fullmatch(r"[a-f0-9]{32}", key) for key in keys):
        raise ValueError("expected one or two Yoru client keys")
    return keys


def download(name, limit):
    request = Request(f"{TELEGRAM}/{name}", headers={"User-Agent": "Yoru-Connect-MTProxy/1"})
    with urlopen(request, timeout=15) as response:
        if response.geturl() != request.full_url:
            raise ValueError("unexpected redirect from Telegram configuration endpoint")
        contents = response.read(limit + 1)
    if not 0 < len(contents) <= limit:
        raise ValueError("unexpected length of Telegram relay configuration")
    return contents


def refresh_relay(config_dir):
    relay_secret = download("getProxySecret", 256)
    relay_config = download("getProxyConfig", 65536)
    if len(relay_secret) < 32 or not re.search(rb"(?m)^proxy_for\s+-?\d+\s+", relay_config):
        raise ValueError("unexpected format of Telegram relay configuration")

    current = config_dir / "relay"
    if current.is_dir() and tuple((current / name).read_bytes() for name in RELAY_FILES) == (
        relay_secret, relay_config
    ):
        print("Telegram relay files are current")
        return

    staged = Path(tempfile.mkdtemp(prefix="relay-", dir=config_dir))
    link = config_dir / ".relay-next"
    try:
        for name, contents in zip(RELAY_FILES, (relay_secret, relay_config)):
            path = staged / name
            path.write_bytes(contents)
            path.chmod(0o644)
        staged.chmod(0o755)
        link.unlink(missing_ok=True)
        link.symlink_to(staged.name, target_is_directory=True)
        link.replace(current)
    except BaseException:
        link.unlink(missing_ok=True)
        shutil.rmtree(staged)
        raise
    print("Updated Telegram relay files")


def update_config(args):
    config_dir = args.config_dir
    config_dir.mkdir(parents=True, exist_ok=True)
    key_path = config_dir / KEY_FILE
    with (config_dir / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command in {"init", "refresh"}:
            refresh_relay(config_dir)
            if args.command == "init" and not key_path.exists():
                write_keys(key_path, [secrets.token_hex(16)])
                print("Created private client key")
        elif args.command == "rotate-key":
            keys = read_keys(key_path)
            if len(keys) != 1:
                raise ValueError("retire the previous key before rotating again")
            write_keys(key_path, [secrets.token_hex(16), keys[0]])
            print("Staged a new client key and kept the previous one")
        else:
            write_keys(key_path, read_keys(key_path)[:1])
            print("Staged retirement of the previous client key")


def run_proxy(args):
    if args.port == args.stats_port:
        raise ValueError("client port and stats port must differ")
    relay = (args.config_dir / "relay").resolve(strict=True)
    command = [
        str(args.engine), "--http-stats", "-p", str(args.stats_port), "-H", str(args.port),
        "--client-secret-file", str(args.key_file), "--aes-pwd", str(relay / RELAY_FILES[0]),
    ]
    if args.nat:
        command.extend(("--nat-info", args.nat))
    command.append(str(relay / RELAY_FILES[1]))
    os.execv(args.engine, command)


def check_status(stats_port):
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{stats_port}/stats", timeout=3) as response:
        stats = dict(
            line.split("\t", 1)
            for line in response.read(1 << 20).decode("ascii").splitlines() if "\t" in line
        )
    targets = int(stats["total_ready_targets"])
    print(f"Local listener responds. Ready Telegram relay targets: {targets}")
    return 0 if targets > 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path("/etc/yoru-mtproxy"))
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "refresh", "rotate-key", "retire-key"):
        commands.add_parser(command)
    link = commands.add_parser("link")
    link.add_argument("host")
    link.add_argument("--port", type=port_number, default=443)
    run = commands.add_parser("run")
    run.add_argument("--engine", type=Path, required=True)
    run.add_argument("--key-file", type=Path, required=True)
    run.add_argument("--port", type=port_number, default=443)
    run.add_argument("--stats-port", type=port_number, default=2399)
    run.add_argument("--nat", type=ipv4_pair)
    status = commands.add_parser("status")
    status.add_argument("--stats-port", type=port_number, default=2399)
    args = parser.parse_args()

    try:
        if args.command == "run":
            run_proxy(args)
        elif args.command == "status":
            return check_status(args.stats_port)
        elif args.command == "link":
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", args.host):
                raise ValueError("use a DNS name or IPv4 address without a port")
            key = read_keys(args.config_dir / KEY_FILE)[0]
            query = urlencode({"server": args.host, "port": args.port, "secret": "dd" + key})
            print(f"tg://proxy?{query}")
        else:
            update_config(args)
    except (KeyError, OSError, ValueError) as error:
        print(f"MTProxy: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
