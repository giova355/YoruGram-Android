"""Local operator commands. The public HTTP API cannot create or elevate accounts."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path

from .config import Settings
from .storage import Conflict, Denied, Store
from .worker import reconcile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.environ.get("YORU_DB", "/var/lib/yoru-connect/state.sqlite3"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    for name in ("create", "rotate-token", "disable", "grant"):
        command = commands.add_parser(name)
        command.add_argument("account")
        if name == "create":
            command.add_argument("--owner", action="store_true")
        if name == "grant":
            command.add_argument("--days", type=int, default=30)
    worker = commands.add_parser("reconcile")
    worker.add_argument("--runtime-directory", default="/run/yoru-connect-wg")
    args = parser.parse_args()

    store = Store(Path(args.database))
    try:
        match args.command:
            case "init":
                store.initialize()
            case "create":
                print(store.create_account(args.account, args.owner))
            case "rotate-token":
                print(store.rotate_token(args.account))
            case "disable":
                store.disable(args.account)
            case "grant":
                print(datetime.fromtimestamp(store.grant(args.account, args.days), timezone.utc).isoformat())
            case "reconcile":
                print(f"Applied {reconcile(Settings.from_env(), Path(args.runtime_directory))} WireGuard peers")
    except (Conflict, Denied, ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
