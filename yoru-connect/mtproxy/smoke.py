"""Exercise the compiled proxy locally and optionally contact Telegram through it."""

import argparse
import asyncio
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import logging
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import ProxyHandler, build_opener


CTL = Path(__file__).with_name("proxyctl.py")


def free_ports():
    with socket.socket() as client, socket.socket() as stats:
        client.bind(("127.0.0.1", 0))
        stats.bind(("127.0.0.1", 0))
        return client.getsockname()[1], stats.getsockname()[1]


def wait_for_stats(port, process, require_relay):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + (25 if require_relay else 5)
    stats = {}
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with opener.open(f"http://127.0.0.1:{port}/stats", timeout=1) as response:
                stats = dict(
                    line.split("\t", 1)
                    for line in response.read().decode().splitlines() if "\t" in line
                )
            if not require_relay or int(stats["total_ready_targets"]) > 0:
                return stats
        except OSError:
            pass
        time.sleep(0.2)
    for key in ("outbound_connections_created", "total_connect_failures", "ready_outbound_connections",
                "total_ready_targets", "total_active_targets"):
        if key in stats:
            print(f"{key}: {stats[key]}", file=sys.stderr)
    raise RuntimeError("MTProxy did not report a ready relay" if require_relay else "MTProxy stats unavailable")


async def request_pq(port, key):
    from telethon.network.connection.tcpmtproxy import ConnectionTcpMTProxyRandomizedIntermediate
    from telethon.network.mtprotoplainsender import MTProtoPlainSender
    from telethon.tl.functions import ReqPqMultiRequest
    from telethon.tl.types import ResPQ

    loggers = defaultdict(lambda: logging.getLogger("telegram-smoke"))
    connection = ConnectionTcpMTProxyRandomizedIntermediate(
        None, None, 2, loggers=loggers, proxy=("127.0.0.1", port, "dd" + key),
    )
    nonce = int.from_bytes(os.urandom(16), "little", signed=True)
    try:
        await connection.connect(timeout=5)
        sender = MTProtoPlainSender(connection, loggers=loggers)
        response = await asyncio.wait_for(sender.send(ReqPqMultiRequest(nonce)), timeout=8)
        assert isinstance(response, ResPQ) and response.nonce == nonce and response.pq
    finally:
        await connection.disconnect()


def check_relay_tcp(config):
    content = (config / "relay" / "proxy-multi.conf").read_text()
    endpoints = set(re.findall(r"(?m)^proxy_for\s+-?\d+\s+([\d.]+):(\d+);", content))

    def reachable(endpoint):
        host, port = endpoint
        try:
            with socket.create_connection((host, int(port)), timeout=3):
                return True
        except OSError:
            return False

    with ThreadPoolExecutor(max_workers=16) as pool:
        successes = sum(pool.map(reachable, endpoints))
    print(f"Direct TCP reachability to configured Telegram relays: {successes}/{len(endpoints)}", flush=True)


def test_node(engine, config, live, nat):
    ctl = [sys.executable, str(CTL), "--config-dir", str(config)]
    subprocess.run([*ctl, "init"], check=True)
    key_path = config / "client-secrets"
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    initial = key_path.read_text()
    subprocess.run([*ctl, "init"], check=True)
    assert key_path.read_text() == initial
    subprocess.run([*ctl, "rotate-key"], check=True)
    active, previous = key_path.read_text().splitlines()
    assert active != previous == initial.strip()
    link = subprocess.check_output([*ctl, "link", "proxy.example.test"], text=True)
    assert parse_qs(urlsplit(link.strip()).query)["secret"] == ["dd" + active]

    port, stats_port = free_ports()
    command = [
        *ctl, "run", "--engine", str(engine), "--key-file", str(key_path),
        "--port", str(port), "--stats-port", str(stats_port),
    ]
    if nat:
        command.extend(("--nat", nat))
    if live:
        check_relay_tcp(config)
        command.append("--verbose")
    with tempfile.TemporaryFile() as log:
        with subprocess.Popen(command, stdout=log, stderr=log) as process:
            try:
                wait_for_stats(stats_port, process, live)
                with socket.create_connection(("127.0.0.1", port), timeout=2):
                    pass
                try:
                    with socket.create_connection(("127.0.0.2", stats_port), timeout=2):
                        raise AssertionError("Stats accepted a connection outside 127.0.0.1")
                except ConnectionRefusedError:
                    pass
                argv = Path(f"/proc/{process.pid}/cmdline").read_bytes()
                assert active.encode() not in argv and previous.encode() not in argv
                status = subprocess.run(
                    [*ctl, "status", "--stats-port", str(stats_port)], capture_output=True, text=True,
                )
                print(status.stdout, end="")
                assert status.stdout.startswith("Local listener responds.")
                assert status.returncode == (1 if status.stdout.rstrip().endswith(": 0") else 0)
                print("Validated public client listener, loopback-only stats, and secret-free process arguments")
                if live:
                    asyncio.run(request_pq(port, active))
                    asyncio.run(request_pq(port, previous))
                    print("Telegram returned matching ResPQ through the proxy with both rotation keys")
            except Exception:
                log.seek(0)
                print(log.read(8192).decode(errors="replace"), file=sys.stderr)
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

    subprocess.run([*ctl, "retire-key"], check=True)
    assert key_path.read_text().splitlines() == [active]
    key_path.write_bytes(b"not-a-key\n")
    bad_key = subprocess.run(command, capture_output=True, timeout=5)
    assert bad_key.returncode == 2
    assert b"Client secret file must contain" in bad_key.stderr and b"not-a-key" not in bad_key.stderr
    print("Validated rotation, retirement, import link, and rejection of malformed secrets")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--nat")
    options = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        test_node(options.engine.resolve(), Path(directory), options.live, options.nat)
