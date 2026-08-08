"""Minimal GB/T 28181 SIP registration service.

This module owns SIP registration, Keepalive and Catalog messages. Media remains
owned by ZLMediaKit, which receives GB28181 PS-RTP after a SIP INVITE flow is
added for a specific device integration.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from db import replace_gb28181_channels, touch_gb28181_device, upsert_gb28181_device


_DEVICE_ID_PATTERN = re.compile(r"sip:([0-9A-Za-z_.-]+)@", re.IGNORECASE)
_DIGEST_PATTERN = re.compile(r'([A-Za-z]+)=(?:"([^"]*)"|([^,\s]+))')


def _env_flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _header(message: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}\s*:\s*(.+)$", message, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _sip_user(value: str) -> str:
    match = _DEVICE_ID_PATTERN.search(value)
    return match.group(1) if match else ""


def _digest_values(value: str) -> dict[str, str]:
    return {key.lower(): quoted or plain or "" for key, quoted, plain in _DIGEST_PATTERN.findall(value)}


def _xml_text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    return node.text.strip() if node is not None and node.text else ""


@dataclass
class Gb28181Device:
    device_id: str
    address: tuple[str, int]
    expires_at: float
    last_seen_at: float
    channels: list[dict[str, str]] = field(default_factory=list)
    keepalive_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "address": {"host": self.address[0], "port": self.address[1]},
            "online": self.expires_at > time.time(),
            "last_seen_at": int(self.last_seen_at),
            "channels": self.channels,
            "keepalive_count": self.keepalive_count,
        }


class Gb28181Server(asyncio.DatagramProtocol):
    """A standards-focused GB28181 SIP registrar for the initial device flow."""

    def __init__(self) -> None:
        self.enabled = _env_flag("STREAMUI_GB28181_ENABLED")
        self.host = os.getenv("STREAMUI_GB28181_HOST", "0.0.0.0")
        self.port = int(os.getenv("STREAMUI_GB28181_SIP_PORT", "5060"))
        self.server_id = os.getenv("STREAMUI_GB28181_SERVER_ID", "34020000002000000001")
        self.realm = os.getenv("STREAMUI_GB28181_REALM", self.server_id)
        self.password = os.getenv("STREAMUI_GB28181_PASSWORD", "")
        self.transport: asyncio.DatagramTransport | None = None
        self.devices: dict[str, Gb28181Device] = {}
        self.nonces: dict[str, str] = {}
        self.play_sessions: dict[str, dict[str, str | int]] = {}

    async def start(self) -> None:
        if not self.enabled or self.transport:
            return
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(lambda: self, local_addr=(self.host, self.port))
        self.transport = transport

    async def stop(self) -> None:
        if self.transport:
            self.transport.close()
            self.transport = None
        self.devices.clear()
        self.nonces.clear()
        self.play_sessions.clear()

    async def configure(self, values: dict[str, Any]) -> None:
        current = {"enabled": self.enabled, "host": self.host, "port": self.port, "server_id": self.server_id, "realm": self.realm, "password": self.password}
        requested = {"enabled": bool(values["enabled"]), "host": str(values["host"]), "port": int(values["port"]), "server_id": str(values["server_id"]), "realm": str(values["realm"]), "password": str(values["password"])}
        if requested == current:
            return
        was_listening = self.transport is not None
        if was_listening:
            await self.stop()
        for key, value in requested.items():
            setattr(self, key, value)
        try:
            await self.start()
        except Exception:
            for key, value in current.items():
                setattr(self, key, value)
            if was_listening:
                await self.start()
            raise

    def connection_lost(self, exc: Exception | None) -> None:
        self.transport = None

    def datagram_received(self, data: bytes, address: tuple[str, int]) -> None:
        try:
            message = data.decode("utf-8", errors="replace")
            self._handle_message(message, address)
        except Exception:
            # A malformed device packet must never terminate the SIP listener.
            return

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "listening": self.transport is not None,
            "host": self.host,
            "port": self.port,
            "server_id": self.server_id,
            "realm": self.realm,
            "password_set": bool(self.password),
            "devices": [item.as_dict() for item in self.devices.values()],
        }

    def invite_play(self, *, device_id: str, channel_id: str, media_host: str, media_port: int, stream_id: str) -> dict[str, str | int]:
        if not self.transport:
            raise RuntimeError("GB28181 SIP 服务未监听")
        device = self.devices.get(device_id)
        if not device or device.expires_at <= time.time():
            raise ValueError("国标设备未注册或已离线")
        call_id = f"gb-{secrets.token_hex(12)}"
        tag = secrets.token_hex(6)
        branch = f"z9hG4bK{secrets.token_hex(10)}"
        uri = f"sip:{channel_id}@{device.address[0]}:{device.address[1]}"
        sdp = "\r\n".join([
            "v=0",
            f"o={self.server_id} 0 0 IN IP4 {media_host}",
            "s=StreamUI GB28181",
            f"c=IN IP4 {media_host}",
            "t=0 0",
            f"m=video {media_port} RTP/AVP 96",
            "a=recvonly",
            "a=rtpmap:96 PS/90000",
            "",
        ])
        request = "\r\n".join([
            f"INVITE {uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {media_host}:{self.port};branch={branch}",
            "Max-Forwards: 70",
            f"From: <sip:{self.server_id}@{media_host}>;tag={tag}",
            f"To: <sip:{channel_id}@{device.address[0]}>",
            f"Call-ID: {call_id}",
            "CSeq: 1 INVITE",
            f"Contact: <sip:{self.server_id}@{media_host}:{self.port}>",
            "Content-Type: application/sdp",
            f"Content-Length: {len(sdp.encode())}",
            "",
            sdp,
        ])
        self.transport.sendto(request.encode(), device.address)
        session = {"call_id": call_id, "device_id": device_id, "channel_id": channel_id, "stream_id": stream_id, "media_host": media_host, "media_port": media_port, "state": "inviting", "to": ""}
        self.play_sessions[call_id] = session
        return session

    def bye_play(self, call_id: str) -> bool:
        if not self.transport or call_id not in self.play_sessions:
            return False
        session = self.play_sessions[call_id]
        device = self.devices.get(str(session["device_id"]))
        if not device:
            return False
        media_host = str(session["media_host"])
        request = "\r\n".join([
            f"BYE sip:{session['channel_id']}@{device.address[0]}:{device.address[1]} SIP/2.0",
            f"Via: SIP/2.0/UDP {media_host}:{self.port};branch=z9hG4bK{secrets.token_hex(10)}",
            f"From: <sip:{self.server_id}@{media_host}>;tag=streamui",
            f"To: <sip:{session['channel_id']}@{device.address[0]}>",
            f"Call-ID: {call_id}",
            "CSeq: 2 BYE",
            "Content-Length: 0",
            "",
            "",
        ])
        self.transport.sendto(request.encode(), device.address)
        session["state"] = "stopping"
        return True

    def query_device(self, *, device_id: str, command: str, sender_host: str) -> bool:
        if not self.transport:
            raise RuntimeError("GB28181 SIP 服务未监听")
        device = self.devices.get(device_id)
        if not device or device.expires_at <= time.time():
            raise ValueError("国标设备未注册或已离线")
        command = command.strip()
        if command not in {"DeviceInfo", "DeviceStatus", "Catalog"}:
            raise ValueError("不支持的国标查询命令")
        media_host = sender_host.strip()
        if not media_host:
            raise ValueError("请先配置 RTP 媒体地址")
        branch = f"z9hG4bK{secrets.token_hex(10)}"
        call_id = f"query-{secrets.token_hex(10)}"
        body = f'<?xml version="1.0" encoding="GB2312"?><Query><CmdType>{command}</CmdType><SN>1</SN><DeviceID>{device_id}</DeviceID></Query>'
        request = "\r\n".join([
            f"MESSAGE sip:{device_id}@{device.address[0]}:{device.address[1]} SIP/2.0",
            f"Via: SIP/2.0/UDP {media_host}:{self.port};branch={branch}",
            f"From: <sip:{self.server_id}@{media_host}>;tag={secrets.token_hex(6)}",
            f"To: <sip:{device_id}@{device.address[0]}>",
            f"Call-ID: {call_id}",
            "CSeq: 1 MESSAGE",
            f"Content-Type: Application/MANSCDP+xml; charset=GB2312",
            f"Content-Length: {len(body.encode())}",
            "",
            body,
        ])
        self.transport.sendto(request.encode(), device.address)
        return True

    def _handle_message(self, message: str, address: tuple[str, int]) -> None:
        first_line = message.split("\r\n", 1)[0].strip()
        if not first_line:
            return
        if first_line.startswith("SIP/2.0"):
            self._handle_response(message, address)
            return
        method = first_line.split(" ", 1)[0].upper()
        if method == "REGISTER":
            self._handle_register(message, address)
        elif method in {"MESSAGE", "NOTIFY"}:
            self._handle_message_or_notify(message, address)
        elif method == "OPTIONS":
            self._reply(message, address, 200, "OK")

    def _handle_response(self, response: str, address: tuple[str, int]) -> None:
        status_match = re.match(r"SIP/2\.0\s+(\d{3})", response)
        if not status_match:
            return
        call_id = _header(response, "Call-ID")
        session = self.play_sessions.get(call_id)
        if not session:
            return
        status = int(status_match.group(1))
        cseq = _header(response, "CSeq").upper()
        if cseq.endswith("INVITE"):
            if 200 <= status < 300:
                self._send_ack(response, address, session)
                session["state"] = "active"
                session["to"] = _header(response, "To")
            elif status >= 300:
                session["state"] = "failed"
        elif cseq.endswith("BYE") and 200 <= status < 300:
            self.play_sessions.pop(call_id, None)

    def _send_ack(self, response: str, address: tuple[str, int], session: dict[str, str | int]) -> None:
        if not self.transport:
            return
        media_host = str(session["media_host"])
        channel_id = str(session["channel_id"])
        request = "\r\n".join([
            f"ACK sip:{channel_id}@{address[0]}:{address[1]} SIP/2.0",
            f"Via: SIP/2.0/UDP {media_host}:{self.port};branch=z9hG4bK{secrets.token_hex(10)}",
            f"From: {_header(response, 'From')}",
            f"To: {_header(response, 'To')}",
            f"Call-ID: {session['call_id']}",
            "CSeq: 1 ACK",
            "Content-Length: 0",
            "",
            "",
        ])
        self.transport.sendto(request.encode(), address)

    def _handle_register(self, message: str, address: tuple[str, int]) -> None:
        device_id = _sip_user(_header(message, "From")) or _sip_user(_header(message, "To"))
        if not device_id:
            self._reply(message, address, 400, "Bad Request")
            return
        authorization = _digest_values(_header(message, "Authorization"))
        nonce = self.nonces.get(device_id)
        if self.password and not self._verify_digest(authorization, nonce, "REGISTER"):
            nonce = secrets.token_hex(16)
            self.nonces[device_id] = nonce
            self._reply(message, address, 401, "Unauthorized", extra=f'Digest realm="{self.realm}", nonce="{nonce}", algorithm=MD5')
            return
        expires = _header(message, "Expires")
        try:
            expires_seconds = max(30, min(int(expires or "3600"), 86400))
        except ValueError:
            expires_seconds = 3600
        now = time.time()
        self.devices[device_id] = Gb28181Device(device_id=device_id, address=address, expires_at=now + expires_seconds, last_seen_at=now)
        upsert_gb28181_device(device_id=device_id, address=address[0], sip_port=address[1], expires_seconds=expires_seconds)
        self._reply(message, address, 200, "OK", expires=expires_seconds)

    def _verify_digest(self, values: dict[str, str], nonce: str | None, method: str) -> bool:
        if not nonce or values.get("username") is None or values.get("nonce") != nonce:
            return False
        uri = values.get("uri", "")
        response = values.get("response", "")
        if not uri or not response:
            return False
        ha1 = hashlib.md5(f"{values['username']}:{self.realm}:{self.password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        expected = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        return secrets.compare_digest(expected, response)

    def _handle_message_or_notify(self, message: str, address: tuple[str, int]) -> None:
        device_id = _sip_user(_header(message, "From")) or _sip_user(_header(message, "To"))
        if device_id and device_id in self.devices:
            device = self.devices[device_id]
            device.address = address
            device.last_seen_at = time.time()
            device.expires_at = max(device.expires_at, device.last_seen_at + 90)
            command = self._consume_xml(device, message.partition("\r\n\r\n")[2])
            touch_gb28181_device(device_id=device_id, address=address[0], sip_port=address[1], keepalive=command == "keepalive")
        self._reply(message, address, 200, "OK")

    def _consume_xml(self, device: Gb28181Device, body: str) -> str:
        try:
            root = ET.fromstring(body.strip())
        except ET.ParseError:
            return ""
        command = _xml_text(root, ".//CmdType").lower()
        if command == "keepalive":
            device.keepalive_count += 1
        elif command == "catalog":
            channels: list[dict[str, str]] = []
            for item in root.findall(".//Item"):
                channel_id = _xml_text(item, "DeviceID")
                if channel_id:
                    channels.append({"channel_id": channel_id, "name": _xml_text(item, "Name"), "status": _xml_text(item, "Status") or "ON"})
            if channels:
                device.channels = channels
                replace_gb28181_channels(device_id=device.device_id, channels=channels)
        return command

    def _reply(self, request: str, address: tuple[str, int], code: int, reason: str, *, extra: str = "", expires: int | None = None) -> None:
        if not self.transport:
            return
        to_value = _header(request, "To")
        if "tag=" not in to_value:
            to_value = f"{to_value};tag={secrets.token_hex(6)}"
        lines = [
            f"SIP/2.0 {code} {reason}",
            f"Via: {_header(request, 'Via')}",
            f"From: {_header(request, 'From')}",
            f"To: {to_value}",
            f"Call-ID: {_header(request, 'Call-ID')}",
            f"CSeq: {_header(request, 'CSeq')}",
            f"Date: {time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())}",
        ]
        if expires is not None:
            lines.append(f"Expires: {expires}")
        if extra:
            lines.append(f"WWW-Authenticate: {extra}")
        lines.extend(["Content-Length: 0", "", ""])
        self.transport.sendto("\r\n".join(lines).encode(), address)
