"""Async client for the KlikAanKlikUit ICS-2000.

Protocol details follow ics-2000-python (zefanjajobse/ics_2000_python):
- the Trust cloud API gives the home's MAC + AES key, the device list and the
  current device statuses;
- commands are AES-CBC encrypted JSON frames sent to the hub over UDP port
  2012 on the LAN, with the cloud command endpoint as fallback.
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import logging
import socket
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import API_URL, HUB_PORT

_LOGGER = logging.getLogger(__name__)

_MAGIC = 653213
REPEAT_DELAY = 0.6  # seconds between repeated LAN sends
_DISCOVERY_FRAME = bytes.fromhex(
    "010003ffffffffffffca000000010400044795000401040004000400040000000000000000020000003000"
)


class Ics2000Error(Exception):
    """Generic ICS-2000 error."""


class Ics2000AuthError(Ics2000Error):
    """Wrong e-mail address or password."""


class Ics2000ConnectionError(Ics2000Error):
    """Cloud or hub not reachable."""


# --------------------------------------------------------------------- crypto
def decrypt(data: str, aes_key: str) -> str:
    raw = base64.b64decode(data)
    iv, body = raw[:16], raw[16:]
    dec = Cipher(algorithms.AES(bytes.fromhex(aes_key)), modes.CBC(iv)).decryptor()
    padded = dec.update(body) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode()


def encrypt(data: str, aes_key: str) -> bytes:
    """Encrypt like the KAKU app: zero IV, IV prepended to the ciphertext."""
    iv = bytes(16)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data.encode()) + padder.finalize()
    enc = Cipher(algorithms.AES(bytes.fromhex(aes_key)), modes.CBC(iv)).encryptor()
    return iv + enc.update(padded) + enc.finalize()


def build_command(mac: str, aes_key: str, device_id: int, function: int, value: int) -> bytes:
    """Build the UDP frame that sets one function of one module."""
    payload = encrypt(
        json.dumps({"module": {"id": device_id, "function": function, "value": value}}),
        aes_key,
    )
    header = bytearray(43)
    header[0] = 1
    header[2] = 128
    header[3:9] = bytes.fromhex(mac)
    header[9:13] = _MAGIC.to_bytes(4, "little")
    header[29:33] = device_id.to_bytes(4, "little")
    header[41:43] = len(payload).to_bytes(2, "little")
    return bytes(header) + payload


def normalize_mac(mac: str) -> str:
    return mac.replace(":", "").replace("-", "").lower()


# ---------------------------------------------------------------------- model
@dataclass(slots=True)
class Home:
    home_id: str
    name: str
    mac: str
    aes_key: str


@dataclass(slots=True)
class Module:
    device_id: int
    name: str
    device_type: int
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


# --------------------------------------------------------------------- client
class Ics2000Client:
    """Talks to the Trust cloud API and to the hub on the LAN."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        *,
        home_id: str | None = None,
        mac: str | None = None,
        aes_key: str | None = None,
        host: str | None = None,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self.home_id = home_id
        self.mac = normalize_mac(mac) if mac else None
        self.aes_key = aes_key
        self.host = host
        self._repeats: dict[tuple[int, int], asyncio.Task[None]] = {}

    # ------------------------------------------------------------- cloud API
    async def _post(self, path: str, data: dict[str, str]) -> Any:
        try:
            async with self._session.post(
                f"{API_URL}/{path}", data=data, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 401:
                    raise Ics2000AuthError("invalid credentials")
                if resp.status != 200:
                    raise Ics2000ConnectionError(f"{path}: HTTP {resp.status}")
                text = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise Ics2000ConnectionError(f"{path}: {err}") from err
        try:
            return json.loads(text) if text else None
        except ValueError as err:
            raise Ics2000ConnectionError(f"{path}: invalid JSON") from err

    async def login(self) -> list[Home]:
        data = await self._post(
            "account.php",
            {
                "action": "login",
                "email": self._email,
                "password_hash": self._password,
                "device_unique_id": "android",
                "platform": "",
                "mac": "",
            },
        )
        if not isinstance(data, dict) or not data.get("homes"):
            raise Ics2000AuthError("login returned no homes")
        return [
            Home(
                home_id=str(h["home_id"]),
                name=h.get("home_name") or "ICS-2000",
                mac=normalize_mac(h["mac"]),
                aes_key=h["aes_key"],
            )
            for h in data["homes"]
            if h.get("mac") and h.get("aes_key")
        ]

    def use_home(self, home: Home) -> None:
        self.home_id, self.mac, self.aes_key = home.home_id, home.mac, home.aes_key

    def _auth(self) -> dict[str, str]:
        if not (self.mac and self.aes_key):
            raise Ics2000Error("no home selected")
        return {"email": self._email, "mac": self.mac, "password_hash": self._password}

    async def get_modules(self) -> list[Module]:
        """All modules (devices) of the home. Groups and scenes are skipped."""
        rows = await self._post(
            "gateway.php", {"action": "sync", "home_id": self.home_id or "", **self._auth()}
        )
        if not isinstance(rows, list):
            raise Ics2000ConnectionError("sync returned no device list")
        modules: list[Module] = []
        for row in rows:
            try:
                data = json.loads(decrypt(row["data"], self.aes_key))
            except Exception:  # noqa: BLE001 - malformed rows are skipped
                continue
            mod = data.get("module")
            if not isinstance(mod, dict) or "id" not in mod or "device" not in mod:
                continue
            if not any(i > 0 for i in mod.get("info", []) or []):
                continue  # empty / deleted slot
            modules.append(
                Module(
                    device_id=int(mod["id"]),
                    name=str(mod.get("name") or f"KAKU {mod['id']}"),
                    device_type=int(mod["device"]),
                    raw=mod,
                )
            )
        return modules

    async def get_statuses(self, device_ids: list[int]) -> dict[int, list[int]]:
        """Current function values per module, as stored by the hub in the cloud."""
        if not device_ids:
            return {}
        rows = await self._post(
            "entity.php",
            {"action": "get-multiple", "home_id": "", "entity_id": json.dumps(device_ids), **self._auth()},
        )
        result: dict[int, list[int]] = {}
        for row in rows if isinstance(rows, list) else []:
            try:
                status = json.loads(decrypt(row["status"], self.aes_key))
            except Exception:  # noqa: BLE001
                continue
            section = status.get("module") or status.get("group") or {}
            if isinstance(section.get("functions"), list):
                result[int(row["id"])] = section["functions"]
        return result

    # --------------------------------------------------------------- commands
    async def set_function(self, device_id: int, function: int, value: int, tries: int = 1) -> None:
        """Send a command and return immediately.

        The hub executes LAN commands but never answers them, so we don't wait
        for a reply. Extra ``tries`` are re-sent in the background a little
        later (433 MHz RF is lossy; repeating an on/off/dim is harmless).
        Without a LAN address, or if the LAN send itself fails, the cloud is used.
        """
        frame = build_command(self.mac, self.aes_key, device_id, function, value)
        if self.host:
            try:
                self._send_udp(frame)
            except OSError as err:
                _LOGGER.debug("LAN send to %s failed, using cloud: %s", self.host, err)
            else:
                if tries > 1:
                    self._schedule_repeats(device_id, function, frame, tries - 1)
                return
        await self._send_cloud(frame)

    def _schedule_repeats(self, device_id: int, function: int, frame: bytes, count: int) -> None:
        key = (device_id, function)
        if (old := self._repeats.pop(key, None)) is not None:
            old.cancel()  # a newer command for the same function wins

        async def _repeat() -> None:
            try:
                for _ in range(count):
                    await asyncio.sleep(REPEAT_DELAY)
                    try:
                        self._send_udp(frame)
                    except OSError:
                        return
            finally:
                if self._repeats.get(key) is task:
                    del self._repeats[key]

        task = asyncio.get_running_loop().create_task(_repeat())
        self._repeats[key] = task

    def _send_udp(self, frame: bytes) -> None:
        """Fire-and-forget UDP datagram to the hub (non-blocking)."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setblocking(False)
            sock.sendto(frame, (self.host, HUB_PORT))

    async def _send_cloud(self, frame: bytes) -> None:
        params = {**self._auth(), "action": "add", "device_unique_id": "", "command": frame.hex()}
        try:
            async with self._session.get(
                f"{API_URL}/command.php", params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    raise Ics2000ConnectionError(f"cloud command: HTTP {resp.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise Ics2000ConnectionError(f"cloud command: {err}") from err


# ------------------------------------------------------------------ discovery
async def discover_hubs(timeout: float = 3.0, extra_targets: list[str] | None = None) -> dict[str, str]:
    """Find ICS-2000 hubs; returns {mac: ip}.

    The hub doesn't always answer broadcasts (seen over Wi-Fi), so besides the
    broadcast we also send the discovery frame to every address in
    ``extra_targets`` (normally all hosts of the local subnets).
    """
    loop = asyncio.get_running_loop()
    found: dict[str, str] = {}

    class _Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data: bytes, addr: Any) -> None:
            if len(data) >= 9 and data[0] == 2:
                found[data[3:9].hex()] = addr[0]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)
    sock.bind(("0.0.0.0", 0))
    transport, _ = await loop.create_datagram_endpoint(_Proto, sock=sock)
    try:
        for target in ["255.255.255.255", *(extra_targets or [])]:
            try:
                transport.sendto(_DISCOVERY_FRAME, (target, HUB_PORT))
            except OSError:
                pass
        await asyncio.sleep(timeout)
    finally:
        transport.close()
    return found


def subnet_hosts(networks: list[str], limit: int = 1024) -> list[str]:
    """All host addresses of the given IPv4 networks (skipping huge ones)."""
    hosts: list[str] = []
    for net in networks:
        try:
            n = ipaddress.ip_network(net, strict=False)
        except ValueError:
            continue
        if n.version == 4 and n.num_addresses <= limit:
            hosts.extend(str(h) for h in n.hosts())
    return hosts


__all__ = [
    "Home", "Module", "Ics2000Client", "Ics2000Error", "Ics2000AuthError",
    "Ics2000ConnectionError", "discover_hubs", "normalize_mac", "build_command",
    "encrypt", "decrypt", "subnet_hosts",
]
