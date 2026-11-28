"""Offline tests for preserving router settings during control operations."""

import ast
import asyncio
import copy
import __future__
from pathlib import Path
from types import SimpleNamespace as S
import unittest
from unittest.mock import AsyncMock

import aiohttp
from test_auth import ConfigEntryAuthFailed, HomeAssistantError, IPTimeAPI


# Summary: Cover every read/modify/write operation with non-default retained values.
# Related files: api.py, select.py, switch.py, dhcp.py.
def setting_cases():
    return [
        {
            "name": "wireguard", "call": ("async_set_web_wg_server_run", (True,), {}),
            "reads": {"wg/server/show": {"active": False, "address": "10.55.1.1/24", "port": 51880, "nat": False}},
            "write": ("wg/server/set", {"active": True, "address": "10.55.1.1/24", "port": 51880, "nat": False, "commit": True}),
            "required": [("wg/server/show", (key,)) for key in ("address", "port", "nat")],
        },
        {
            "name": "led", "call": ("async_set_web_led_config", ("off",), {}),
            "reads": {"led/config": {"mode": "schedule", "on": 0, "off": 7}},
            "write": ("led/config", {"mode": "off", "on": 0, "off": 7, "commit": True}),
            "required": [("led/config", (key,)) for key in ("on", "off")],
        },
        {
            "name": "reboot toggle", "call": ("async_set_web_reboot_timer", (True,), {}),
            "reads": {"reboot/timer": {"run": False, "hour": 0, "min": 17, "days": ["Tue", "Thu"]}},
            "write": ("reboot/timer", {"run": True, "hour": 0, "min": 17, "days": ["Tue", "Thu"]}),
            "required": [("reboot/timer", (key,)) for key in ("hour", "min", "days")],
        },
        {
            "name": "reboot day", "call": ("async_set_web_reboot_timer", (None,), {"days": ["Sun"]}),
            "reads": {"reboot/timer": {"run": False, "hour": 21, "min": 0, "days": ["Tue"]}},
            "write": ("reboot/timer", {"run": False, "hour": 21, "min": 0, "days": ["Sun"]}),
            "required": [("reboot/timer", (key,)) for key in ("run", "hour", "min")],
        },
        {
            "name": "wan", "call": ("async_set_web_wan_heartbeat", (True,), {}),
            "reads": {"wan/heartbeat": {"run": False, "interval": 0}},
            "write": ("wan/heartbeat", {"run": True, "interval": 0}),
            "required": [("wan/heartbeat", ("interval",))],
        },
        {
            "name": "arp", "call": ("async_set_security_switch", ("arp_virus", True), {}),
            "reads": {"dos/config": {"arp_virus": {"run": False, "pps": 0}}},
            "write": ("dos/config", {"arp_virus": {"run": True, "pps": 0}}),
            "required": [("dos/config", ("arp_virus", "pps"))],
        },
        {
            "name": "density toggle", "call": ("async_set_easymesh_density_control", (True,), {}),
            "reads": {"easymesh/config": {"global": {"density_control": {"enable": False, "rssi": -63}}}},
            "write": ("easymesh/config", {"global": {"density_control": {"enable": True, "rssi": -63}}}),
            "required": [("easymesh/config", ("global", "density_control", "rssi"))],
        },
        {
            "name": "density rssi", "call": ("async_set_easymesh_density_rssi", (-61,), {}),
            "reads": {"easymesh/config": {"global": {"density_control": {"enable": False, "rssi": -63}}}},
            "write": ("easymesh/config", {"global": {"density_control": {"enable": False, "rssi": -61}}}),
            "required": [("easymesh/config", ("global", "density_control", "enable"))],
        },
        {
            "name": "remote management", "call": ("async_set_web_accesslist_enable", (False,), {}),
            "reads": {"acl/config": [{"ntag": "wan1", "open": {"flag": True, "port": 8443}}]},
            "write": ("acl/config", {"ntag": "wan1", "open": {"flag": False, "port": 8443}}),
            "required": [("acl/config", (0, "open", "port"))],
        },
        {
            "name": "wifi channel", "call": ("async_set_wireless_channel", ("5g", "48"), {}),
            "reads": {"wireless/band/show": [{"band": "5g", "enable": False, "channel": "149"}],
                      "wireless/band/info": [{"band": "5g"}]},
            "write": ("wireless/band/set", {"band": "5g", "channel": "48", "enable": False, "commit": True}),
            "required": [("wireless/band/show", (0, "enable"))],
        },
    ]


class RPC:
    def __init__(self, reads):
        self.reads = copy.deepcopy(reads)
        self.calls = []
        self.writes = []
        self.error = None

    async def __call__(self, method, params=None):
        await asyncio.sleep(0)
        self.calls.append((method, copy.deepcopy(params)))
        if params is None:
            if self.error is not None:
                return self.error
            return {"result": copy.deepcopy(self.reads[method])}
        self.writes.append((method, copy.deepcopy(params)))
        return {"result": "done"}


def make_router(reads):
    api = IPTimeAPI(None, "router.invalid", "synthetic", "synthetic")
    api._beta_ui = True
    api.web_result = {"easymesh": {"info": {"active": True, "role": "controller"}}}
    rpc = RPC(reads)
    api._async_service_json = rpc
    return api, rpc


async def invoke(api, case):
    method, args, kwargs = case["call"]
    return await getattr(api, method)(*args, **kwargs)


class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_controls_preserve_fresh_router_values(self):
        for case in setting_cases():
            with self.subTest(control=case["name"]):
                api, rpc = make_router(case["reads"])
                # Polling cache must never provide values for the write.
                api.web_result.update(wg_server={"ip": "10.0.21.1", "port": 53344, "nat": True},
                                      reboot_timer={"hour": 4}, led_config={"on": 22, "off": 8})
                self.assertTrue(await invoke(api, case))
                self.assertEqual(rpc.writes, [case["write"]])
                self.assertEqual(rpc.calls[-1], case["write"])
                self.assertEqual(api._last_caching_time, 0)

    async def test_missing_null_and_invalid_retained_fields_block_every_write(self):
        for case in setting_cases():
            for method, path in case["required"]:
                for invalid in ("missing", None, "invalid"):
                    with self.subTest(control=case["name"], field=path, invalid=invalid):
                        reads = copy.deepcopy(case["reads"])
                        container = reads[method]
                        for key in path[:-1]:
                            container = container[key]
                        if invalid == "missing":
                            del container[path[-1]]
                        else:
                            container[path[-1]] = invalid
                        api, rpc = make_router(reads)
                        with self.assertRaises(HomeAssistantError):
                            await invoke(api, case)
                        self.assertEqual(rpc.writes, [])

    async def test_failed_and_malformed_fresh_reads_never_write(self):
        for case in setting_cases():
            for response in ({}, {"result": None}, {"error": {"message": "unavailable"}},
                             {"result": "invalid"}):
                with self.subTest(control=case["name"], response=response):
                    api, rpc = make_router(case["reads"])
                    rpc.error = response
                    with self.assertRaises(HomeAssistantError):
                        await invoke(api, case)
                    self.assertEqual(rpc.writes, [])

    async def test_boolean_values_cannot_be_used_as_numbers(self):
        for case in setting_cases():
            for method, path in case["required"]:
                if path[-1] in ("nat", "enable", "run", "address", "days"):
                    continue
                with self.subTest(control=case["name"], field=path):
                    reads = copy.deepcopy(case["reads"])
                    container = reads[method]
                    for key in path[:-1]:
                        container = container[key]
                    container[path[-1]] = False
                    api, rpc = make_router(reads)
                    with self.assertRaises(HomeAssistantError):
                        await invoke(api, case)
                    self.assertEqual(rpc.writes, [])

    async def test_numeric_strings_are_preserved_as_exact_numbers(self):
        api, rpc = make_router({"wg/server/show": {
            "address": "10.66.0.1", "port": "51830", "nat": False,
        }})
        await api.async_set_web_wg_server_run(False)
        self.assertEqual(rpc.writes[0][1]["port"], 51830)

    async def test_read_transport_failure_is_a_clear_error_and_auth_still_propagates(self):
        for failure in (aiohttp.ClientConnectionError(), ConfigEntryAuthFailed()):
            api, _ = make_router({})
            request = AsyncMock(side_effect=failure)
            api._async_service_json = request
            expected = ConfigEntryAuthFailed if isinstance(failure, ConfigEntryAuthFailed) else HomeAssistantError
            with self.assertRaises(expected):
                await api.async_set_web_wg_server_run(True)
            self.assertEqual(request.await_count, 1)

    async def test_supplied_schedule_values_remain_supported(self):
        api, rpc = make_router({"led/config": {}, "reboot/timer": {}})
        await api.async_set_web_led_config("schedule", 23, 6)
        await api.async_set_web_reboot_timer(True, 2, 19, ["Wed"])
        self.assertEqual(rpc.writes, [
            ("led/config", {"mode": "schedule", "on": 23, "off": 6, "commit": True}),
            ("reboot/timer", {"run": True, "hour": 2, "min": 19, "days": ["Wed"]}),
        ])

    async def test_ambiguous_remote_management_entries_are_refused(self):
        api, rpc = make_router({"acl/config": [
            {"ntag": "wan1", "open": {"port": 8443}},
            {"ntag": "wan1", "open": {"port": 8080}},
        ]})
        with self.assertRaises(HomeAssistantError):
            await api.async_set_web_accesslist_enable(True)
        self.assertEqual(rpc.writes, [])

    async def test_sequential_settings_writes_read_the_latest_change(self):
        current = {"run": False, "hour": 2, "min": 13, "days": ["Tue"]}
        calls = []
        api, _ = make_router({})

        async def rpc(method, params=None):
            await asyncio.sleep(0)
            calls.append(copy.deepcopy(params))
            if params is None:
                return {"result": dict(current)}
            current.update(params)
            return {"result": "done"}

        api._async_service_json = rpc
        await asyncio.gather(
            api.async_set_web_reboot_timer(True),
            api.async_set_web_reboot_timer(None, days=["Sun"]),
        )
        self.assertEqual(current, {"run": True, "hour": 2, "min": 13, "days": ["Sun"]})
        self.assertEqual([call is None for call in calls], [True, False, True, False])


# Summary: Exercise entity entry points so cached display values cannot become writes.
# Related files: select.py, switch.py, api.py.
def entity_method(filename, class_name, method_name):
    source = Path(__file__).parents[1] / "custom_components/iptime_manager" / filename
    tree = ast.parse(source.read_text(encoding="utf-8"))
    entity = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in entity.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name)
    method.decorator_list = []
    namespace = {"HomeAssistantError": HomeAssistantError}
    exec(compile(ast.Module(body=[method], type_ignores=[]), filename, "exec",
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace[method_name]


class SettingEntityTests(unittest.IsolatedAsyncioTestCase):
    async def test_entities_send_only_user_selected_changes(self):
        cases = [
            ("switch.py", "IPTimeAutoRebootSwitch", "async_turn_on", (), "async_set_web_reboot_timer", (True,), {}),
            ("switch.py", "IPTimeAutoRebootSwitch", "async_turn_off", (), "async_set_web_reboot_timer", (False,), {}),
            ("switch.py", "IPTimeWanReconnectSwitch", "async_turn_on", (), "async_set_web_wan_heartbeat", (True,), {}),
            ("select.py", "IPTimeNightLEDSelect", "async_select_option", ("Always Off",), "async_set_web_led_config", ("off",), {}),
            ("select.py", "IPTimeRebootDaySelect", "async_select_option", ("Sunday",), "async_set_web_reboot_timer", (None,), {"days": ["Sun"]}),
        ]
        for filename, class_name, method_name, args, api_name, expected, kwargs in cases:
            with self.subTest(entity=class_name, action=method_name):
                target = AsyncMock()
                entity = S(coordinator=S(data={"web": {}}, api=S(**{api_name: target}),
                                         async_request_refresh=AsyncMock()))
                await entity_method(filename, class_name, method_name)(entity, *args)
                target.assert_awaited_once_with(*expected, **kwargs)

    async def test_missing_display_values_are_unknown(self):
        entity = S(coordinator=S(data={"web": {}}))
        self.assertIsNone(entity_method("select.py", "IPTimeNightLEDSelect", "current_option")(entity))
        self.assertIsNone(entity_method("select.py", "IPTimeRebootDaySelect", "current_option")(entity))
        attributes = entity_method("select.py", "IPTimeNightLEDSelect", "extra_state_attributes")(entity)
        self.assertTrue(all(value is None for value in attributes.values()))
        for name in ("IPTimeAutoRebootSwitch", "IPTimeWanReconnectSwitch", "IPTimeWireGuardServerSwitch"):
            self.assertIsNone(entity_method("switch.py", name, "is_on")(entity))

    async def test_invalid_select_option_cannot_send_a_default_change(self):
        source = Path(__file__).parents[1] / "custom_components/iptime_manager/select.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_option_to_policy")
        namespace = {"HomeAssistantError": HomeAssistantError}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "select.py", "exec",
                     flags=__future__.annotations.compiler_flag), namespace)
        with self.assertRaises(HomeAssistantError):
            namespace["_option_to_policy"]("Invalid selection")
        self.assertEqual(namespace["_option_to_policy"]("Country Allow"), (True, "accept"))
