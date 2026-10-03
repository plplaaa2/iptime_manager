"""Offline tests for port forwarding RPCs and conflict prevention."""

import asyncio
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "port_forward", Path(__file__).parents[1] / "custom_components/iptime_manager/port_forward.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


# Summary: Simulate exact UI request identities and rule list responses.
# Related files: custom_components/iptime_manager/port_forward.py, main.dart.js.
class Router:
    _beta_ui = True

    def __init__(self):
        self.rows = []
        self.upnp = []
        self.calls = []
        self.fail_get = False
        self.ignore_write = False

    async def _async_service_json(self, method, params):
        await asyncio.sleep(0)
        self.calls.append((method, copy.deepcopy(params)))
        if method == "portforward/get":
            return {} if self.fail_get else {"result": copy.deepcopy(self.rows if params == "user" else self.upnp)}
        if method == "network/interface/lan/info":
            return {"result": {"ip": "192.168.0.1", "mask": "255.255.255.0"}}
        if not self.ignore_write:
            if method == "portforward/add":
                self.rows.append(dict(params, fixed=False))
            elif method == "portforward/set":
                row = next(row for row in self.rows if row["name"] == params["current"])
                row.update({key: value for key, value in params.items() if key != "current"})
            elif method == "portforward/del":
                assert params["type"] == "user"
                self.rows = [row for row in self.rows if row["name"] not in params["list"]]
        return {"result": copy.deepcopy(self.rows)}


class PortForwardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.router = Router()
        self.client = module.PortForwardRules(self.router)
        self.rule = dict(name="web", protocol="tcp", internal_ip="192.168.0.50",
                         external_port_start=8080, internal_port_start=80)

    def writes(self):
        return [(method, params) for method, params in self.router.calls if method in ("portforward/add", "portforward/set", "portforward/del")]

    async def test_crud_partial_update_and_rename(self):
        self.assertEqual(await self.client.execute("get"), {"rules": [], "upnp_rules": []})
        await self.client.execute("add", **self.rule)
        self.assertEqual(self.writes()[0][1], {"name": "web", "active": True, "protocol": "tcp", "target": "192.168.0.50", "src": {"start": 8080}, "dst": {"start": 80}})
        await self.client.execute("update", name="web", new_name="site", internal_ip="192.168.0.51")
        self.assertEqual(self.router.rows[0]["src"], {"start": 8080})
        self.assertEqual(self.writes()[-1][1]["current"], "web")
        await self.client.execute("delete", name="site")
        self.assertEqual(self.writes()[-1], ("portforward/del", {"type": "user", "list": ["site"]}))
        self.assertEqual(self.router.rows, [])

    async def test_disable_and_reenable_preserves_mapping(self):
        await self.client.execute("add", **self.rule)
        await self.client.execute("update", name="web", active=False)
        self.assertEqual(self.writes()[-1][1], {"current": "web", "active": False})
        await self.client.execute("update", name="web", active=True)
        self.assertTrue(self.router.rows[0]["active"])
        with self.assertRaises(ValueError):
            await self.client.execute("update", name="web", active=False, internal_port_start=90)

    async def test_duplicate_name_and_missing_rule(self):
        await self.client.execute("add", **self.rule)
        with self.assertRaises(ValueError):
            await self.client.execute("add", **self.rule)
        for operation in ("update", "delete"):
            with self.assertRaises(ValueError):
                await self.client.execute(operation, name="missing")

    async def test_protocol_overlap_and_disjoint_protocol(self):
        await self.client.execute("add", **self.rule)
        await self.client.execute("add", **dict(self.rule, name="udp", protocol="udp"))
        for protocol in ("tcp", "udp", "tcpudp"):
            with self.assertRaises(ValueError):
                await self.client.execute("add", **dict(self.rule, name="conflict", protocol=protocol))

    async def test_upnp_overlap_and_disabled_rules(self):
        self.router.upnp = [{"name": "auto", "active": True, "protocol": "tcpudp", "src": {"start": 8070, "end": 8090}}]
        with self.assertRaises(ValueError):
            await self.client.execute("add", **self.rule)
        self.assertEqual(self.writes(), [])
        self.router.upnp[0]["active"] = False
        await self.client.execute("add", **self.rule)

    async def test_ranges_and_invalid_ports(self):
        self.assertEqual(module.port_number(8080.0), 8080)
        self.assertEqual(module.port_number("8080"), 8080)
        for value in (True, 8080.5, "8080.5", 0, 65536, None):
            with self.assertRaises(ValueError):
                module.port_number(value)
        await self.client.execute("add", **dict(self.rule, external_port_end=8082, internal_port_end=82))
        await self.client.execute("update", name="web", external_port_start=9090, internal_port_start=90)
        self.assertEqual(self.router.rows[0]["src"], {"start": 9090})
        for changes in ({"external_port_start": 0}, {"internal_port_start": 65536}, {"external_port_end": 8079}, {"external_port_end": 8082}, {"external_port_start": True}):
            with self.assertRaises(ValueError):
                await self.client.execute("add", **dict(self.rule, name="bad", **changes))

    async def test_bad_targets_and_incomplete_add(self):
        for ip in ("192.168.0.0", "192.168.0.255", "192.168.0.1", "192.168.1.50", "::1"):
            with self.assertRaises(ValueError):
                await self.client.execute("add", **dict(self.rule, internal_ip=ip))
        with self.assertRaises(ValueError):
            await self.client.execute("add", name="incomplete")
        self.assertEqual(self.writes(), [])

    async def test_fixed_rules_are_protected(self):
        await self.client.execute("add", **self.rule)
        self.router.rows[0]["fixed"] = True
        for operation in ("update", "delete"):
            with self.assertRaises(ValueError):
                await self.client.execute(operation, name="web")

    async def test_failed_read_and_ignored_write(self):
        self.router.fail_get = True
        with self.assertRaises(ValueError):
            await self.client.execute("add", **self.rule)
        self.assertEqual(self.writes(), [])
        self.router.fail_get = False
        self.router.ignore_write = True
        with self.assertRaises(ValueError):
            await self.client.execute("add", **self.rule)

    async def test_concurrent_overlap(self):
        results = await asyncio.gather(self.client.execute("add", **self.rule), self.client.execute("add", **dict(self.rule, name="other")), return_exceptions=True)
        self.assertEqual(sum(isinstance(result, ValueError) for result in results), 1)
        self.assertEqual(len(self.router.rows), 1)

    async def test_unsupported_and_malformed_lists(self):
        self.router._beta_ui = False
        with self.assertRaises(ValueError):
            await self.client.execute("get")
        self.router._beta_ui = True
        self.router.rows = [{"name": "bad"}]
        with self.assertRaises(ValueError):
            await self.client.execute("get")


if __name__ == "__main__":
    unittest.main()
