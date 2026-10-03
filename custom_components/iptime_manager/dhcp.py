"""Validated DHCP reservations for the router's beta UI."""

import asyncio
from ipaddress import IPv4Address, IPv4Network
import re


# Summary: Serialize reservation changes and reject conflicts before router writes.
# Related files: api.py, services.py, services.yaml.
def normalize_mac(value):
    compact = re.sub(r"[:-]", "", value)
    if not re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        raise ValueError("Invalid MAC address")
    if int(compact[:2], 16) & 1 or int(compact, 16) == 0:
        raise ValueError("A unicast device MAC address is required")
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2)).upper()


class DHCPReservations:
    def __init__(self, api):
        self.api = api
        self.lock = asyncio.Lock()

    async def request(self, method, params=None):
        if not self.api._beta_ui:
            raise ValueError("DHCP actions require the router's beta UI")
        response = await self.api._async_service_json(method, params)
        if not isinstance(response, dict) or response.get("error") is not None or response.get("result") is None:
            raise ValueError("Router DHCP request failed")
        return response["result"]

    async def read(self):
        result = await self.request("dhcpd/reservedaddr/show", "lan")
        if not isinstance(result, list):
            raise ValueError("Invalid DHCP reservation response")
        rows = []
        for row in result:
            if not isinstance(row, dict):
                raise ValueError("Invalid DHCP reservation item")
            rows.append({"mac": normalize_mac(row.get("mac", "")),
                         "ip": str(IPv4Address(row.get("ip", ""))),
                         "description": row.get("desc") or ""})
        return rows

    async def execute(self, operation, mac=None, ip=None, description=None):
        async with self.lock:
            rows = await self.read()
            if operation == "get":
                return {"reservations": rows}
            mac = normalize_mac(mac)
            existing = next((row for row in rows if row["mac"] == mac), None)
            if operation == "add" and existing:
                raise ValueError("This MAC already has a DHCP reservation; use update")
            if operation in ("update", "delete") and existing is None:
                raise ValueError("No DHCP reservation exists for this MAC")
            if operation == "delete":
                await self.request("dhcpd/reservedaddr/del", {"ntag": "lan", "mac": [mac]})
            else:
                ip = str(IPv4Address(ip))
                if any(row["ip"] == ip and row["mac"] != mac for row in rows):
                    raise ValueError("This IP is reserved for another MAC")
                info = await self.request("network/interface/lan/info")
                if not isinstance(info, dict) or not info.get("ip") or not info.get("mask"):
                    raise ValueError("Cannot validate the router LAN subnet")
                network = IPv4Network(f"{info['ip']}/{info['mask']}", strict=False)
                address = IPv4Address(ip)
                if address not in network or address in (network.network_address, network.broadcast_address, IPv4Address(info["ip"])) or address.is_multicast or address.is_unspecified:
                    raise ValueError("IP must be a usable LAN address other than the router IP")
                stations = await self.request("network/interface/lan/stations")
                if not isinstance(stations, list):
                    raise ValueError("Cannot check connected device IP conflicts")
                for station in stations:
                    if not isinstance(station, dict) or not isinstance(station.get("info"), dict):
                        raise ValueError("Invalid connected device response")
                    if station["info"].get("ip") == ip and normalize_mac(station.get("mac", "")) != mac:
                        raise ValueError("This IP is used by another connected device")
                if description is None:
                    description = existing["description"] if existing else ""
                await self.request("dhcpd/reservedaddr/add", {"ntag": "lan", "mac": mac, "ip": ip, "desc": description})
            updated = await self.read()
            current = next((row for row in updated if row["mac"] == mac), None)
            if operation == "delete":
                verified = current is None
            else:
                verified = current is not None and current["ip"] == ip and current["description"] == description
            if not verified:
                raise ValueError("Could not verify the DHCP change; query reservations before retrying")
            return {"reservations": updated}
