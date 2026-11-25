"""Offline login, backoff and reauthentication regression tests."""

import ast
import asyncio
import __future__
import json
from pathlib import Path
from types import SimpleNamespace as S
import unittest
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from multidict import CIMultiDict


ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components/iptime_manager"


class ConfigEntryAuthFailed(Exception):
    pass


# Summary: Run production API code with HTTP and HA dependencies isolated.
# Related files: custom_components/iptime_manager/api.py, config_flow.py, coordinator.py.
def load_api():
    namespace = {
        "__name__": "offline_api",
        "ConfigEntryAuthFailed": ConfigEntryAuthFailed,
        "DHCPReservations": lambda api: S(),
        "PortForwardRules": lambda api: S(),
    }
    constants = ast.parse((COMPONENT / "const.py").read_text(encoding="utf-8"))
    for node in constants.body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    namespace[target.id] = value
    tree = ast.parse((COMPONENT / "api.py").read_text(encoding="utf-8"))
    tree.body = [
        node for node in tree.body
        if not isinstance(node, ast.ImportFrom)
        or (node.level == 0 and not (node.module or "").startswith("homeassistant"))
    ]
    exec(compile(tree, "api.py", "exec"), namespace)
    return namespace


API_NAMESPACE = load_api()
IPTimeAPI = API_NAMESPACE["IPTimeAPI"]
RouterConnectionError = API_NAMESPACE["RouterConnectionError"]


class Response:
    def __init__(self, payload=None, *, status=200, text=None, cookie=False):
        self.status = status
        self.body = json.dumps(payload) if text is None else text
        self.cookies = {"efm_session_id": S(value="synthetic-session")} if cookie else {}
        self.headers = CIMultiDict()

    async def __aenter__(self):
        await asyncio.sleep(0)
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self):
        return self.body

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientError("Synthetic HTTP failure")


class Session:
    closed = False

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    async def close(self):
        self.closed = True


def router(*responses, beta=True, logged_in=False):
    api = IPTimeAPI(None, "http://router.invalid", "synthetic-user", "synthetic-input")
    api._session = Session(*responses)
    api._ui_detected = True
    api._beta_ui = beta
    if logged_in:
        api.efm_session_id = "previous-synthetic-session"
    return api


class LoginTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_login_stops_polling_and_action_retries(self):
        api = router(Response({"error": {"code": -32000, "message": "Invalid credentials"}}))
        with self.assertRaises(ConfigEntryAuthFailed):
            await api._async_ensure_login()
        for action in (api.async_update, lambda: api._async_service_json("led/config")):
            with self.assertRaises(ConfigEntryAuthFailed):
                await action()
        self.assertEqual(len(api._session.calls), 1)

    async def test_concurrent_rejected_logins_make_one_request(self):
        api = router(Response({"result": "fail"}))
        results = await asyncio.gather(
            *(api._async_ensure_login() for _ in range(5)), return_exceptions=True
        )
        self.assertTrue(all(isinstance(result, ConfigEntryAuthFailed) for result in results))
        self.assertEqual(len(api._session.calls), 1)

    async def test_concurrent_successful_logins_share_session(self):
        api = router(Response({"result": "done"}, cookie=True))
        await asyncio.gather(*(api._async_ensure_login() for _ in range(5)))
        self.assertIsNotNone(api.efm_session_id)
        self.assertEqual(len(api._session.calls), 1)

    async def test_network_failures_back_off_and_cap_at_five_minutes(self):
        api = router(*(aiohttp.ClientConnectionError() for _ in range(7)))
        with patch.object(API_NAMESPACE["time"], "monotonic") as clock:
            clock.return_value = 1000.0
            for delay in (15, 30, 60, 120, 240, 300, 300):
                with self.assertRaises(aiohttp.ClientError):
                    await api._async_ensure_login()
                self.assertEqual(api._retry_delay, delay)
                requests = len(api._session.calls)
                with self.assertRaises(RouterConnectionError):
                    await api._async_ensure_login()
                self.assertEqual(len(api._session.calls), requests)
                clock.return_value = api._retry_at
        self.assertFalse(api._auth_failed)
        api.reset_retry_delay()
        self.assertEqual((api._retry_at, api._retry_delay), (0, 0))

    async def test_empty_or_malformed_rpc_does_not_reauthenticate(self):
        for response in (Response({}), Response(text=""), Response(text="<html>unavailable</html>")):
            api = router(response, logged_in=True)
            with self.subTest(body=response.body):
                with self.assertRaises(RouterConnectionError):
                    await api._async_service_json("led/config")
                self.assertEqual(len(api._session.calls), 1)
                self.assertFalse(api._auth_failed)
                self.assertGreater(api._retry_delay, 0)

    async def test_invalid_parameters_do_not_trigger_login(self):
        payload = {"error": {"code": -32602, "message": "Invalid parameters"}}
        api = router(Response(payload), logged_in=True)
        self.assertEqual(await api._async_service_json("led/config"), payload)
        self.assertEqual(len(api._session.calls), 1)

    async def test_expired_session_recovers_once(self):
        for expired in (
            Response({"error": {"message": "Invalid session"}}),
            Response(status=401),
        ):
            api = router(expired, Response({"result": "done"}, cookie=True),
                         Response({"result": []}), logged_in=True)
            self.assertEqual(await api._async_service_json("clients"), {"result": []})
            self.assertEqual(len(api._session.calls), 3)

    async def test_failed_session_recovery_latches_auth_failure(self):
        api = router(Response(status=403), Response({"result": "fail"}), logged_in=True)
        with self.assertRaises(ConfigEntryAuthFailed):
            await api._async_service_json("clients")
        with self.assertRaises(ConfigEntryAuthFailed):
            await api._async_service_json("clients")
        self.assertEqual(len(api._session.calls), 2)

    async def test_concurrent_session_recovery_logs_in_only_once(self):
        api = router(
            *(Response(status=401) for _ in range(5)),
            Response({"result": "done"}, cookie=True),
            *(Response({"result": []}) for _ in range(5)),
            logged_in=True,
        )
        results = await asyncio.gather(
            *(api._async_service_json("clients") for _ in range(5))
        )
        self.assertEqual(results, [{"result": []}] * 5)
        methods = [call[2]["json"]["method"] for call in api._session.calls]
        self.assertEqual(methods.count("session/login"), 1)

    async def test_concurrent_session_recovery_rejection_stops_every_caller(self):
        api = router(*(Response(status=401) for _ in range(5)),
                     Response({"result": "fail"}), logged_in=True)
        results = await asyncio.gather(
            *(api._async_service_json("clients") for _ in range(5)), return_exceptions=True
        )
        self.assertTrue(all(isinstance(result, ConfigEntryAuthFailed) for result in results))
        self.assertEqual(len(api._session.calls), 6)

    async def test_new_session_still_rejected_stops_after_one_login(self):
        api = router(Response(status=401), Response({"result": "done"}, cookie=True),
                     Response(status=401), logged_in=True)
        with self.assertRaises(ConfigEntryAuthFailed):
            await api._async_service_json("clients")
        self.assertEqual(len(api._session.calls), 3)

    async def test_obsolete_session_cannot_cause_duplicate_recovery(self):
        api = router(Response({"result": "done"}, cookie=True))
        await api._async_ensure_login()
        await api._async_ensure_login(expired_session="older-synthetic-session")
        self.assertEqual(len(api._session.calls), 1)

    async def test_unrecognized_login_or_missing_cookie_is_connection_failure(self):
        for payload in ({}, {"result": "done"}, {"result": {"unexpected": True}}):
            api = router(Response(payload))
            with self.assertRaises(RouterConnectionError):
                await api._async_ensure_login()
            self.assertFalse(api._auth_failed)
            self.assertGreater(api._retry_delay, 0)

    async def test_legacy_and_mobile_login_rejection_stops_retries(self):
        for mobile in (False, True):
            api = router(Response(text='<form><input name="passwd"></form>'), beta=False)
            api._ismobile = mobile
            with self.assertRaises(ConfigEntryAuthFailed):
                await api._async_ensure_login()
            with self.assertRaises(ConfigEntryAuthFailed):
                await api._async_ensure_login()
            self.assertEqual(len(api._session.calls), 1)

    async def test_legacy_session_cookie_and_named_assignment(self):
        for response in (
            Response(text="", cookie=True),
            Response(text="setCookie('efm_session_id', 'synthetic-session');"),
            Response(text="setCookie('abcdefghijklmnop');"),
        ):
            api = router(response, beta=False)
            await api._async_ensure_login()
            self.assertIsNotNone(api.efm_session_id)

    async def test_legacy_fallback_only_attempts_two_endpoints(self):
        api = router(Response(status=404), Response(text="", cookie=True), beta=False)
        await api._async_ensure_login()
        self.assertEqual(len(api._session.calls), 2)

    async def test_arbitrary_sixteen_character_text_is_not_a_session(self):
        api = router(Response(text="abcdefghijklmnop"), Response(text="unrecognized"), beta=False)
        with self.assertRaises(RouterConnectionError):
            await api._async_ensure_login()
        self.assertIsNone(api.efm_session_id)

    async def test_ui_detection_network_failure_never_submits_credentials(self):
        api = router(aiohttp.ClientConnectionError())
        api._ui_detected = False
        with self.assertRaises(aiohttp.ClientError):
            await api._async_ensure_login()
        self.assertEqual([call[0] for call in api._session.calls], ["GET"])

    async def test_legacy_session_expiry_is_not_an_empty_client_list(self):
        for text in (
            '<form><input name="passwd"></form>',
            "window.location.href='/login/login.cgi';",
            "top.location.replace('/m_login.cgi');",
        ):
            api = router(Response(text=text), beta=False, logged_in=True)
            with self.assertRaises(RouterConnectionError):
                await api._async_request("GET", api._url + "/clients")
            self.assertIsNone(api.efm_session_id)
            self.assertFalse(api._auth_failed)
            self.assertGreater(api._retry_delay, 0)

    async def test_empty_connected_device_list_is_valid(self):
        api = router(Response({"result": []}), logged_in=True)
        self.assertEqual(await api.beta_ui_wlan_check(), {"session": True})

    async def test_successful_poll_keeps_session_without_another_login(self):
        api = router(Response({"result": {"active": False}}),
                     Response({"result": []}), Response({"result": "done"}), logged_in=True)
        with patch.object(API_NAMESPACE["asyncio"], "sleep", new=AsyncMock()):
            self.assertTrue(await api.async_update())
        methods = [call[2]["json"]["method"] for call in api._session.calls]
        self.assertEqual(methods, ["easymesh/info", "network/interface/lan/stations", "session/update"])

    async def test_transport_error_in_authenticated_rpc_defers_polling(self):
        api = router(aiohttp.ClientConnectionError(), logged_in=True)
        with self.assertRaises(aiohttp.ClientError):
            await api._async_service_json("led/config")
        with self.assertRaises(RouterConnectionError):
            await api.async_update()
        self.assertEqual(len(api._session.calls), 1)


def flow_namespace():
    tree = ast.parse((COMPONENT / "config_flow.py").read_text(encoding="utf-8"))
    flow = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "IPTimeConfigFlow")
    flow.bases = []
    flow.keywords = []
    namespace = {
        "IPTimeAPI": Mock(), "ConfigEntryAuthFailed": ConfigEntryAuthFailed,
        "aiohttp": aiohttp, "_LOGGER": Mock(), "CONF_URL": "url",
        "callback": lambda function: function,
        "CONF_ID": "id", "CONF_PASSWORD": "password",
        "vol": __import__("voluptuous"),
        "selector": S(TextSelector=lambda config: str, TextSelectorConfig=lambda **kw: kw,
                      TextSelectorType=S(PASSWORD="password")),
    }
    exec(compile(ast.Module(body=[flow], type_ignores=[]), "config_flow.py", "exec",
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace


class ReauthTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_always_closes_and_classifies_errors(self):
        ns = flow_namespace()
        for failure, expected in (
            (ConfigEntryAuthFailed(), "invalid_auth"),
            (aiohttp.ClientConnectionError(), "cannot_connect"),
            (TimeoutError(), "cannot_connect"), (RuntimeError(), "unknown"), (None, None),
        ):
            api = S(async_update=AsyncMock(return_value=True, side_effect=failure),
                    async_close=AsyncMock())
            ns["IPTimeAPI"].return_value = api
            flow = ns["IPTimeConfigFlow"]()
            flow.hass = S()
            result = await flow._async_validate_credentials(
                {"url": "router.invalid", "id": "synthetic", "password": "synthetic"}
            )
            self.assertEqual(result, expected)
            api.async_close.assert_awaited_once()

    async def test_reauth_updates_only_credentials_after_validation(self):
        ns = flow_namespace()
        flow = ns["IPTimeConfigFlow"]()
        entry = S(data={"url": "router.invalid", "devices": {"synthetic": "label"},
                        "id": "old-synthetic", "password": "old-synthetic"})
        flow._get_reauth_entry = Mock(return_value=entry)
        flow._async_validate_credentials = AsyncMock(return_value=None)
        flow.async_update_reload_and_abort = Mock(return_value={"type": "abort"})
        credentials = {"id": "new-synthetic", "password": "new-synthetic"}
        await flow.async_step_reauth_confirm(credentials)
        flow._async_validate_credentials.assert_awaited_once_with({**entry.data, **credentials})
        flow.async_update_reload_and_abort.assert_called_once_with(entry, data_updates=credentials)
        self.assertEqual(entry.data["id"], "old-synthetic")

    async def test_failed_reauth_preserves_entry_and_asks_again(self):
        ns = flow_namespace()
        flow = ns["IPTimeConfigFlow"]()
        entry = S(data={"url": "router.invalid", "id": "synthetic"})
        flow._get_reauth_entry = Mock(return_value=entry)
        flow._async_validate_credentials = AsyncMock(return_value="invalid_auth")
        flow.async_update_reload_and_abort = Mock()
        flow.async_show_form = Mock(return_value={"type": "form"})
        await flow.async_step_reauth_confirm({"id": "synthetic", "password": "synthetic"})
        flow.async_update_reload_and_abort.assert_not_called()
        self.assertEqual(flow.async_show_form.call_args.kwargs["errors"], {"base": "invalid_auth"})
        self.assertEqual(entry.data, {"url": "router.invalid", "id": "synthetic"})

    async def test_reauth_entry_point_opens_confirmation(self):
        flow = flow_namespace()["IPTimeConfigFlow"]()
        flow.async_step_reauth_confirm = AsyncMock(return_value={"type": "form"})
        self.assertEqual(await flow.async_step_reauth({}), {"type": "form"})
        flow.async_step_reauth_confirm.assert_awaited_once_with()


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_error_escapes_but_network_error_has_retry_delay(self):
        tree = ast.parse((COMPONENT / "coordinator.py").read_text(encoding="utf-8"))
        coordinator_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "IPTimeDataUpdateCoordinator"
        )
        method = next(
            node for node in coordinator_class.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_async_update_data"
        )

        class UpdateFailed(Exception):
            def __init__(self, message, *, retry_after):
                self.retry_after = retry_after

        ns = {
            "ConfigEntryAuthFailed": ConfigEntryAuthFailed, "UpdateFailed": UpdateFailed,
            "CONF_RSSI_LIMIT": "rssi_limit", "DEFAULT_RSSI_LIMIT": -81,
            "monotonic": lambda: 100.0,
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), "coordinator.py", "exec",
                     flags=__future__.annotations.compiler_flag), ns)
        for failure in (ConfigEntryAuthFailed(), aiohttp.ClientConnectionError()):
            api = S(async_update=AsyncMock(side_effect=failure), _retry_at=130.0)
            coordinator = S(api=api, entry=S(options={}, data={}))
            if isinstance(failure, ConfigEntryAuthFailed):
                with self.assertRaises(ConfigEntryAuthFailed):
                    await ns["_async_update_data"](coordinator)
            else:
                with self.assertRaises(UpdateFailed) as caught:
                    await ns["_async_update_data"](coordinator)
                self.assertEqual(caught.exception.retry_after, 30)

    async def test_failed_first_refresh_closes_private_session(self):
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        setup = next(
            node for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_setup_entry"
        )
        api = S(async_close=AsyncMock())
        coordinator = S(
            async_config_entry_first_refresh=AsyncMock(side_effect=ConfigEntryAuthFailed())
        )
        ns = {
            "DOMAIN": "iptime_manager", "CONF_URL": "url", "CONF_ID": "id",
            "CONF_PASSWORD": "password", "is_presence_list_entry": lambda data: False,
            "_LOGGER": Mock(), "IPTimeAPI": Mock(return_value=api),
            "IPTimeDataUpdateCoordinator": Mock(return_value=coordinator),
        }
        exec(compile(ast.Module(body=[setup], type_ignores=[]), "__init__.py", "exec",
                     flags=__future__.annotations.compiler_flag), ns)
        entry = S(data={"url": "router.invalid", "id": "synthetic", "password": "synthetic"})
        with self.assertRaises(ConfigEntryAuthFailed):
            await ns["async_setup_entry"](S(data={}), entry)
        api.async_close.assert_awaited_once()
