"""Offline contract and conflict tests; never contact a router."""

import asyncio
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "dhcp", Path(__file__).parents[1] / "custom_components/iptime_manager/dhcp.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


# Summary: Simulate the observed RPC contract and concurrent reservation writes.
# Related files: custom_components/iptime_manager/dhcp.py, main.dart.js.
class Router:
    _beta_ui = True

    def __init__(self):
        self.rows = []
        self.stations = []
        self.calls = []
        self.fail_read = False
        self.ignore_write = False

    async def _async_service_json(self, method, params):
        await asyncio.sleep(0)
        self.calls.append((method, params))
        if method == "dhcpd/reservedaddr/show":
            return {} if self.fail_read else {"result": [dict(row) for row in self.rows]}
        if method == "network/interface/lan/info":
            return {"result": {"ip": "192.168.0.1", "mask": "255.255.255.0"}}
        if method == "network/interface/lan/stations":
            return {"result": self.stations}
        if not self.ignore_write:
            if method.endswith("/add"):
                self.rows = [row for row in self.rows if row["mac"] != params["mac"]]
                self.rows.append(dict(params))
            if method.endswith("/del"):
                self.rows = [row for row in self.rows if row["mac"] not in params["mac"]]
        return {"result": True}


class DHCPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.router = Router()
        self.client = module.DHCPReservations(self.router)
        self.mac = "02:11:22:33:44:55"

    async def test_crud_and_description_preservation(self):
        self.assertEqual(await self.client.execute("get"), {"reservations": []})
        await self.client.execute("add", self.mac, "192.168.0.50", "device")
        result = await self.client.execute("update", self.mac.lower(), "192.168.0.51")
        self.assertEqual(result["reservations"][0]["description"], "device")
        await self.client.execute("update", self.mac, "192.168.0.51", "")
        await self.client.execute("delete", self.mac)
        self.assertEqual(self.router.calls[-2], ("dhcpd/reservedaddr/del", {"ntag": "lan", "mac": [self.mac]}))
        self.assertEqual(self.router.rows, [])

    async def test_duplicates_and_missing_targets(self):
        await self.client.execute("add", self.mac, "192.168.0.50")
        for operation, mac in (("add", self.mac), ("add", "02:11:22:33:44:66"), ("update", "02:11:22:33:44:66"), ("delete", "02:11:22:33:44:66")):
            with self.assertRaises(ValueError):
                await self.client.execute(operation, mac, "192.168.0.50")

    async def test_bad_addresses_never_write(self):
        for ip in ("192.168.0.0", "192.168.0.255", "192.168.0.1", "192.168.1.5", "224.0.0.1", "invalid", "::1"):
            with self.assertRaises(ValueError):
                await self.client.execute("add", self.mac, ip)
        self.assertFalse(any(method.endswith("/add") for method, _ in self.router.calls))

    async def test_station_conflict(self):
        self.router.stations = [{"mac": "02:11:22:33:44:66", "info": {"ip": "192.168.0.50"}}]
        with self.assertRaises(ValueError):
            await self.client.execute("add", self.mac, "192.168.0.50")

    async def test_failed_read_never_writes(self):
        self.router.fail_read = True
        with self.assertRaises(ValueError):
            await self.client.execute("add", self.mac, "192.168.0.50")
        self.assertEqual(len(self.router.calls), 1)

    async def test_verification_detects_ignored_write(self):
        self.router.ignore_write = True
        with self.assertRaises(ValueError):
            await self.client.execute("add", self.mac, "192.168.0.50")

    async def test_concurrent_duplicate_ip(self):
        results = await asyncio.gather(
            self.client.execute("add", self.mac, "192.168.0.50"),
            self.client.execute("add", "02:11:22:33:44:66", "192.168.0.50"),
            return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(result, ValueError) for result in results), 1)
        self.assertEqual(len(self.router.rows), 1)

    async def test_unsupported_ui_and_malformed_response(self):
        self.router._beta_ui = False
        with self.assertRaises(ValueError):
            await self.client.execute("get")
        self.router._beta_ui = True
        self.router.rows = [{"mac": self.mac}]
        with self.assertRaises(ValueError):
            await self.client.execute("get")


if __name__ == "__main__":
    unittest.main()
