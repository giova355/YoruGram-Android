"""Transactions for accounts, trials, subscriptions and VPN devices."""

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import re
import secrets
import sqlite3
import time
from uuid import uuid4

from .config import PRICE_RUB, TRIAL_SECONDS, wireguard_key

ACTIVE = "(a.owner = 1 OR a.paid_until > :now OR a.trial_started + :trial > :now)"
SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    token_digest BLOB NOT NULL UNIQUE,
    owner INTEGER NOT NULL DEFAULT 0 CHECK (owner IN (0, 1)),
    trial_started INTEGER,
    paid_until INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
);
CREATE UNIQUE INDEX IF NOT EXISTS singleton_owner ON accounts(owner) WHERE owner = 1;
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    public_key TEXT NOT NULL UNIQUE,
    slot INTEGER NOT NULL UNIQUE CHECK (slot BETWEEN 2 AND 254)
);
CREATE INDEX IF NOT EXISTS devices_by_account ON devices(account_id);
"""


class Denied(Exception):
    pass


class AccessRequired(Exception):
    pass


class Conflict(Exception):
    pass


class Capacity(Exception):
    pass


def token_digest(token: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise Denied("Invalid access token")
    return sha256(token.encode("ascii")).digest()


def entitlement(account: sqlite3.Row, now: int) -> dict:
    if account["owner"]:
        return {"tier": "OWNER", "managed_access": True, "expires_at": None,
                "can_start_trial": False, "price_rub": 0}
    trial_end = account["trial_started"] + TRIAL_SECONDS if account["trial_started"] is not None else 0
    paid_end = account["paid_until"] or 0
    valid = max(paid_end, trial_end)
    return {
        "tier": "ECLIPSE" if valid > now else "FREE",
        "managed_access": valid > now,
        "expires_at": valid if valid > now else None,
        "can_start_trial": account["trial_started"] is None and account["paid_until"] is None,
        "access_reason": ("paid" if paid_end >= trial_end else "trial") if valid > now else None,
        "price_rub": PRICE_RUB if paid_end > now else 0,
        "eclipse_monthly_price_rub": PRICE_RUB,
    }


class Store:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def transaction(self, write: bool = False):
        target = self.path if write else self.path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(target, timeout=5, uri=not write)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.transaction(write=True) as conn:
            conn.executescript(SCHEMA)

    def create_account(self, account_id: str, owner: bool = False) -> str:
        if not re.fullmatch(r"[a-z0-9_-]{3,64}", account_id):
            raise ValueError("Use 3–64 lowercase ASCII letters, digits, underscores or hyphens")
        token = secrets.token_urlsafe(32)
        try:
            with self.transaction(write=True) as conn:
                conn.execute(
                    "INSERT INTO accounts (id, token_digest, owner) VALUES (?, ?, ?)",
                    (account_id, token_digest(token), owner),
                )
        except sqlite3.IntegrityError:
            raise Conflict("Account ID or owner role already exists") from None
        return token

    def rotate_token(self, account_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self.transaction(write=True) as conn:
            if conn.execute(
                "UPDATE accounts SET token_digest = ?, enabled = 1 WHERE id = ?",
                (token_digest(token), account_id),
            ).rowcount != 1:
                raise Denied("Account does not exist")
        return token

    def disable(self, account_id: str) -> None:
        with self.transaction(write=True) as conn:
            if conn.execute("UPDATE accounts SET enabled = 0 WHERE id = ?", (account_id,)).rowcount != 1:
                raise Denied("Account does not exist")
            conn.execute("DELETE FROM devices WHERE account_id = ?", (account_id,))

    def grant(self, account_id: str, days: int) -> int:
        if not 1 <= days <= 366:
            raise ValueError("Enter a duration from 1 through 366 days")
        with self.transaction(write=True) as conn:
            row = conn.execute("SELECT * FROM accounts WHERE id = ? AND enabled = 1", (account_id,)).fetchone()
            if not row or row["owner"]:
                raise Denied("Active non-owner account required")
            now = int(time.time())
            start = max(now, row["paid_until"] or 0, (row["trial_started"] or 0) + TRIAL_SECONDS)
            until = start + days * 86400
            conn.execute("UPDATE accounts SET paid_until = ? WHERE id = ?", (until, account_id))
            return until

    @staticmethod
    def account(conn: sqlite3.Connection, digest: bytes) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM accounts WHERE token_digest = ? AND enabled = 1", (digest,),
        ).fetchone()
        if row is None:
            raise Denied("Invalid access token")
        return row

    def status(self, digest: bytes, now: int) -> dict:
        with self.transaction() as conn:
            return entitlement(self.account(conn, digest), now)

    def start_trial(self, digest: bytes, now: int) -> dict:
        with self.transaction(write=True) as conn:
            account = self.account(conn, digest)
            if entitlement(account, now)["can_start_trial"]:
                conn.execute("UPDATE accounts SET trial_started = ? WHERE id = ?", (now, account["id"]))
                account = self.account(conn, digest)
            return entitlement(account, now)

    def devices(self, digest: bytes) -> list[dict]:
        with self.transaction() as conn:
            account = self.account(conn, digest)
            return [dict(row) for row in conn.execute(
                "SELECT id, public_key, slot FROM devices WHERE account_id = ? ORDER BY slot",
                (account["id"],),
            )]

    def enroll(self, digest: bytes, public_key: str, now: int) -> dict:
        wireguard_key(public_key)
        with self.transaction(write=True) as conn:
            account = self.account(conn, digest)
            if not entitlement(account, now)["managed_access"]:
                raise AccessRequired("Managed VPN access requires an active entitlement")
            conn.execute(
                f"""DELETE FROM devices WHERE account_id NOT IN
                (SELECT a.id FROM accounts a WHERE a.enabled = 1 AND {ACTIVE})""",
                {"now": now, "trial": TRIAL_SECONDS},
            )
            existing = conn.execute("SELECT * FROM devices WHERE public_key = ?", (public_key,)).fetchone()
            if existing:
                if existing["account_id"] != account["id"]:
                    raise Conflict("The device key is already enrolled")
                return dict(existing)
            slots = {row["slot"]: row["account_id"] for row in conn.execute("SELECT slot, account_id FROM devices")}
            if not account["owner"] and list(slots.values()).count(account["id"]) >= 2:
                raise Capacity("This subscription supports two registered devices")
            slot = next((candidate for candidate in range(2, 255) if candidate not in slots), None)
            if slot is None:
                raise Capacity("The VPN node has reached its device limit")
            device_id = uuid4().hex
            conn.execute(
                "INSERT INTO devices VALUES (?, ?, ?, ?)",
                (device_id, account["id"], public_key, slot),
            )
            return {"id": device_id, "slot": slot, "public_key": public_key}

    def revoke(self, digest: bytes, device_id: str) -> None:
        with self.transaction(write=True) as conn:
            account = self.account(conn, digest)
            conn.execute("DELETE FROM devices WHERE id = ? AND account_id = ?", (device_id, account["id"]))

    def active_peers(self, now: int) -> list[dict]:
        with self.transaction() as conn:
            return [dict(row) for row in conn.execute(
                f"""SELECT d.public_key, d.slot FROM devices d JOIN accounts a ON a.id = d.account_id
                WHERE a.enabled = 1 AND {ACTIVE} ORDER BY d.slot""",
                {"now": now, "trial": TRIAL_SECONDS},
            )]
