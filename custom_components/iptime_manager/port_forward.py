"""Validated beta UI port forwarding rules."""

import asyncio
import logging
from ipaddress import IPv4Address, IPv4Network

_LOGGER = logging.getLogger(__name__)


# Summary: Validate rule identities, port conflicts and LAN targets before RPC writes.
# Related files: api.py, services.py, services.yaml, tests/test_port_forward.py.
def port_range(start, end=None):
    if type(start) is not int or not 1 <= start <= 65535:
        raise ValueError("Ports must be integers between 1 and 65535")
    if end is None or end == -1:
        end = start
    if type(end) is not int or not start <= end <= 65535:
        raise ValueError("Port range end must be between its start and 65535")
    return start, end


# Summary: Accept integral selector values without truncating fractional ports.
# Related files: services.py, services.yaml, tests/test_port_forward.py.
def port_number(value):
    if isinstance(value, bool):
        raise ValueError("Ports must be integers between 1 and 65535")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise ValueError("Ports must be integers between 1 and 65535") from err
    if isinstance(value, float) and value != number:
        raise ValueError("Fractional ports are not supported")
    if isinstance(value, str) and not value.isdecimal():
        raise ValueError("Ports must contain only digits")
    port_range(number)
    return number


class PortForwardRules:
    def __init__(self, api):
        self.api = api
        self.lock = asyncio.Lock()

    async def request(self, method, params=None):
        if not self.api._beta_ui:
            raise ValueError("Port forwarding actions require the router's beta UI")
        response = await self.api._async_service_json(method, params)
        if not isinstance(response, dict) or response.get("error") is not None or response.get("result") is None:
            raise ValueError("Router port forwarding request failed")
        return response["result"]

    async def read(self, kind="user"):
        rows = await self.request("portforward/get", kind)
        if not isinstance(rows, list):
            raise ValueError("Invalid port forwarding list response")
        names = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"] or type(row.get("active")) is not bool:
                raise ValueError("Invalid port forwarding rule response")
            if row["name"] in names:
                raise ValueError("Router returned ambiguous rule names")
            names.add(row["name"])
        return rows

    async def execute(self, operation, **values):
        if operation not in ("get", "add", "update", "delete"):
            raise ValueError("Unknown port forwarding operation")
        async with self.lock:
            rows = await self.read()
            if operation == "get":
                return {"rules": rows, "upnp_rules": await self.read("upnp")}
            current = values.get("name", "")
            if not isinstance(current, str) or not current.strip():
                raise ValueError("A non-empty rule name is required")
            existing = next((row for row in rows if row["name"] == current), None)
            if operation == "add" and existing:
                raise ValueError("This rule name already exists")
            if operation in ("update", "delete") and existing is None:
                raise ValueError("No rule exists with this name")
            if existing and existing.get("fixed"):
                raise ValueError("Fixed router rules cannot be changed by this action")
            if operation == "delete":
                await self.request("portforward/del", {"type": "user", "list": [current]})
                name = current
                payload = None
            else:
                name = values.get("new_name", current)
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("A non-empty rule name is required")
                if any(row["name"] == name and row is not existing for row in rows):
                    raise ValueError("This rule name already exists")
                active = values.get("active", existing["active"] if existing else True)
                if type(active) is not bool:
                    raise ValueError("Rule activation must be a boolean")
                payload = {"active": active}
                if operation == "add":
                    payload["name"] = name
                else:
                    payload["current"] = current
                    if name != current:
                        payload["name"] = name
                mapping_fields = ("protocol", "internal_ip", "external_port_start", "external_port_end", "internal_port_start", "internal_port_end")
                if not active and any(field in values for field in mapping_fields):
                    raise ValueError("Disable using only name and active=false; mapping edits require an active rule")
                if active:
                    old = existing or {}
                    protocol = values.get("protocol", old.get("protocol"))
                    if protocol not in ("tcp", "udp", "tcpudp"):
                        raise ValueError("Choose tcp, udp or tcpudp; GRE mapping edits are unsupported")
                    target = str(IPv4Address(values.get("internal_ip", old.get("target", ""))))
                    info = await self.request("network/interface/lan/info")
                    if not isinstance(info, dict) or not info.get("ip") or not info.get("mask"):
                        raise ValueError("Cannot validate the router LAN subnet")
                    network = IPv4Network(f"{info['ip']}/{info['mask']}", strict=False)
                    address = IPv4Address(target)
                    if address not in network or address in (network.network_address, network.broadcast_address, IPv4Address(info["ip"])) or address.is_multicast or address.is_unspecified:
                        raise ValueError("Target must be a usable LAN address other than the router IP")
                    ranges = {}
                    for prefix, key in (("external", "src"), ("internal", "dst")):
                        previous = old.get(key) or {}
                        start = values.get(f"{prefix}_port_start", previous.get("start"))
                        end = values.get(f"{prefix}_port_end", None if f"{prefix}_port_start" in values else previous.get("end"))
                        ranges[key] = port_range(start, end)
                    if ranges["src"][1] - ranges["src"][0] != ranges["dst"][1] - ranges["dst"][0]:
                        raise ValueError("External and internal port ranges must have equal lengths")
                    protocols = {"tcp", "udp"} if protocol == "tcpudp" else {protocol}
                    for row in rows + await self.read("upnp"):
                        if row is existing or not row["active"]:
                            continue
                        other_protocol = row.get("protocol")
                        if other_protocol == "gre":
                            continue
                        if other_protocol not in ("tcp", "udp", "tcpudp"):
                            raise ValueError("Cannot validate an unknown existing rule protocol")
                        other = {"tcp", "udp"} if other_protocol == "tcpudp" else {other_protocol}
                        if protocols & other:
                            source = row.get("src")
                            if not isinstance(source, dict):
                                raise ValueError("Cannot validate an existing external port range")
                            start, end = port_range(source.get("start"), source.get("end"))
                            if ranges["src"][0] <= end and start <= ranges["src"][1]:
                                raise ValueError("External ports overlap an active user or UPnP rule")
                    payload.update({"protocol": protocol, "target": target})
                    for key, (start, end) in ranges.items():
                        payload[key] = {"start": start}
                        if end != start:
                            payload[key]["end"] = end
                await self.request("portforward/add" if operation == "add" else "portforward/set", payload)
            updated = await self.read()
            result = next((row for row in updated if row["name"] == name), None)
            verified = result is None if operation == "delete" else result is not None and result["active"] == payload["active"]
            if verified and payload and payload["active"]:
                verified = result.get("protocol") == payload["protocol"] and result.get("target") == payload["target"]
                for key in ("src", "dst"):
                    actual = result.get(key) or {}
                    verified = verified and port_range(actual.get("start"), actual.get("end")) == port_range(payload[key]["start"], payload[key].get("end"))
            if verified and operation == "update" and name != current:
                verified = all(row["name"] != current for row in updated)
            if not verified:
                raise ValueError("Could not verify the port forwarding change; query rules before retrying")
            _LOGGER.info("Port forwarding %s verified", operation)
            return {"rules": updated}
