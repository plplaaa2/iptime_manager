"""Offline authorization tests without router access or an HA installation."""

import ast
import asyncio
import __future__
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock


ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components/iptime_manager"


class Unauthorized(Exception):
    def __init__(self, *, context):
        self.context = context


class UnknownUser(Unauthorized):
    pass


# Summary: Execute the production authorization boundary with isolated HA dependencies.
# Related files: custom_components/iptime_manager/admin.py, button.py, number.py, select.py, switch.py.
def load_function(node, namespace):
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, "<authorization test>", "exec",
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace[node.name]


namespace = {"wraps": wraps, "Unauthorized": Unauthorized, "UnknownUser": UnknownUser}
admin_tree = ast.parse((COMPONENT / "admin.py").read_text(encoding="utf-8"))
require_admin = load_function(
    next(node for node in admin_tree.body if isinstance(node, ast.FunctionDef)),
    namespace,
)


def entity_for(user_id, user):
    return SimpleNamespace(
        _context=SimpleNamespace(user_id=user_id),
        hass=SimpleNamespace(auth=SimpleNamespace(async_get_user=AsyncMock(return_value=user))),
    )


class AdminAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_receives_result_and_arguments(self):
        action = AsyncMock(return_value={"ok": True})
        entity = entity_for("admin", SimpleNamespace(is_admin=True))
        result = await require_admin(action)(entity, 5, enabled=True)
        self.assertEqual(result, {"ok": True})
        action.assert_awaited_once_with(entity, 5, enabled=True)

    async def test_non_admin_cannot_reach_action(self):
        action = AsyncMock()
        entity = entity_for("member", SimpleNamespace(is_admin=False))
        with self.assertRaises(Unauthorized):
            await require_admin(action)(entity)
        action.assert_not_awaited()

    async def test_deleted_user_cannot_reach_action(self):
        action = AsyncMock()
        with self.assertRaises(UnknownUser):
            await require_admin(action)(entity_for("deleted", None))
        action.assert_not_awaited()

    async def test_internal_automation_needs_no_user_lookup(self):
        action = AsyncMock(return_value=True)
        entity = entity_for(None, None)
        self.assertTrue(await require_admin(action)(entity))
        entity.hass.auth.async_get_user.assert_not_awaited()

    async def test_direct_internal_call_without_context(self):
        action = AsyncMock(return_value=True)
        entity = entity_for(None, None)
        entity._context = None
        self.assertTrue(await require_admin(action)(entity))
        entity.hass.auth.async_get_user.assert_not_awaited()

    async def test_admin_reboot_reaches_existing_router_api(self):
        tree = ast.parse((COMPONENT / "button.py").read_text(encoding="utf-8"))
        entity_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "IPTimeRebootButton"
        )
        method = next(
            node for node in entity_class.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_press"
        )
        press = load_function(method, {"require_admin": require_admin})
        entity = entity_for("admin", SimpleNamespace(is_admin=True))
        reboot = AsyncMock()
        entity.coordinator = SimpleNamespace(api=SimpleNamespace(async_reboot=reboot))
        await press(entity)
        reboot.assert_awaited_once_with()

    async def test_permission_lookup_error_blocks_action(self):
        action = AsyncMock()
        entity = entity_for("member", None)
        entity.hass.auth.async_get_user.side_effect = RuntimeError("Auth unavailable")
        with self.assertRaises(RuntimeError):
            await require_admin(action)(entity)
        action.assert_not_awaited()

    async def test_concurrent_call_cannot_replace_checked_user(self):
        action = AsyncMock()
        entity = entity_for("member", None)
        original_context = entity._context

        async def lookup(user_id):
            entity._context = SimpleNamespace(user_id="admin")
            await asyncio.sleep(0)
            return SimpleNamespace(is_admin=False)

        entity.hass.auth.async_get_user.side_effect = lookup
        with self.assertRaises(Unauthorized) as caught:
            await require_admin(action)(entity)
        self.assertIs(caught.exception.context, original_context)
        action.assert_not_awaited()

    async def test_all_sensitive_entity_methods_reject_non_admins(self):
        counts = {}
        for filename in ("button.py", "number.py", "select.py", "switch.py"):
            tree = ast.parse((COMPONENT / filename).read_text(encoding="utf-8"))
            count = 0
            for entity_class in (node for node in tree.body if isinstance(node, ast.ClassDef)):
                for method in entity_class.body:
                    if not isinstance(method, ast.AsyncFunctionDef):
                        continue
                    if method.name not in (
                        "async_press", "async_set_native_value", "async_select_option",
                        "async_turn_on", "async_turn_off",
                    ):
                        continue
                    protected = any(
                        isinstance(node, ast.Name) and node.id == "require_admin"
                        for node in method.decorator_list
                    )
                    if entity_class.name == "IPTimeNightLEDSelect":
                        self.assertFalse(protected)
                        continue
                    with self.subTest(entity=entity_class.name, method=method.name):
                        self.assertTrue(protected)
                        function = load_function(method, {"require_admin": require_admin})
                        arguments = ["test"] if len(method.args.args) > 1 else []
                        for user in (None, SimpleNamespace(is_admin=False)):
                            entity = entity_for("unprivileged", user)
                            with self.assertRaises(Unauthorized):
                                await function(entity, *arguments)
                    count += 1
            counts[filename] = count
        self.assertEqual(counts, {"button.py": 1, "number.py": 2, "select.py": 3, "switch.py": 30})
