import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from yoru_connect.api import create_app
from yoru_connect.config import Settings, TRIAL_SECONDS
from yoru_connect.profile import format_profile
from yoru_connect.storage import Conflict, Denied, Store, token_digest
from yoru_connect.worker import peer_config


def key(byte: int) -> str:
    return base64.b64encode(bytes([byte]) * 32).decode()


class ConnectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.settings = Settings(root / "state.sqlite3", "wg-yoru", "vpn.example.invalid:51820",
                                 key(9), "Pilot", "10.70.0.1", root / "server.key")
        self.store = Store(self.settings.database)
        self.client = TestClient(create_app(self.settings))
        self.headers = {"Authorization": "Bearer " + self.store.create_account("client")}
        self.owner_headers = {"Authorization": "Bearer " + self.store.create_account("giova355", owner=True)}

    def test_free_requires_entitlement_and_owner_is_free(self):
        self.assertEqual(self.client.get("/v1/nodes", headers=self.headers).status_code, 403)
        self.assertEqual(self.client.post("/v1/devices", headers=self.headers,
                                          json={"public_key": key(1)}).status_code, 403)
        owner = self.client.get("/v1/account", headers=self.owner_headers).json()
        self.assertEqual((owner["tier"], owner["price_rub"], owner["expires_at"]), ("OWNER", 0, None))
        self.assertEqual(self.client.post("/v1/devices", headers=self.owner_headers,
                                          json={"public_key": key(1)}).status_code, 200)
        with self.assertRaises(Conflict):
            self.store.create_account("other-owner", owner=True)
        with self.assertRaises(Denied):
            self.store.grant("giova355", 30)

    def test_trial_is_once_and_peer_expires(self):
        now = int(time.time())
        with patch("yoru_connect.api.time.time", return_value=now):
            trial = self.client.post("/v1/trial", headers=self.headers).json()
            self.assertEqual(trial["expires_at"], now + TRIAL_SECONDS)
            self.assertEqual(trial["price_rub"], 0)
            self.assertEqual(self.client.post("/v1/trial", headers=self.headers).json(), trial)
            response = self.client.post("/v1/devices", headers=self.headers, json={"public_key": key(2)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.store.active_peers(now + TRIAL_SECONDS - 1)), 1)
        self.assertEqual(self.store.active_peers(now + TRIAL_SECONDS), [])
        with patch("yoru_connect.api.time.time", return_value=now + TRIAL_SECONDS):
            self.assertFalse(self.client.post("/v1/trial", headers=self.headers).json()["managed_access"])

    def test_paid_extension_and_rotation(self):
        self.store.grant("client", 30)
        state = self.client.get("/v1/account", headers=self.headers).json()
        self.assertEqual((state["tier"], state["access_reason"], state["price_rub"]), ("ECLIPSE", "paid", 149))
        self.assertGreater(self.store.grant("client", 30), state["expires_at"])
        token = self.store.rotate_token("client")
        self.assertEqual(self.client.get("/v1/account", headers=self.headers).status_code, 401)
        response = self.client.get("/v1/account", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        with sqlite3.connect(self.settings.database) as conn:
            stored = conn.execute("SELECT token_digest FROM accounts WHERE id='client'").fetchone()[0]
        self.assertEqual(stored, token_digest(token))
        self.assertNotEqual(stored, token.encode())

    def test_enrollment_and_revocation_are_scoped(self):
        self.client.post("/v1/trial", headers=self.headers)
        data = self.client.post("/v1/devices", headers=self.headers, json={"public_key": key(3)}).json()
        self.assertEqual(data["allowed_ips"], ["0.0.0.0/0", "::/0"])
        self.assertNotIn("private_key", data)
        route = "/v1/devices/" + data["id"]
        self.assertEqual(self.client.delete(route, headers=self.owner_headers).status_code, 204)
        self.assertEqual(len(self.store.active_peers(int(time.time()))), 1)
        other = self.client.post("/v1/devices", headers=self.owner_headers, json={"public_key": key(3)})
        self.assertEqual(other.status_code, 409)
        self.assertEqual(self.client.delete(route, headers=self.headers).status_code, 204)
        self.assertEqual(self.store.active_peers(int(time.time())), [])

    def test_parallel_retry_and_capacity(self):
        self.client.post("/v1/trial", headers=self.headers)
        digest = token_digest(self.headers["Authorization"].removeprefix("Bearer "))
        with ThreadPoolExecutor(max_workers=6) as workers:
            ids = set(workers.map(lambda _: self.store.enroll(digest, key(4), int(time.time()))["id"], range(12)))
        self.assertEqual(len(ids), 1)
        self.assertEqual(self.client.post("/v1/devices", headers=self.headers,
                                          json={"public_key": key(5)}).status_code, 200)
        self.assertEqual(self.client.post("/v1/devices", headers=self.headers,
                                          json={"public_key": key(6)}).status_code, 409)
        self.store.disable("client")
        self.assertEqual(self.store.active_peers(int(time.time())), [])
        self.assertEqual(self.client.get("/v1/account", headers=self.headers).status_code, 401)

    def test_protocol_configuration_and_reject_privilege_fields(self):
        self.assertEqual(self.client.post("/v1/devices", headers=self.headers,
                                          json={"public_key": key(6), "owner": True}).status_code, 422)
        self.assertEqual(self.client.post("/v1/devices", headers=self.owner_headers,
                                          json={"public_key": "!" * 44}).status_code, 422)
        device = self.client.post("/v1/devices", headers=self.owner_headers, json={"public_key": key(7)}).json()
        configuration = format_profile(key(8), device)
        self.assertIn("PersistentKeepalive = 25", configuration)
        self.assertIn("MTU = 1280", configuration)
        device["endpoint"] = "example.invalid:51820\nPostUp = test"
        with self.assertRaises(ValueError):
            format_profile(key(8), device)
        config = peer_config(self.settings, key(9), self.store.active_peers(int(time.time())))
        self.assertIn("AllowedIPs = 10.70.0.2/32, fd70:7952:7500::2/128", config)
        self.assertNotIn(key(8), config)


if __name__ == "__main__":
    unittest.main()
