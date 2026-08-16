import os
import re
import shutil
import asyncio
import time
import html
import platform
import socket
import subprocess
import tempfile
import uuid
import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import zipfile
import io
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import httpx
import docker
import psutil
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph as PdfParagraph
from reportlab.platypus import SimpleDocTemplate, Spacer
from starlette.background import BackgroundTask
from db import delete_pull_proxy as db_delete_pull_proxy
from db import delete_record_policy as db_delete_record_policy
from db import BUILTIN_ADMIN_ID
from db import assign_device_to_interview_room as db_assign_device_to_interview_room
from db import create_business_directory as db_create_business_directory
from db import create_interview_area as db_create_interview_area
from db import create_interview_room as db_create_interview_room
from db import create_alarm_event as db_create_alarm_event
from db import create_access_event as db_create_access_event
from db import create_access_point as db_create_access_point
from db import update_access_point as db_update_access_point
from db import create_remote_command as db_create_remote_command
from db import create_organization as db_create_organization
from db import create_personnel as db_create_personnel
from db import delete_business_directory as db_delete_business_directory
from db import delete_interview_area as db_delete_interview_area
from db import delete_interview_room as db_delete_interview_room
from db import delete_alarm_recipient as db_delete_alarm_recipient
from db import delete_access_point as db_delete_access_point
from db import delete_access_permission as db_delete_access_permission
from db import delete_organization as db_delete_organization
from db import delete_personnel as db_delete_personnel
from db import get_record_policy as db_get_record_policy
from db import get_platform_settings as db_get_platform_settings
from db import init_db as db_init
from db import list_pull_proxies as db_list_pull_proxies
from db import list_record_policies as db_list_record_policies
from db import upsert_record_policy as db_upsert_record_policy
from db import upsert_platform_settings as db_upsert_platform_settings
from db import upsert_pull_proxy as db_upsert_pull_proxy
from db import create_user as db_create_user
from db import delete_user as db_delete_user
from db import create_device as db_create_device
from db import delete_device as db_delete_device
from db import device_has_active_case_work as db_device_has_active_case_work
from db import device_has_case_history as db_device_has_case_history
from db import delete_record_schedule as db_delete_record_schedule
from db import get_device as db_get_device
from db import get_device_access_key as db_get_device_access_key
from db import get_business_directory as db_get_business_directory
from db import get_interview_area as db_get_interview_area
from db import get_interview_room as db_get_interview_room
from db import get_alarm_event as db_get_alarm_event
from db import get_organization as db_get_organization
from db import get_personnel as db_get_personnel
from db import get_user as db_get_user
from db import get_video_wall as db_get_video_wall
from db import list_channels as db_list_channels
from db import list_gb28181_devices as db_list_gb28181_devices
from db import list_business_directories as db_list_business_directories
from db import list_devices as db_list_devices
from db import list_interview_areas as db_list_interview_areas
from db import list_interview_room_devices as db_list_interview_room_devices
from db import list_interview_rooms as db_list_interview_rooms
from db import list_alarm_events as db_list_alarm_events
from db import list_alarm_linkage_actions as db_list_alarm_linkage_actions
from db import list_alarm_recipients as db_list_alarm_recipients
from db import list_access_events as db_list_access_events
from db import list_access_permissions as db_list_access_permissions
from db import list_access_points as db_list_access_points
from db import list_remote_commands as db_list_remote_commands
from db import list_organizations as db_list_organizations
from db import list_personnel as db_list_personnel
from db import list_record_schedules as db_list_record_schedules
from db import list_users as db_list_users
from db import mark_stale_devices_offline as db_mark_stale_devices_offline
from db import remove_device_from_interview_room as db_remove_device_from_interview_room
from db import save_video_wall as db_save_video_wall
from db import touch_device as db_touch_device
from db import update_user as db_update_user
from db import update_device as db_update_device
from db import rotate_device_access_key as db_rotate_device_access_key
from db import update_business_directory as db_update_business_directory
from db import update_interview_area as db_update_interview_area
from db import update_interview_room as db_update_interview_room
from db import update_alarm_event_status as db_update_alarm_event_status
from db import update_alarm_linkage_action as db_update_alarm_linkage_action
from db import upsert_alarm_recipient as db_upsert_alarm_recipient
from db import update_access_permission_delivery as db_update_access_permission_delivery
from db import upsert_access_permission as db_upsert_access_permission
from db import acknowledge_remote_command as db_acknowledge_remote_command
from db import cancel_remote_command as db_cancel_remote_command
from db import complete_remote_command as db_complete_remote_command
from db import update_organization as db_update_organization
from db import update_personnel as db_update_personnel
from db import upsert_channel as db_upsert_channel
from db import upsert_device as db_upsert_device
from db import upsert_record_schedule as db_upsert_record_schedule
from db import verify_device_key as db_verify_device_key
from db import create_archive_file as db_create_archive_file
from db import create_archive_folder as db_create_archive_folder
from db import delete_archive_file as db_delete_archive_file
from db import get_archive_file as db_get_archive_file
from db import get_archive_folder as db_get_archive_folder
from db import list_archive_files as db_list_archive_files
from db import list_case_archive_files as db_list_case_archive_files
from db import list_archive_folders as db_list_archive_folders
from db import update_archive_file as db_update_archive_file
from db import assign_case_to_device as db_assign_case_to_device
from db import create_case as db_create_case
from db import delete_case as db_delete_case
from db import get_case as db_get_case
from db import get_case_by_no as db_get_case_by_no
from db import get_case_assignment as db_get_case_assignment
from db import list_case_assignments as db_list_case_assignments
from db import list_cases as db_list_cases
from db import update_case_assignment_status as db_update_case_assignment_status
from db import archive_is_immutable as db_archive_is_immutable
from db import add_case_transcript_version as db_add_case_transcript_version
from db import create_case_media_asset as db_create_case_media_asset
from db import create_case_session as db_create_case_session
from db import reschedule_case_session as db_reschedule_case_session
from db import create_case_transcript as db_create_case_transcript
from db import finalize_case_transcript as db_finalize_case_transcript
from db import get_case_session as db_get_case_session
from db import get_case_transcript as db_get_case_transcript
from db import get_case_transcript_template as db_get_case_transcript_template
from db import list_case_audit_logs as db_list_case_audit_logs
from db import list_case_media_assets as db_list_case_media_assets
from db import list_case_sessions as db_list_case_sessions
from db import list_case_transcripts as db_list_case_transcripts
from db import list_case_transcript_templates as db_list_case_transcript_templates
from db import update_case_session_status as db_update_case_session_status
from db import verify_case_audit_chain as db_verify_case_audit_chain
from db import close_case as db_close_case
from db import archive_case as db_archive_case
from db import get_case_completion_report as db_get_case_completion_report
from db import get_case_workflow_dashboard as db_get_case_workflow_dashboard
from db import log_case_archive_event as db_log_case_archive_event
from db import create_case_recording_binding as db_create_case_recording_binding
from db import list_case_recording_bindings as db_list_case_recording_bindings
from db import create_case_device_command as db_create_case_device_command
from db import claim_due_case_device_commands as db_claim_due_case_device_commands
from db import finish_case_device_command as db_finish_case_device_command
from db import get_case_disc_evidence as db_get_case_disc_evidence
from db import list_case_device_commands as db_list_case_device_commands
from db import upsert_case_disc_evidence as db_upsert_case_disc_evidence
from db import upsert_case_transcript_template as db_upsert_case_transcript_template
from db import complete_case_assignment_if_ready as db_complete_case_assignment_if_ready
from db import save_case_transcript_draft as db_save_case_transcript_draft
from db import create_remote_hearing_task as db_create_remote_hearing_task
from db import get_remote_hearing_task as db_get_remote_hearing_task
from db import list_remote_hearing_tasks as db_list_remote_hearing_tasks
from db import set_remote_hearing_task_state as db_set_remote_hearing_task_state
from db import update_remote_hearing_participant as db_update_remote_hearing_participant
from scheduler import cleanup_old_videos
from tiptap_templates import BUILTIN_TIPTAP_TEMPLATES
from utils import get_video_shanghai_time, get_video_shanghai_time_from_filename, get_zlm_secret, summarize_existing_recordings
from gb28181 import Gb28181Server

# =========================================================
# zlmediakit 地址
# ZLM_SERVER = "http://127.0.0.1:8080"
ZLM_SERVER = os.getenv("ZLM_SERVER", "http://zlm-server:80")
ZLM_RTMP_PUBLISH_URL = os.getenv("ZLM_RTMP_PUBLISH_URL", "").rstrip("/")
REMOTE_HEARING_RTMP_BASE = os.getenv("STREAMUI_REMOTE_HEARING_RTMP_BASE", ZLM_RTMP_PUBLISH_URL).rstrip("/")
# zlmediakit 密钥
ZLM_SECRET = get_zlm_secret(os.getenv("STREAMUI_ZLM_CONF", "/opt/media/conf/config.ini"))
GB28181_SERVER = Gb28181Server()
# zlmediakit 录像
def _resolve_record_root() -> Path:
    configured_root = Path(os.getenv("STREAMUI_RECORD_ROOT", "/opt/media/bin/www/record"))
    candidates = [
        configured_root,
        Path("/opt/hongmsoft/softapp/bin/www/record"),
        Path("/opt/media/bin/www/record"),
    ]
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.rglob("*.mp4")):
            return candidate
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return configured_root


RECORD_ROOT = _resolve_record_root()
ARCHIVE_ROOT = Path(os.getenv("STREAMUI_ARCHIVE_ROOT", str(Path(__file__).resolve().parent / "data" / "device_archives")))
TRANSCRIPT_TEMPLATE_ROOT = ARCHIVE_ROOT / "_transcript_templates"
ONLYOFFICE_DOCUMENT_SERVER_URL = os.getenv("ONLYOFFICE_DOCUMENT_SERVER_URL", "/onlyoffice").rstrip("/")
ONLYOFFICE_PLATFORM_URL = os.getenv("ONLYOFFICE_PLATFORM_URL", "http://streamui-web-server:10800").rstrip("/")
ONLYOFFICE_JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET", "")
ONLYOFFICE_CALLBACK_HOSTS = {item.strip().lower() for item in os.getenv("ONLYOFFICE_CALLBACK_HOSTS", "onlyoffice-document-server").split(",") if item.strip()}
ENABLE_ONLYOFFICE = False
ENABLE_PLATFORM_TIPTAP = False
# 容器
ZLM_CONTAINER_NAME = os.getenv("ZLM_CONTAINER_NAME", "zlm-server")
STREAMUI_CONTAINER_NAME = os.getenv("STREAMUI_CONTAINER_NAME", "streamui-web-server")
# =========================================================

_last_record_start_attempt: dict[tuple[str, str, str], float] = {}
_case_recording_streams: dict[int, list[dict]] = {}
AUTH_SECRET = os.getenv("STREAMUI_AUTH_SECRET") or secrets.token_urlsafe(32)
SESSION_COOKIE = "streamui_session"
DEVICE_STALE_SECONDS = 90
INITIAL_USER_PASSWORD = os.getenv("STREAMUI_INITIAL_USER_PASSWORD", "123456")
LEGACY_INITIAL_USER_PASSWORD = "gv123456"
LM700_AUTH_KEY = os.getenv("STREAMUI_LM700_AUTH_KEY", "6zV?W5j1Mn4+D8w@")
APP_STARTED_AT = datetime.now()
LICENSE_PRODUCT = "GS8000"
LICENSE_SERIAL_PREFIX = "GS8"
LICENSE_FILE = Path(__file__).resolve().parent / "db" / "system_license.json"
LICENSE_PUBLIC_KEY = Path(__file__).resolve().parent / "license_public_key.pem"
MANAGEMENT_GET_PATHS = {
    "/api/playback/start-record",
    "/api/playback/stop-record",
    "/api/playback/event-record",
    "/api/server/restart",
}


def _password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(_password_hash(password, salt), stored)


def _sign_session(username: str, role: str) -> str:
    payload = {"username": username, "role": role, "exp": int(time.time()) + 8 * 3600}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(AUTH_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _read_session(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    expected = hmac.new(AUTH_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        return payload if int(payload["exp"]) >= int(time.time()) else None
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def _request_user(request: Request) -> dict | None:
    session = _read_session(request.cookies.get(SESSION_COOKIE))
    if not session:
        return None
    user = db_get_user(username=str(session.get("username", "")))
    if not user or not user.get("enabled"):
        return None
    return {"id": user["id"], "username": user["username"], "full_name": user["full_name"], "nickname": user["nickname"], "role": user["role"], "must_change_password": bool(user.get("must_change_password"))}


def _is_admin(request: Request) -> bool:
    user = _request_user(request)
    return bool(user and user.get("role") == "admin")


def _machine_feature_code() -> str:
    machine_id = ""
    try:
        machine_id = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    mac_family = getattr(socket, "AF_LINK", getattr(socket, "AF_PACKET", None))
    mac_addresses = sorted(
        address.address for addresses in psutil.net_if_addrs().values()
        for address in addresses
        if getattr(address, "family", None) == mac_family
        and address.address
        and address.address != "00:00:00:00:00:00"
    )
    source = "|".join([machine_id, *mac_addresses]) or f"{socket.gethostname()}|{uuid.getnode():012X}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest().upper()[:16]


def _machine_serial_number() -> str:
    return f"{LICENSE_SERIAL_PREFIX}-{_machine_feature_code()}-0001"


def _license_payload(license_data: dict) -> bytes:
    return (
        f"schema=1\nproduct={license_data['product']}\nfingerprint={license_data['fingerprint']}\n"
        f"license_id={license_data['licenseId']}\nexpires_at={license_data['expiresAt']}\n"
    ).encode("utf-8")


def _license_status() -> tuple[bool, str]:
    if not LICENSE_FILE.exists():
        return False, "未授权"
    try:
        license_data = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        required = {"schema", "product", "fingerprint", "licenseId", "expiresAt", "signature"}
        if not required.issubset(license_data) or license_data["schema"] != 1:
            return False, "授权文件无效"
        if license_data["product"] != LICENSE_PRODUCT or license_data["fingerprint"] != _machine_serial_number():
            return False, "授权不匹配"
        expires_at = str(license_data["expiresAt"])
        if expires_at:
            expiry = datetime.strptime(expires_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc).date() > expiry.date():
                return False, "授权已过期"
        signature = base64.b64decode(str(license_data["signature"]), validate=True)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False, "授权文件无效"

    if not LICENSE_PUBLIC_KEY.is_file():
        return False, "授权公钥缺失"
    try:
        with tempfile.TemporaryDirectory() as directory:
            payload_path = Path(directory) / "payload"
            signature_path = Path(directory) / "signature"
            payload_path.write_bytes(_license_payload(license_data))
            signature_path.write_bytes(signature)
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(LICENSE_PUBLIC_KEY), "-signature", str(signature_path),
                 "-sigopt", "rsa_padding_mode:pss", "-sigopt", "rsa_mgf1_md:sha256",
                 "-sigopt", "rsa_pss_saltlen:digest", str(payload_path)],
                capture_output=True, text=True, timeout=5, check=False,
            )
        if result.returncode != 0:
            return False, "授权签名无效"
    except (OSError, subprocess.SubprocessError):
        return False, "授权验证不可用"
    return True, "已授权" if not expires_at else f"已授权，至 {expires_at}"


def _install_license(license_code: str) -> tuple[bool, str]:
    code = license_code.strip()
    if code.startswith("LIC1:"):
        try:
            code = base64.b64decode(code[5:], validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False, "授权码编码无效"
    if not code or len(code) > 8192:
        return False, "授权码长度无效"
    try:
        license_data = json.loads(code)
    except json.JSONDecodeError:
        return False, "授权码内容无效"
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = LICENSE_FILE.with_suffix(".tmp")
    try:
        temporary_path.write_text(json.dumps(license_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temporary_path.replace(LICENSE_FILE)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        return False, "授权文件保存失败"
    licensed, status = _license_status()
    if licensed:
        return True, status
    LICENSE_FILE.unlink(missing_ok=True)
    return False, status


def _can_manage(request: Request) -> bool:
    user = _request_user(request)
    return bool(user and user.get("role") in {"admin", "operator"})


def _public_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "full_name": user.get("full_name"),
        "nickname": user.get("nickname"),
        "role": user.get("role"),
        "enabled": bool(user.get("enabled")),
        "must_change_password": bool(user.get("must_change_password")),
        "bound_mac": user.get("bound_mac", ""),
        "bound_ip": user.get("bound_ip", ""),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }


def _valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def _valid_device_web_url(value: object) -> str | None:
    if value is None or not str(value).strip():
        return None
    url = str(value).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def _is_within_schedule(now: datetime, weekdays: str, start_time: str, end_time: str) -> bool:
    try:
        active_days = {int(day) for day in weekdays.split(",")}
    except ValueError:
        return False
    current = now.hour * 60 + now.minute
    start_hour, start_minute = map(int, start_time.split(":"))
    end_hour, end_minute = map(int, end_time.split(":"))
    start = start_hour * 60 + start_minute
    end = end_hour * 60 + end_minute
    today = now.weekday()
    if start_time <= end_time:
        return today in active_days and start <= current < end
    if current >= start:
        return today in active_days
    return current < end and (today - 1) % 7 in active_days


async def apply_record_schedules() -> None:
    now = datetime.now()
    targets: dict[tuple[str, str, str], dict] = {}
    for schedule in db_list_record_schedules():
        if not schedule.get("enabled") or not schedule.get("app") or not schedule.get("stream"):
            continue
        key = (str(schedule["vhost"]), str(schedule["app"]), str(schedule["stream"]))
        target = targets.setdefault(key, {"desired": False, "retention_days": 0})
        target["desired"] = target["desired"] or _is_within_schedule(now, schedule["weekdays"], schedule["start_time"], schedule["end_time"])
        target["retention_days"] = max(target["retention_days"], int(schedule["retention_days"]))

    for (vhost, app, stream), target in targets.items():
        desired = bool(target["desired"])
        policy = db_get_record_policy(vhost=vhost, app=app, stream=stream)
        active = bool(policy and policy.get("enabled"))
        if desired == active:
            continue
        try:
            action = "startRecord" if desired else "stopRecord"
            params = {"secret": ZLM_SECRET, "vhost": vhost, "app": app, "stream": stream, "type": "1"}
            if desired:
                params["max_second"] = "300"
            response = await client.get(f"{ZLM_SERVER}/index/api/{action}", params=params)
            if response.json().get("code") == 0:
                db_upsert_record_policy(vhost=vhost, app=app, stream=stream, retention_days=int(target["retention_days"]), enabled=desired)
        except Exception:
            continue


async def ensure_recording_from_policies() -> None:
    try:
        policies = db_list_record_policies(enabled_only=True) or []
    except Exception:
        return
    if not policies:
        return

    try:
        response = await client.get(
            f"{ZLM_SERVER}/index/api/getMediaList", params={"secret": ZLM_SECRET}
        )
        raw = response.json()
        if raw.get("code") != 0:
            return
    except Exception:
        return

    media_map: dict[tuple[str, str, str], dict] = {}
    for media in raw.get("data", []) or []:
        if not isinstance(media, dict):
            continue
        vhost = str(media.get("vhost") or "__defaultVhost__")
        app = str(media.get("app") or "")
        stream = str(media.get("stream") or "")
        if not (app and stream):
            continue
        key = (vhost, app, stream)
        agg = media_map.get(key) or {"isRecordingMP4": False}
        if media.get("isRecordingMP4"):
            agg["isRecordingMP4"] = True
        media_map[key] = agg

    now = time.time()
    for policy in policies:
        vhost = str(policy.get("vhost") or "__defaultVhost__")
        app = str(policy.get("app") or "")
        stream = str(policy.get("stream") or "")
        if not (app and stream):
            continue
        key = (vhost, app, stream)
        state = media_map.get(key)
        if not state:
            continue
        if state.get("isRecordingMP4"):
            continue

        last = _last_record_start_attempt.get(key, 0.0)
        if now - last < 60:
            continue
        _last_record_start_attempt[key] = now

        try:
            await client.get(
                f"{ZLM_SERVER}/index/api/startRecord",
                params={
                    "secret": ZLM_SECRET,
                    "vhost": vhost,
                    "app": app,
                    "stream": stream,
                    "type": "1",
                    "max_second": "300",
                },
            )
        except Exception:
            continue


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _onlyoffice_token(payload: dict) -> str:
    if not ONLYOFFICE_JWT_SECRET:
        return ""
    header = _base64url(b'{"alg":"HS256","typ":"JWT"}')
    encoded = _base64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = _base64url(hmac.new(ONLYOFFICE_JWT_SECRET.encode("utf-8"), f"{header}.{encoded}".encode("ascii"), hashlib.sha256).digest())
    return f"{header}.{encoded}.{signature}"


def _verify_onlyoffice_token(token: str) -> dict | None:
    if not ONLYOFFICE_JWT_SECRET or token.count(".") != 2:
        return None
    header, encoded, signature = token.split(".", 2)
    expected = _base64url(hmac.new(ONLYOFFICE_JWT_SECRET.encode("utf-8"), f"{header}.{encoded}".encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None


def _onlyoffice_draft_path(transcript_id: int) -> Path:
    return ARCHIVE_ROOT / "_onlyoffice_drafts" / f"{transcript_id}.docx"


def _onlyoffice_docx_bytes(transcript: dict, content: dict | None = None) -> bytes:
    lines = _tiptap_docx_lines(content) if content else [str(transcript["title"]), f"案件编号：{transcript['case_no']}", f"案件名称：{transcript['case_name']}", f"办案会话：{transcript['session_no']}", f"制作时间：{datetime.now().astimezone().strftime('%Y-%m-%d')}", "", "问：", "答：", "", "以上笔录经核对无误。"]
    paragraphs = "".join(f'<w:p><w:r><w:t xml:space="preserve">{html.escape(line)}</w:t></w:r></w:p>' for line in lines)
    package = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + paragraphs + '<w:sectPr/></w:body></w:document>',
    }
    with tempfile.SpooledTemporaryFile() as output:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in package.items():
                archive.writestr(name, content)
        output.seek(0)
        return output.read()


def _onlyoffice_document_signature(transcript_id: int, expires: int) -> str:
    message = f"onlyoffice-document:{transcript_id}:{expires}".encode("ascii")
    return hmac.new(AUTH_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _onlyoffice_demo_document_signature(expires: int) -> str:
    message = f"onlyoffice-demo-document:{expires}".encode("ascii")
    return hmac.new(AUTH_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _save_onlyoffice_version(transcript: dict, document: bytes, actor: str, note: str) -> dict | None:
    digest = hashlib.sha256(document).hexdigest()
    if digest == str(transcript.get("current_file_hash") or ""):
        return transcript
    next_version = int(transcript["current_version"]) + 1
    original_name = f"{transcript['session_no']}-{transcript['title']}-V{next_version}.docx"[:240]
    stored_name = f"{uuid.uuid4().hex}.docx"
    target = _archive_storage_path(str(transcript["device_id"]), stored_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(document)
    archive = db_create_archive_file(device_id=str(transcript["device_id"]), case_id=int(transcript["case_id"]), session_id=int(transcript["session_id"]), folder_id=None, archive_type="transcript", status="closed", title=str(transcript["title"]), original_name=original_name, stored_name=stored_name, file_size=len(document), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", sha256=digest, uploaded_by=actor)
    saved = db_add_case_transcript_version(transcript_id=int(transcript["id"]), archive_id=int((archive or {})["id"]), content_hash=digest, note=note[:500], created_by=actor) if archive else None
    if not saved:
        target.unlink(missing_ok=True)
    return saved


def _parse_planned_time(value: object) -> str | None:
    if value in (None, ""):
        return None
    try:
        planned = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if planned.tzinfo is None:
        planned = planned.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return planned.astimezone(timezone.utc).isoformat(timespec="seconds")


def _lm700_control_url(address: object) -> str | None:
    raw = str(address or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"{parsed.scheme}://{host}:8070/interface/action"


def _device_command_audit_payload(payload: dict) -> dict:
    audit_payload = json.loads(json.dumps(payload))
    for field in ("authKey", "tokenKey"):
        if field in audit_payload:
            audit_payload[field] = "[redacted]"
    return audit_payload


async def _start_platform_case_recording(session_id: int, device_id: str) -> None:
    channels = [item for item in db_list_channels(device_id=device_id) if item.get("app") and item.get("stream")]
    if not channels:
        return
    try:
        response = await client.get(f"{ZLM_SERVER}/index/api/getMediaList", params={"secret": ZLM_SECRET})
        media = response.json().get("data") or []
    except (httpx.HTTPError, ValueError):
        return
    active = {(str(item.get("vhost") or "__defaultVhost__"), str(item.get("app") or ""), str(item.get("stream") or "")): bool(item.get("isRecordingMP4")) for item in media if isinstance(item, dict)}
    started: list[dict] = []
    for channel in channels:
        key = (str(channel.get("vhost") or "__defaultVhost__"), str(channel["app"]), str(channel["stream"]))
        if active.get(key):
            continue
        try:
            response = await client.get(f"{ZLM_SERVER}/index/api/startRecord", params={"secret": ZLM_SECRET, "vhost": key[0], "app": key[1], "stream": key[2], "type": "1", "max_second": "300"})
            if response.json().get("code") == 0:
                started.append({"vhost": key[0], "app": key[1], "stream": key[2]})
        except (httpx.HTTPError, ValueError):
            continue
    if started:
        _case_recording_streams[session_id] = started


async def _stop_platform_case_recording(session_id: int) -> None:
    for stream in _case_recording_streams.pop(session_id, []):
        try:
            await client.get(f"{ZLM_SERVER}/index/api/stopRecord", params={"secret": ZLM_SECRET, "vhost": stream["vhost"], "app": stream["app"], "stream": stream["stream"], "type": "1"})
        except httpx.HTTPError:
            continue


def _recording_window(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


async def sync_platform_case_recordings() -> None:
    if not RECORD_ROOT.is_dir():
        return
    bindings = db_list_case_recording_bindings()
    bound_paths = {str(item["recording_path"]) for item in bindings}
    bound_sessions = {int(item["session_id"]) for item in bindings}
    for session in db_list_case_sessions():
        if session["status"] != "ended" or int(session["id"]) in bound_sessions:
            continue
        started_at = _recording_window(str(session.get("started_at") or ""))
        ended_at = _recording_window(str(session.get("ended_at") or ""))
        if not started_at or not ended_at:
            continue
        for channel in db_list_channels(device_id=str(session["device_id"])):
            app_name, stream_name = str(channel.get("app") or ""), str(channel.get("stream") or "")
            if not app_name or not stream_name:
                continue
            stream_root = RECORD_ROOT / app_name / stream_name
            if not stream_root.is_dir():
                continue
            local_start = started_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
            local_end = ended_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
            for offset in range((local_end - local_start).days + 1):
                record_dir = stream_root / (local_start + timedelta(days=offset)).isoformat()
                if not record_dir.is_dir():
                    continue
                for file_path in record_dir.glob("*.mp4"):
                    if not file_path.is_file() or time.time() - file_path.stat().st_mtime < 10:
                        continue
                    timing = get_video_shanghai_time_from_filename(file_path) or get_video_shanghai_time(file_path)
                    if not timing:
                        continue
                    file_start = _recording_window(str(timing["start"]))
                    file_end = _recording_window(str(timing["end"]))
                    if not file_start or not file_end or file_end <= started_at or file_start >= ended_at:
                        continue
                    relative = file_path.relative_to(RECORD_ROOT).as_posix()
                    if relative in bound_paths:
                        continue
                    created = db_create_case_recording_binding(session_id=int(session["id"]), app=app_name, stream=stream_name, recording_path=relative, started_at=str(timing["start"]), ended_at=str(timing["end"]), sha256=_file_sha256(file_path), integrity_status="verified", created_by="system:platform-recorder")
                    if created:
                        bound_paths.add(relative)
                        bound_sessions.add(int(session["id"]))
                        break
                if int(session["id"]) in bound_sessions:
                    break


async def _lm700_recording_state(url: str) -> dict[str, bool] | None:
    payload = {
        "restfulApi": "WebAjax",
        "tokenKey": secrets.token_hex(16),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "authKey": LM700_AUTH_KEY,
        "interface": {"action": "serviceRunning", "matcher": "interQuery", "data": {}},
    }
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        values = result.get("returnData") if int(result.get("returnVal", -1)) == 0 else None
        if not isinstance(values, dict):
            return None
        return {
            "recording": int(values.get("recordAction") or 0) not in {0, 6},
            "burning": int(values.get("cdrWorkAction") or 0) not in {0, 5},
        }
    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def _lm700_stop_current_recording(url: str) -> tuple[bool, str]:
    payload = {
        "restfulApi": "WebAjax",
        "tokenKey": secrets.token_hex(16),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "authKey": LM700_AUTH_KEY,
        "interface": {"action": "recordCease", "matcher": "devControl", "data": {}},
    }
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return False, f"停止设备当前录像失败：{error}"
    if int(result.get("returnVal", -1)) != 0:
        message = str((result.get("returnData") or {}).get("errMsg") or result.get("returnMsg") or "设备拒绝停止当前录像")
        return False, f"停止设备当前录像失败：{message}"
    return True, ""


async def _execute_case_device_command(command: dict) -> None:
    session_id = int(command["session_id"])
    action = str(command["action"])
    recording_mode = str(command["recording_mode"])
    expected_status = {"start": "planned", "stop": "active", "verify_begin": "finalizing", "verify_status": "finalizing"}.get(action)
    if expected_status and command.get("session_status") != expected_status:
        db_finish_case_device_command(command_id=int(command["id"]), status="skipped", request_data={}, response_data={}, error_message="会话状态已变化，跳过过期命令")
        return
    device = db_get_device(device_id=str(command["device_id"]))
    url = _lm700_control_url((device or {}).get("address"))
    if not device or not device.get("enabled") or not url:
        db_finish_case_device_command(command_id=int(command["id"]), status="failed", request_data={}, response_data={}, error_message="设备未启用或未配置有效控制地址")
        return
    if action == "start":
        state = await _lm700_recording_state(url)
        if state is None:
            db_finish_case_device_command(command_id=int(command["id"]), status="failed", request_data={}, response_data={}, error_message="无法确认设备录像或刻录状态")
            return
        if state["burning"]:
            db_finish_case_device_command(command_id=int(command["id"]), status="failed", request_data={}, response_data={}, error_message="设备正在进行光盘刻录，不能自动中断后启动办案会话")
            return
        if state["recording"]:
            stopped, message = await _lm700_stop_current_recording(url)
            if not stopped:
                db_finish_case_device_command(command_id=int(command["id"]), status="failed", request_data={}, response_data={}, error_message=message)
                return
            state = await _lm700_recording_state(url)
            if state is None or state["recording"] or state["burning"]:
                db_finish_case_device_command(command_id=int(command["id"]), status="failed", request_data={}, response_data={}, error_message="设备当前录像未停止，不能启动办案会话")
                return
    action_map = {
        "start": "cdrWorkStart" if recording_mode == "sync_burn" else "recordStart",
        "stop": "cdrWorkCease" if recording_mode == "sync_burn" else "recordCease",
        "verify_begin": "discHashCheck",
        "verify_status": "discHashCheck",
    }
    device_action = action_map.get(action)
    if not device_action:
        db_finish_case_device_command(command_id=int(command["id"]), status="failed", request_data={}, response_data={}, error_message="未知设备命令")
        return
    data = {"user_name": "streamui", "sign": str(command["session_no"]), "case_no": str(command["case_no"])} if action == "start" else ({"queryStat": action == "verify_status"} if action.startswith("verify_") else {})
    payload = {"restfulApi": "WebAjax", "tokenKey": secrets.token_hex(16), "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], "authKey": LM700_AUTH_KEY, "interface": {"action": device_action, "matcher": "devControl", "data": data}}
    audit_payload = _device_command_audit_payload(payload)
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as error:
        db_finish_case_device_command(command_id=int(command["id"]), status="failed", request_data=audit_payload, response_data={}, error_message=f"设备请求失败：{error}")
        return
    if int(result.get("returnVal", -1)) != 0:
        message = str((result.get("returnData") or {}).get("errMsg") or result.get("returnMsg") or "设备拒绝执行")
        db_finish_case_device_command(command_id=int(command["id"]), status="failed", request_data=audit_payload, response_data=result, error_message=message)
        return
    db_finish_case_device_command(command_id=int(command["id"]), status="succeeded", request_data=audit_payload, response_data=result)
    if action == "start":
        db_update_case_session_status(session_id=session_id, status="active", actor="system:orchestrator")
        await _start_platform_case_recording(session_id, str(command["device_id"]))
        if recording_mode == "sync_burn":
            db_upsert_case_disc_evidence(session_id=session_id, status="recording", detail={"start_command_id": int(command["id"])})
    elif action == "stop":
        await _stop_platform_case_recording(session_id)
        if recording_mode == "disk":
            db_update_case_session_status(session_id=session_id, status="ended", actor="system:orchestrator")
            db_complete_case_assignment_if_ready(session_id=session_id, actor="system:orchestrator")
        else:
            db_update_case_session_status(session_id=session_id, status="finalizing", actor="system:orchestrator")
            db_upsert_case_disc_evidence(session_id=session_id, status="verifying", detail={"stop_command_id": int(command["id"])})
            db_create_case_device_command(session_id=session_id, action="verify_begin", scheduled_at=_now_iso(), idempotency_key=f"session:{session_id}:verify-begin", created_by="system:orchestrator")
    elif action == "verify_begin":
        db_create_case_device_command(session_id=session_id, action="verify_status", scheduled_at=_now_iso(), idempotency_key=f"session:{session_id}:verify-status:{command['id']}", created_by="system:orchestrator")
    elif action == "verify_status":
        values = result.get("returnData") if isinstance(result.get("returnData"), list) else []
        valid = [item for item in values if isinstance(item, dict) and int(item.get("checkPercent") or 0) >= 100 and item.get("hashValue") and item.get("hashValue") == item.get("checkHash")]
        if valid:
            item = valid[0]
            db_upsert_case_disc_evidence(session_id=session_id, status="verified", drive_name=str(item.get("dummyName") or ""), primary_hash=str(item.get("hashValue") or ""), verified_hash=str(item.get("checkHash") or ""), check_percent=int(item.get("checkPercent") or 100), detail={"device_result": values}, verified=True)
            db_update_case_session_status(session_id=session_id, status="ended", actor="system:orchestrator")
            db_complete_case_assignment_if_ready(session_id=session_id, actor="system:orchestrator")
        else:
            attempts = len([item for item in db_list_case_device_commands(session_id=session_id) if item["action"] == "verify_status"])
            if attempts >= 60:
                db_upsert_case_disc_evidence(session_id=session_id, status="failed", detail={"device_result": values, "reason": "光盘校验超时"})
            else:
                db_upsert_case_disc_evidence(session_id=session_id, status="verifying", check_percent=max([int(item.get("checkPercent") or 0) for item in values if isinstance(item, dict)] or [0]), detail={"device_result": values})
                scheduled = (datetime.now(timezone.utc) + timedelta(seconds=15)).isoformat(timespec="seconds")
                db_create_case_device_command(session_id=session_id, action="verify_status", scheduled_at=scheduled, idempotency_key=f"session:{session_id}:verify-status:{command['id']}", created_by="system:orchestrator")


async def run_due_case_device_commands() -> None:
    for command in db_claim_due_case_device_commands(limit=10):
        await _execute_case_device_command(command)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()

    db_init()
    admin_password = os.getenv("STREAMUI_ADMIN_PASSWORD", INITIAL_USER_PASSWORD)
    admin_user = db_get_user(username="admin")
    if not admin_user:
        db_create_user(username="admin", full_name="管理员", nickname="admin", password_hash=_password_hash(admin_password), role="admin", user_id=BUILTIN_ADMIN_ID)
    elif _verify_password(LEGACY_INITIAL_USER_PASSWORD, str(admin_user.get("password_hash") or "")):
        db_update_user(username="admin", password_hash=_password_hash(admin_password))
    await GB28181_SERVER.configure(_gb28181_settings(include_password=True))
    asyncio.create_task(sync_pull_proxies_from_db())

    # 添加任务：每小时整点执行
    scheduler.add_job(
        cleanup_old_videos,
        kwargs={"path": RECORD_ROOT},
        trigger=CronTrigger(minute=0),
        id="cleanup_videos",
        name="清理旧视频片段",
        replace_existing=True,
    )
    scheduler.add_job(
        ensure_recording_from_policies,
        trigger=IntervalTrigger(seconds=30),
        id="ensure_recording",
        name="保障录像自动续录",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(apply_record_schedules, trigger=IntervalTrigger(seconds=30), id="record_schedules", replace_existing=True, max_instances=1)
    scheduler.add_job(db_mark_stale_devices_offline, kwargs={"stale_seconds": DEVICE_STALE_SECONDS}, trigger=IntervalTrigger(seconds=30), id="device_status", replace_existing=True)
    scheduler.add_job(run_due_case_device_commands, trigger=IntervalTrigger(seconds=10), id="case_orchestration", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(sync_platform_case_recordings, trigger=IntervalTrigger(seconds=15), id="case_recording_bindings", replace_existing=True, max_instances=1, coalesce=True)

    await GB28181_SERVER.start()

    # 只有在这里，事件循环已经启动，可以安全 start
    scheduler.start()
    print("[Scheduler] 🚀 定时任务已启动")

    yield

    scheduler.shutdown()
    await GB28181_SERVER.stop()
    await client.aclose()
    print("[Scheduler] 🛑 定时任务已取消")


t = """
| 端口  | 协议    | 服务                            |
| ----- | ------- | ------------------------------- |
| 10800 | TCP     | 管理平台前端                    |
| 10801 | TCP     | 管理平台后端               |
| 1935  | TCP     | RTMP 推流拉流                   |
| 8080  | TCP     | FLV、HLS、TS、fMP4、WebRTC 支持 |
| 8443  | TCP     | HTTPS、WebSocket 支持           |
| 8554  | TCP     | RTSP 服务端口                   |
| 10000 | TCP/UDP | RTP、RTCP 端口                  |
| 8000  | UDP     | WebRTC ICE/STUN 端口            |
| 9000  | UDP     | WebRTC 辅助端口                 |

"""

app = FastAPI(
    title="接口文档",
    version="latest",
    description=t,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# The frontend is served from the same Nginx origin. Cross-origin clients must be
# explicitly configured instead of allowing credentialed requests from any origin.
cors_origins = [item.strip() for item in os.getenv("STREAMUI_CORS_ORIGINS", "").split(",") if item.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )


client = httpx.AsyncClient(
    timeout=5.0,
    limits=httpx.Limits(
        max_connections=10,
        max_keepalive_connections=20,
    ),
)


@app.middleware("http")
async def require_api_auth(request: Request, call_next):
    path = request.url.path
    public_paths = {"/api/auth/login", "/api/auth/logout", "/api/device/register", "/api/device/heartbeat", "/api/device/alarms", "/api/device/access-events", "/api/archives/upload"}
    device_archive_download = path.startswith("/api/device/archives/") and path.endswith("/download")
    device_case_access = path in {"/api/device/cases", "/api/device/case-history"} or (path.startswith("/api/device/case-assignments/") and path.endswith("/ack"))
    device_template_access = path == "/api/device/transcript-templates" or (path.startswith("/api/device/transcript-templates/") and path.endswith("/download"))
    device_session_access = path == "/api/device/case-sessions" or (path.startswith("/api/device/case-sessions/") and path.endswith("/status"))
    device_command_access = path.startswith("/api/device/case-sessions/") and (path.endswith("/remote-commands") or "/remote-commands/" in path and path.endswith("/ack"))
    device_remote_hearing_access = path == "/api/device/remote-hearing-tasks" or (path.startswith("/api/device/remote-hearing-tasks/") and path.endswith("/status"))
    if path.startswith("/api/") and path not in public_paths and not device_archive_download and not device_case_access and not device_template_access and not device_session_access and not device_command_access and not device_remote_hearing_access:
        user = _request_user(request)
        if not user:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"code": 401, "msg": "请先登录"})
        viewer_self_service = path == "/api/auth/password" or (request.method == "PUT" and path.startswith("/api/users/"))
        if (request.method in {"POST", "PUT", "PATCH", "DELETE"} or path in MANAGEMENT_GET_PATHS) and user.get("role") == "viewer" and not viewer_self_service:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"code": 403, "msg": "查看者没有修改权限"})
    return await call_next(request)


def _audio_type_to_zlm_params(audio_type: int | None) -> dict[str, str]:
    if audio_type == 0:
        return {"enable_audio": "0", "add_mute_audio": "0"}
    if audio_type == 1:
        return {"enable_audio": "1", "add_mute_audio": "0"}
    if audio_type == 2:
        return {"enable_audio": "1", "add_mute_audio": "1"}
    return {}


def _stream_proxy_key(vhost: str, app: str, stream: str) -> str:
    return f"{vhost}/{app}/{stream}"


DEFAULT_PLATFORM_SETTINGS = {
    "portal": {"title": "集中管理平台", "logo_url": "./assets/logo.svg", "quick_links": [], "hidden_menu_pages": []},
    "security": {"password_expiry_days": 0, "watermark_enabled": False, "watermark_text": "", "watermark_show_username": True, "watermark_show_ip": False},
}

DEFAULT_GB28181_SETTINGS = {"enabled": GB28181_SERVER.enabled, "host": GB28181_SERVER.host, "port": GB28181_SERVER.port, "server_id": GB28181_SERVER.server_id, "realm": GB28181_SERVER.realm, "password": GB28181_SERVER.password, "media_host": os.getenv("STREAMUI_GB28181_MEDIA_HOST", "")}


def _platform_settings() -> dict:
    stored = db_get_platform_settings()
    result = json.loads(json.dumps(DEFAULT_PLATFORM_SETTINGS))
    for section, values in stored.items():
        if section in result and isinstance(values, dict):
            result[section].update(values)
    if result["portal"].get("title") in {"同录集中管理平台", "同录设备集中管理平台"}:
        result["portal"]["title"] = DEFAULT_PLATFORM_SETTINGS["portal"]["title"]
    return result


def _gb28181_settings(*, include_password: bool = False) -> dict:
    values = dict(DEFAULT_GB28181_SETTINGS)
    stored = db_get_platform_settings().get("gb28181")
    if isinstance(stored, dict):
        for key in values:
            if key in stored and (key != "password" or stored[key]):
                values[key] = stored[key]
    values["enabled"] = bool(values["enabled"])
    values["port"] = int(values["port"])
    if not include_password:
        values.pop("password", None)
        values["password_set"] = bool(DEFAULT_GB28181_SETTINGS["password"] or (isinstance(stored, dict) and stored.get("password")))
    return values


def _password_expired(user: dict, settings: dict) -> bool:
    days = int((settings.get("security") or {}).get("password_expiry_days") or 0)
    if days <= 0:
        return False
    try:
        changed_at = datetime.fromisoformat(str(user.get("password_changed_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return True
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= changed_at + timedelta(days=days)


@app.post("/api/auth/login")
async def login(request: Request):
    body = await request.json()
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    user = db_get_user(username=username)
    if not user or not user.get("enabled") or not _verify_password(password, str(user["password_hash"])):
        return {"code": -1, "msg": "用户名或密码错误"}
    bound_ip = str(user.get("bound_ip") or "").strip()
    client_ip = str(request.client.host if request.client else "")
    if bound_ip and client_ip != bound_ip:
        return {"code": -1, "msg": "当前 IP 不在账号允许范围内"}
    bound_mac = str(user.get("bound_mac") or "").strip().upper().replace("-", ":")
    client_mac = str(request.headers.get("X-Client-MAC") or "").strip().upper().replace("-", ":")
    if bound_mac and client_mac != bound_mac:
        return {"code": -1, "msg": "当前终端未通过 MAC 地址校验"}
    if _password_expired(user, _platform_settings()) and not user.get("must_change_password"):
        user = db_update_user(username=username, must_change_password=True) or user
    from fastapi.responses import JSONResponse
    response = JSONResponse({"code": 0, "data": {"username": username, "role": user["role"], "must_change_password": bool(user.get("must_change_password"))}})
    response.set_cookie(SESSION_COOKIE, _sign_session(username, str(user["role"])), httponly=True, samesite="lax", max_age=8 * 3600)
    return response


@app.get("/api/platform-settings", summary="获取门户与安全配置", tags=["平台配置"])
async def get_platform_settings():
    return {"code": 0, "data": _platform_settings()}


@app.put("/api/platform-settings", summary="更新门户与安全配置", tags=["平台配置"])
async def put_platform_settings(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    portal = body.get("portal") if isinstance(body.get("portal"), dict) else {}
    security = body.get("security") if isinstance(body.get("security"), dict) else {}
    title = str(portal.get("title") or "").strip()
    logo_url = str(portal.get("logo_url") or "").strip()
    if not title or len(title) > 64 or len(logo_url) > 300 or (logo_url and not (logo_url.startswith(("/", "./", "http://", "https://")))):
        return {"code": -1, "msg": "门户标题或 Logo 地址不合法"}
    quick_links = portal.get("quick_links", [])
    hidden_menu_pages = portal.get("hidden_menu_pages", [])
    if not isinstance(quick_links, list) or not isinstance(hidden_menu_pages, list) or len(quick_links) > 20 or len(hidden_menu_pages) > 20:
        return {"code": -1, "msg": "快捷入口或菜单配置不合法"}
    normalized_links = []
    for item in quick_links:
        if not isinstance(item, dict):
            return {"code": -1, "msg": "快捷入口格式不合法"}
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        parsed = urlparse(url)
        if not label or len(label) > 40 or parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return {"code": -1, "msg": "快捷入口名称或链接不合法"}
        normalized_links.append({"label": label, "url": url})
    normalized_hidden_pages = [str(item).strip() for item in hidden_menu_pages]
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", item) for item in normalized_hidden_pages):
        return {"code": -1, "msg": "菜单标识不合法"}
    try:
        password_expiry_days = int(security.get("password_expiry_days", 0))
    except (TypeError, ValueError):
        return {"code": -1, "msg": "密码有效期不合法"}
    watermark_text = str(security.get("watermark_text") or "").strip()
    if not 0 <= password_expiry_days <= 3650 or len(watermark_text) > 80:
        return {"code": -1, "msg": "密码有效期或水印内容不合法"}
    saved = db_upsert_platform_settings(values={"portal": {"title": title, "logo_url": logo_url or "./assets/logo.svg", "quick_links": normalized_links, "hidden_menu_pages": normalized_hidden_pages}, "security": {"password_expiry_days": password_expiry_days, "watermark_enabled": bool(security.get("watermark_enabled", False)), "watermark_text": watermark_text, "watermark_show_username": bool(security.get("watermark_show_username", True)), "watermark_show_ip": bool(security.get("watermark_show_ip", False))}})
    return {"code": 0, "data": saved}


@app.get("/api/gb28181/config", summary="获取 GB28181 接入配置", tags=["GB28181"])
async def get_gb28181_config(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    values = _gb28181_settings()
    values["listening"] = GB28181_SERVER.transport is not None
    return {"code": 0, "data": values}


@app.put("/api/gb28181/config", summary="更新 GB28181 接入配置", tags=["GB28181"])
async def put_gb28181_config(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    try:
        enabled = bool(body["enabled"])
        host = str(body["host"]).strip()
        port = int(body["port"])
        server_id = str(body["server_id"]).strip()
        realm = str(body.get("realm") or server_id).strip()
        media_host = str(body.get("media_host") or "").strip()
    except (KeyError, TypeError, ValueError):
        return {"code": -1, "msg": "GB28181 配置格式不合法"}
    try:
        if media_host:
            ipaddress.IPv4Address(media_host)
    except ipaddress.AddressValueError:
        return {"code": -1, "msg": "RTP 媒体地址必须是 IPv4 地址"}
    if not host or len(host) > 255 or not 1 <= port <= 65535 or not re.fullmatch(r"[0-9A-Za-z_.-]{3,64}", server_id) or not re.fullmatch(r"[0-9A-Za-z_.-]{3,64}", realm) or (enabled and not media_host):
        return {"code": -1, "msg": "SIP 地址、端口、平台 ID、域或 RTP 媒体地址不合法"}
    current = _gb28181_settings(include_password=True)
    submitted_password = body.get("password")
    if submitted_password is not None and not isinstance(submitted_password, str):
        return {"code": -1, "msg": "国标密码格式不合法"}
    password = str(submitted_password) if submitted_password else str(current["password"])
    if len(password) > 256:
        return {"code": -1, "msg": "国标密码长度不能超过 256"}
    values = {"enabled": enabled, "host": host, "port": port, "server_id": server_id, "realm": realm, "password": password, "media_host": media_host}
    try:
        await GB28181_SERVER.configure({key: values[key] for key in ("enabled", "host", "port", "server_id", "realm", "password")})
    except OSError as error:
        return {"code": -1, "msg": f"SIP 监听启动失败: {error}"}
    db_upsert_platform_settings(values={"gb28181": values})
    result = _gb28181_settings()
    result["listening"] = GB28181_SERVER.transport is not None
    return {"code": 0, "data": result}


@app.post("/api/gb28181/devices/{device_id}/channels/{channel_id}/play", summary="发起 GB28181 实时点播", tags=["GB28181"])
async def play_gb28181_channel(device_id: str, channel_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    settings = _gb28181_settings(include_password=True)
    if not settings["enabled"] or not settings.get("media_host"):
        return {"code": -1, "msg": "请先启用 GB28181 并配置 RTP 媒体地址"}
    if not re.fullmatch(r"[0-9A-Za-z_.-]{3,64}", device_id) or not re.fullmatch(r"[0-9A-Za-z_.-]{3,64}", channel_id):
        return {"code": -1, "msg": "设备或通道 ID 不合法"}
    stream_id = f"gb_{device_id[-8:]}_{channel_id[-8:]}_{secrets.token_hex(4)}"
    try:
        response = await client.get(f"{ZLM_SERVER}/index/api/openRtpServer", params={"secret": ZLM_SECRET, "port": 0, "stream_id": stream_id, "tcp_mode": 0, "enable_tcp": 0})
        payload = response.json()
        rtp_port = int(payload.get("port") or (payload.get("data") or {}).get("port") or 0)
    except (httpx.HTTPError, ValueError, TypeError):
        return {"code": -1, "msg": "ZLMediaKit RTP 接收端口申请失败"}
    if payload.get("code") not in {0, "0"} or not 1 <= rtp_port <= 65535:
        return {"code": -1, "msg": f"ZLMediaKit RTP 接收端口申请失败: {payload.get('msg') or payload}"}
    try:
        session = GB28181_SERVER.invite_play(device_id=device_id, channel_id=channel_id, media_host=str(settings["media_host"]), media_port=rtp_port, stream_id=stream_id)
    except (RuntimeError, ValueError) as error:
        await client.get(f"{ZLM_SERVER}/index/api/closeRtpServer", params={"secret": ZLM_SECRET, "stream_id": stream_id})
        return {"code": -1, "msg": str(error)}
    return {"code": 0, "data": {**session, "rtp_port": rtp_port, "app": "rtp", "stream": stream_id}}


@app.post("/api/gb28181/play/{call_id}/stop", summary="停止 GB28181 实时点播", tags=["GB28181"])
async def stop_gb28181_play(call_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    session = GB28181_SERVER.play_sessions.get(call_id)
    if not session:
        return {"code": -1, "msg": "点播会话不存在"}
    sent = GB28181_SERVER.bye_play(call_id)
    try:
        await client.get(f"{ZLM_SERVER}/index/api/closeRtpServer", params={"secret": ZLM_SECRET, "stream_id": session["stream_id"]})
    except httpx.HTTPError:
        pass
    return {"code": 0, "data": {"bye_sent": sent}}


@app.get("/api/gb28181/play/{call_id}", summary="查询 GB28181 点播状态", tags=["GB28181"])
async def get_gb28181_play(call_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    session = GB28181_SERVER.play_sessions.get(call_id)
    if not session:
        return {"code": -1, "msg": "点播会话不存在或已停止"}
    is_online = False
    try:
        response = await client.get(f"{ZLM_SERVER}/index/api/getMediaList", params={"secret": ZLM_SECRET, "app": "rtp", "stream": session["stream_id"]})
        payload = response.json()
        is_online = payload.get("code") in {0, "0"} and any(
            str(item.get("app")) == "rtp" and str(item.get("stream")) == str(session["stream_id"])
            for item in (payload.get("data") or []) if isinstance(item, dict)
        )
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    return {"code": 0, "data": {**session, "is_online": is_online, "app": "rtp", "stream": session["stream_id"]}}


@app.post("/api/auth/logout")
async def logout():
    from fastapi.responses import JSONResponse
    response = JSONResponse({"code": 0})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/auth/me")
async def get_current_user(request: Request):
    user = _request_user(request)
    return {"code": 0, "data": user}


@app.get("/api/users")
async def get_users(request: Request):
    user = _request_user(request)
    if not user:
        return {"code": 401, "msg": "请先登录"}
    if user["role"] == "admin":
        return {"code": 0, "data": [_public_user(item) for item in db_list_users()], "self_only": False}
    stored = db_get_user(username=str(user["username"]))
    return {"code": 0, "data": [_public_user(stored)] if stored else [], "self_only": True}


@app.post("/api/users")
async def post_user(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    username = str(body.get("username", "")).strip()
    full_name = str(body.get("full_name", "")).strip()
    nickname = str(body.get("nickname", "")).strip()
    password = str(body.get("password") or INITIAL_USER_PASSWORD)
    role = str(body.get("role", "operator"))
    bound_mac = str(body.get("bound_mac") or "").strip().upper().replace("-", ":")
    bound_ip = str(body.get("bound_ip") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username) or not full_name or not nickname or len(full_name) > 64 or len(nickname) > 64 or len(password) < 8 or role not in {"admin", "operator", "viewer"} or (bound_mac and not re.fullmatch(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", bound_mac)) or (bound_ip and not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", bound_ip)):
        return {"code": -1, "msg": "请填写姓名和昵称；登录名称为 3-32 位字符，密码至少 8 位"}
    if db_get_user(username=username):
        return {"code": -1, "msg": "用户名已存在"}
    try:
        created = db_create_user(username=username, full_name=full_name, nickname=nickname, password_hash=_password_hash(password), role=role, must_change_password=True, bound_mac=bound_mac, bound_ip=bound_ip)
    except ValueError as error:
        return {"code": -1, "msg": str(error)}
    return {"code": 0, "data": _public_user(created), "initial_password": password}


@app.put("/api/users/{username}")
async def put_user(username: str, request: Request):
    current_user = _request_user(request)
    if not current_user:
        return {"code": 401, "msg": "请先登录"}
    body = await request.json()
    password = body.get("password")
    role = body.get("role")
    enabled = body.get("enabled")
    target = db_get_user(username=username)
    if not target:
        return {"code": -1, "msg": "用户不存在"}
    full_name = body.get("full_name")
    nickname = body.get("nickname")
    if full_name is not None:
        full_name = str(full_name).strip()
    if nickname is not None:
        nickname = str(nickname).strip()
    if (full_name is not None and (not full_name or len(full_name) > 64)) or (nickname is not None and (not nickname or len(nickname) > 64)):
        return {"code": -1, "msg": "用户姓名和昵称不能为空且不能超过 64 个字符"}
    if current_user["role"] != "admin":
        if username != current_user["username"]:
            return {"code": 403, "msg": "只能编辑自己的账号资料"}
        if any(key in body for key in {"role", "enabled", "password", "must_change_password"}):
            return {"code": 403, "msg": "普通账号不能修改账号类型、状态或重置密码"}
        result = db_update_user(username=username, full_name=full_name, nickname=nickname)
        return {"code": 0, "data": _public_user(result)}
    if role is not None and role not in {"admin", "operator", "viewer"}:
        return {"code": -1, "msg": "无效角色"}
    if password is not None and len(str(password)) < 8:
        return {"code": -1, "msg": "密码至少 8 位"}
    bound_mac = str(body.get("bound_mac") or "").strip().upper().replace("-", ":") if "bound_mac" in body else None
    bound_ip = str(body.get("bound_ip") or "").strip() if "bound_ip" in body else None
    if (bound_mac and not re.fullmatch(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", bound_mac)) or (bound_ip and not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", bound_ip)):
        return {"code": -1, "msg": "MAC 地址或 IP 地址格式无效"}
    if username == current_user.get("username") and ((role is not None and role != target["role"]) or enabled is False):
        return {"code": -1, "msg": "不能修改当前管理员自己的角色或禁用自己"}
    remains_active_admin = (role if role is not None else target["role"]) == "admin" and (bool(enabled) if enabled is not None else bool(target["enabled"]))
    if target["role"] == "admin" and target["enabled"] and not remains_active_admin:
        active_admins = [item for item in db_list_users() if item["role"] == "admin" and item["enabled"]]
        if len(active_admins) <= 1:
            return {"code": -1, "msg": "至少需要保留一个可用管理员"}
    result = db_update_user(username=username, full_name=full_name, nickname=nickname, role=role, enabled=bool(enabled) if enabled is not None else None, password_hash=_password_hash(str(password)) if password is not None else None, must_change_password=bool(body.get("must_change_password", True)) if password is not None else None, bound_mac=bound_mac, bound_ip=bound_ip)
    return {"code": 0, "data": _public_user(result)}


@app.delete("/api/users/{username}")
async def delete_user(username: str, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    target = db_get_user(username=username)
    current_user = _request_user(request) or {}
    if not target:
        return {"code": -1, "msg": "用户不存在"}
    if int(target["id"]) == BUILTIN_ADMIN_ID:
        return {"code": -1, "msg": "内置管理员（ID 1000）不能删除"}
    if username == current_user.get("username"):
        return {"code": -1, "msg": "不能删除当前登录账号"}
    if target["role"] == "admin" and target["enabled"]:
        active_admins = [item for item in db_list_users() if item["role"] == "admin" and item["enabled"]]
        if len(active_admins) <= 1:
            return {"code": -1, "msg": "至少需要保留一个可用管理员"}
    deleted = db_delete_user(username=username)
    return {"code": 0, "deleted": deleted}


def _organization_payload(body: dict) -> tuple[int | None, str, str, int, bool] | None:
    parent_value = body.get("parent_id")
    try:
        parent_id = int(parent_value) if parent_value not in (None, "") else None
        sort_order = int(body.get("sort_order", 0))
    except (TypeError, ValueError):
        return None
    name = str(body.get("name") or "").strip()
    code = str(body.get("code") or "").strip().upper()
    if not name or len(name) > 80 or not re.fullmatch(r"[A-Z0-9_-]{2,32}", code) or not 0 <= sort_order <= 9999:
        return None
    return parent_id, name, code, sort_order, bool(body.get("enabled", True))


@app.get("/api/organizations", summary="获取组织机构", tags=["组织人员"])
async def get_organizations():
    return {"code": 0, "data": db_list_organizations()}


@app.post("/api/organizations", summary="创建组织机构", tags=["组织人员"])
async def post_organization(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    payload = _organization_payload(await request.json())
    if not payload:
        return {"code": -1, "msg": "组织名称、编码或排序值不合法"}
    saved = db_create_organization(parent_id=payload[0], name=payload[1], code=payload[2], sort_order=payload[3], enabled=payload[4])
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "上级组织不存在或组织编码已存在"}


@app.put("/api/organizations/{organization_id}", summary="更新组织机构", tags=["组织人员"])
async def put_organization(organization_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    payload = _organization_payload(await request.json())
    if not payload:
        return {"code": -1, "msg": "组织名称、编码或排序值不合法"}
    saved = db_update_organization(organization_id=organization_id, parent_id=payload[0], name=payload[1], code=payload[2], sort_order=payload[3], enabled=payload[4])
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "组织不存在、上级组织无效或编码已存在"}


@app.delete("/api/organizations/{organization_id}", summary="删除组织机构", tags=["组织人员"])
async def delete_organization(organization_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    return {"code": 0, "deleted": db_delete_organization(organization_id=organization_id)}


def _personnel_payload(body: dict) -> tuple[int | None, str, str, str, str, str, bool] | None:
    organization_value = body.get("organization_id")
    try:
        organization_id = int(organization_value) if organization_value not in (None, "") else None
    except (TypeError, ValueError):
        return None
    name = str(body.get("name") or "").strip()
    employee_no = str(body.get("employee_no") or "").strip()
    identity_no = str(body.get("identity_no") or "").strip().upper()
    phone = str(body.get("phone") or "").strip()
    title = str(body.get("title") or "").strip()
    if not name or not employee_no or len(name) > 64 or not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", employee_no) or len(identity_no) > 32 or len(phone) > 32 or len(title) > 64:
        return None
    return organization_id, name, employee_no, identity_no, phone, title, bool(body.get("enabled", True))


@app.get("/api/personnel", summary="获取人员档案", tags=["组织人员"])
async def get_personnel(keyword: str = Query("", max_length=80)):
    return {"code": 0, "data": db_list_personnel(keyword=keyword.strip())}


@app.post("/api/personnel", summary="创建人员档案", tags=["组织人员"])
async def post_personnel(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    payload = _personnel_payload(body)
    if not payload:
        return {"code": -1, "msg": "人员信息不合法"}
    create_account = bool(body.get("create_account", False))
    username = ""
    initial_password = ""
    if create_account:
        username = str(body.get("username") or payload[2]).strip()
        initial_password = str(body.get("password") or INITIAL_USER_PASSWORD)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username) or len(initial_password) < 8 or db_get_user(username=username):
            return {"code": -1, "msg": "自动创建账号的登录名称或密码不合法，或账号已存在"}
        try:
            db_create_user(username=username, full_name=payload[1], nickname=payload[1], password_hash=_password_hash(initial_password), role="operator", must_change_password=True)
        except ValueError as error:
            return {"code": -1, "msg": str(error)}
    saved = db_create_personnel(organization_id=payload[0], name=payload[1], employee_no=payload[2], identity_no=payload[3], phone=payload[4], title=payload[5], username=username or None, enabled=payload[6])
    if not saved and username:
        db_delete_user(username=username)
    return {"code": 0, "data": saved, "initial_password": initial_password} if saved else {"code": -1, "msg": "组织不存在、工号已存在或账号已关联其他人员"}


@app.put("/api/personnel/{personnel_id}", summary="更新人员档案", tags=["组织人员"])
async def put_personnel(personnel_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    payload = _personnel_payload(await request.json())
    if not payload:
        return {"code": -1, "msg": "人员信息不合法"}
    saved = db_update_personnel(personnel_id=personnel_id, organization_id=payload[0], name=payload[1], employee_no=payload[2], identity_no=payload[3], phone=payload[4], title=payload[5], enabled=payload[6])
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "人员或组织不存在，或工号已存在"}


@app.delete("/api/personnel/{personnel_id}", summary="删除人员档案", tags=["组织人员"])
async def delete_personnel(personnel_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    return {"code": 0, "deleted": db_delete_personnel(personnel_id=personnel_id)}


@app.post("/api/auth/password")
async def change_own_password(request: Request):
    user = _request_user(request)
    if not user:
        return {"code": 401, "msg": "请先登录"}
    body = await request.json()
    current_password = str(body.get("current_password", ""))
    new_password = str(body.get("new_password", ""))
    stored = db_get_user(username=str(user["username"]))
    if not stored or not _verify_password(current_password, str(stored["password_hash"])):
        return {"code": -1, "msg": "当前密码错误"}
    if len(new_password) < 8:
        return {"code": -1, "msg": "新密码至少 8 位"}
    if _verify_password(new_password, str(stored["password_hash"])):
        return {"code": -1, "msg": "新密码不能与当前密码相同"}
    result = db_update_user(username=str(user["username"]), password_hash=_password_hash(new_password), must_change_password=False)
    return {"code": 0, "data": _public_user(result)}


@app.post("/api/device/register")
async def register_device(request: Request):
    body = await request.json()
    device_id = str(body.get("device_id", "")).strip()
    name = str(body.get("name", "")).strip()
    provided_key = str(body.get("access_key", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{3,64}", device_id) or not name:
        return {"code": -1, "msg": "device_id 或设备名称不合法"}
    if len(name) > 128:
        return {"code": -1, "msg": "设备名称不能超过 128 个字符"}
    existing = db_get_device(device_id=device_id)
    if not existing:
        return {"code": 403, "msg": "设备未在平台预创建"}
    if not existing.get("enabled"):
        return {"code": 403, "msg": "设备接入尚未启用"}
    if not provided_key or not db_verify_device_key(device_id=device_id, access_key=provided_key):
        return {"code": -1, "msg": "access_key 无效"}
    web_url = _valid_device_web_url(body.get("web_url"))
    if body.get("web_url") and not web_url:
        return {"code": -1, "msg": "设置地址必须是有效的 http 或 https URL"}
    device = db_touch_device(device_id=device_id, metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else None) or existing
    return {"code": 0, "msg": "注册成功", "data": device}


@app.post("/api/device/heartbeat")
async def device_heartbeat(request: Request):
    body = await request.json()
    device_id = str(body.get("device_id", "")).strip()
    device = db_get_device(device_id=device_id)
    if not device or not device.get("enabled"):
        return {"code": 403, "msg": "设备未预创建或接入未启用"}
    if not db_verify_device_key(device_id=device_id, access_key=str(body.get("access_key", ""))):
        return {"code": -1, "msg": "设备认证失败"}
    return {"code": 0, "data": db_touch_device(device_id=device_id, metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else None)}


@app.post("/api/devices")
async def post_device(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    device_id = str(body.get("device_id", "")).strip()
    name = str(body.get("name", "")).strip()
    serial_number = str(body.get("serial_number", "")).strip() or None
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{3,64}", device_id) or not name or len(name) > 128:
        return {"code": -1, "msg": "device_id 或设备名称不合法"}
    web_url = _valid_device_web_url(body.get("web_url"))
    if body.get("web_url") and not web_url:
        return {"code": -1, "msg": "设置地址必须是有效的 http 或 https URL"}
    access_key = secrets.token_urlsafe(24)
    device = db_create_device(device_id=device_id, name=name, access_key=access_key, serial_number=serial_number, address=str(body.get("address") or "").strip() or None, web_url=web_url, enabled=bool(body.get("enabled", False)))
    if not device:
        return {"code": -1, "msg": "设备 ID 已存在"}
    return {"code": 0, "data": device, "access_key": access_key}


@app.put("/api/devices/{device_id}")
async def put_device(device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    if not body:
        return {"code": -1, "msg": "没有可更新的设备字段"}
    name = body.get("name")
    if name is not None:
        name = str(name).strip()
        if not name or len(name) > 128:
            return {"code": -1, "msg": "设备名称不能为空且不能超过 128 个字符"}
    serial_number = body.get("serial_number")
    if serial_number is not None:
        serial_number = str(serial_number).strip()
    address = body.get("address")
    if address is not None:
        address = str(address).strip()
    web_url = _valid_device_web_url(body.get("web_url")) if "web_url" in body else None
    if body.get("web_url") and not web_url:
        return {"code": -1, "msg": "设置地址必须是有效的 http 或 https URL"}
    if "web_url" in body and not body.get("web_url"):
        web_url = ""
    if body.get("enabled") is False and db_device_has_active_case_work(device_id=device_id):
        return {"code": -1, "msg": "设备存在办理中任务或活动会话，不能停用接入"}
    device = db_update_device(device_id=device_id, name=name, serial_number=serial_number, address=address, web_url=web_url, enabled=bool(body["enabled"]) if "enabled" in body else None)
    return {"code": 0, "data": device} if device else {"code": -1, "msg": "设备不存在"}


@app.delete("/api/devices/{device_id}")
async def delete_device(device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    if db_device_has_active_case_work(device_id=device_id):
        return {"code": -1, "msg": "设备存在办理中任务或活动会话，不能删除"}
    if db_device_has_case_history(device_id=device_id):
        return {"code": -1, "msg": "设备已有案件历史，不能删除；请停用接入以保留证据链"}
    deleted = db_delete_device(device_id=device_id)
    return {"code": 0, "deleted": deleted} if deleted else {"code": -1, "msg": "设备不存在"}


@app.get("/api/devices")
async def get_devices():
    return {"code": 0, "data": db_list_devices()}


@app.get("/api/devices/{device_id}/access-key")
async def get_device_access_key(device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    access_key = db_get_device_access_key(device_id=device_id)
    if access_key is None:
        return {"code": -1, "msg": "该设备的历史接入密钥无法查看，请重新生成"}
    return {"code": 0, "access_key": access_key}


@app.post("/api/devices/{device_id}/access-key")
async def rotate_device_access_key(device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    access_key = secrets.token_urlsafe(24)
    if not db_rotate_device_access_key(device_id=device_id, access_key=access_key):
        return {"code": -1, "msg": "设备不存在"}
    return {"code": 0, "access_key": access_key}


ROOM_TYPES = {"interrogation", "talk", "investigation_command", "retention", "other"}


def _resource_text(body: dict, field: str, maximum: int, *, required: bool = False) -> str | None:
    value = str(body.get(field) or "").strip()
    if (required and not value) or len(value) > maximum:
        return None
    return value


def _resource_number(body: dict, field: str, minimum: int, maximum: int, default: int = 0) -> int | None:
    try:
        value = int(body.get(field, default))
    except (TypeError, ValueError):
        return None
    return value if minimum <= value <= maximum else None


@app.get("/api/resources/directories", summary="获取业务目录", tags=["资源管理"])
async def get_business_directories():
    return {"code": 0, "data": db_list_business_directories()}


@app.post("/api/resources/directories", summary="创建业务目录", tags=["资源管理"])
async def post_business_directory(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    name = _resource_text(body, "name", 80, required=True)
    code = _resource_text(body, "code", 32, required=True)
    description = _resource_text(body, "description", 500)
    sort_order = _resource_number(body, "sort_order", 0, 9999)
    if not name or not code or not re.fullmatch(r"[A-Za-z0-9_-]{2,32}", code) or description is None or sort_order is None:
        return {"code": -1, "msg": "目录名称、编码、描述或排序值不合法"}
    saved = db_create_business_directory(name=name, code=code.upper(), description=description, sort_order=sort_order, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "目录名称或编码已存在"}


@app.put("/api/resources/directories/{directory_id}", summary="更新业务目录", tags=["资源管理"])
async def put_business_directory(directory_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    name = _resource_text(body, "name", 80, required=True)
    code = _resource_text(body, "code", 32, required=True)
    description = _resource_text(body, "description", 500)
    sort_order = _resource_number(body, "sort_order", 0, 9999)
    if not name or not code or not re.fullmatch(r"[A-Za-z0-9_-]{2,32}", code) or description is None or sort_order is None:
        return {"code": -1, "msg": "目录名称、编码、描述或排序值不合法"}
    saved = db_update_business_directory(directory_id=directory_id, name=name, code=code.upper(), description=description, sort_order=sort_order, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "目录不存在，或名称/编码已存在"}


@app.delete("/api/resources/directories/{directory_id}", summary="删除业务目录", tags=["资源管理"])
async def delete_business_directory(directory_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    return {"code": 0, "deleted": db_delete_business_directory(directory_id=directory_id)}


@app.get("/api/resources/areas", summary="获取谈话办案区", tags=["资源管理"])
async def get_interview_areas(directory_id: int | None = None):
    return {"code": 0, "data": db_list_interview_areas(directory_id=directory_id)}


@app.post("/api/resources/areas", summary="创建谈话办案区", tags=["资源管理"])
async def post_interview_area(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    directory_id = _resource_number(body, "directory_id", 1, 2_147_483_647)
    name = _resource_text(body, "name", 80, required=True)
    location = _resource_text(body, "location", 160)
    sort_order = _resource_number(body, "sort_order", 0, 9999)
    if not directory_id or not db_get_business_directory(directory_id=directory_id) or not name or location is None or sort_order is None:
        return {"code": -1, "msg": "所属目录、区域名称、位置或排序值不合法"}
    saved = db_create_interview_area(directory_id=directory_id, name=name, location=location, sort_order=sort_order, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "区域名称已存在"}


@app.put("/api/resources/areas/{area_id}", summary="更新谈话办案区", tags=["资源管理"])
async def put_interview_area(area_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    directory_id = _resource_number(body, "directory_id", 1, 2_147_483_647)
    name = _resource_text(body, "name", 80, required=True)
    location = _resource_text(body, "location", 160)
    sort_order = _resource_number(body, "sort_order", 0, 9999)
    if not directory_id or not db_get_business_directory(directory_id=directory_id) or not name or location is None or sort_order is None:
        return {"code": -1, "msg": "所属目录、区域名称、位置或排序值不合法"}
    saved = db_update_interview_area(area_id=area_id, directory_id=directory_id, name=name, location=location, sort_order=sort_order, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "区域不存在或同目录名称已存在"}


@app.delete("/api/resources/areas/{area_id}", summary="删除谈话办案区", tags=["资源管理"])
async def delete_interview_area(area_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    return {"code": 0, "deleted": db_delete_interview_area(area_id=area_id)}


@app.get("/api/resources/rooms", summary="获取谈话房间", tags=["资源管理"])
async def get_interview_rooms(area_id: int | None = None):
    return {"code": 0, "data": db_list_interview_rooms(area_id=area_id)}


@app.post("/api/resources/rooms", summary="创建谈话房间", tags=["资源管理"])
async def post_interview_room(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    area_id = _resource_number(body, "area_id", 1, 2_147_483_647)
    name = _resource_text(body, "name", 80, required=True)
    room_type = _resource_text(body, "room_type", 32, required=True)
    capacity = _resource_number(body, "capacity", 0, 999)
    location = _resource_text(body, "location", 160)
    if not area_id or not db_get_interview_area(area_id=area_id) or not name or room_type not in ROOM_TYPES or capacity is None or location is None:
        return {"code": -1, "msg": "所属区域、房间名称、类型、容量或位置不合法"}
    saved = db_create_interview_room(area_id=area_id, name=name, room_type=room_type, capacity=capacity, location=location, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "房间名称已存在"}


@app.put("/api/resources/rooms/{room_id}", summary="更新谈话房间", tags=["资源管理"])
async def put_interview_room(room_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    area_id = _resource_number(body, "area_id", 1, 2_147_483_647)
    name = _resource_text(body, "name", 80, required=True)
    room_type = _resource_text(body, "room_type", 32, required=True)
    capacity = _resource_number(body, "capacity", 0, 999)
    location = _resource_text(body, "location", 160)
    if not area_id or not db_get_interview_area(area_id=area_id) or not name or room_type not in ROOM_TYPES or capacity is None or location is None:
        return {"code": -1, "msg": "所属区域、房间名称、类型、容量或位置不合法"}
    saved = db_update_interview_room(room_id=room_id, area_id=area_id, name=name, room_type=room_type, capacity=capacity, location=location, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "房间不存在或同区域名称已存在"}


@app.delete("/api/resources/rooms/{room_id}", summary="删除谈话房间", tags=["资源管理"])
async def delete_interview_room(room_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    return {"code": 0, "deleted": db_delete_interview_room(room_id=room_id)}


@app.get("/api/resources/rooms/{room_id}/devices", summary="获取房间设备", tags=["资源管理"])
async def get_interview_room_devices(room_id: int):
    if not db_get_interview_room(room_id=room_id):
        return {"code": -1, "msg": "房间不存在"}
    return {"code": 0, "data": db_list_interview_room_devices(room_id=room_id)}


@app.put("/api/resources/rooms/{room_id}/devices/{device_id}", summary="关联房间设备", tags=["资源管理"])
async def put_interview_room_device(room_id: int, device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    if db_assign_device_to_interview_room(room_id=room_id, device_id=device_id):
        return {"code": 0, "data": db_get_interview_room(room_id=room_id)}
    return {"code": -1, "msg": "房间或设备不存在，或设备存在未结束办案会话"}


@app.delete("/api/resources/rooms/{room_id}/devices/{device_id}", summary="解除房间设备关联", tags=["资源管理"])
async def delete_interview_room_device(room_id: int, device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    if db_remove_device_from_interview_room(room_id=room_id, device_id=device_id):
        return {"code": 0}
    return {"code": -1, "msg": "关联不存在，或设备存在未结束办案会话"}


@app.get("/api/resources/rooms/{room_id}/case-devices", summary="获取房间可用办案设备", tags=["资源管理"])
async def get_interview_room_case_devices(room_id: int, case_id: int = Query(...)):
    if not db_get_interview_room(room_id=room_id) or not db_get_case(case_id=case_id):
        return {"code": -1, "msg": "房间或案件不存在"}
    assigned = {str(item["device_id"]) for item in db_list_case_assignments(case_id=case_id) if item["status"] in {"received", "handling"}}
    devices = [item for item in db_list_interview_room_devices(room_id=room_id) if item["enabled"] and item["device_id"] in assigned]
    return {"code": 0, "data": devices}


ALARM_SOURCE_TYPES = {"button", "camera", "intercom", "guard_terminal", "alarm_host", "manual"}
ALARM_SEVERITIES = {"info", "warning", "urgent", "critical"}


async def _execute_alarm_linkages(alarm: dict, *, retry: bool = False) -> None:
    actions = db_list_alarm_linkage_actions(alarm_id=int(alarm["id"]))
    device_ids = [str(alarm["device_id"])] if alarm.get("device_id") else []
    if not device_ids and alarm.get("room_id"):
        device_ids = [str(item["device_id"]) for item in db_list_interview_room_devices(room_id=int(alarm["room_id"]))]
    channels = [channel for device_id in device_ids for channel in db_list_channels(device_id=device_id) if channel.get("app") and channel.get("stream")]
    online_keys: set[tuple[str, str, str]] = set()
    try:
        response = await client.get(f"{ZLM_SERVER}/index/api/getMediaList", params={"secret": ZLM_SECRET})
        raw = response.json()
        if raw.get("code") == 0:
            online_keys = {(str(item.get("vhost") or "__defaultVhost__"), str(item.get("app") or ""), str(item.get("stream") or "")) for item in raw.get("data", [])}
    except (httpx.HTTPError, ValueError):
        pass
    online_channels = [channel for channel in channels if (str(channel.get("vhost") or "__defaultVhost__"), str(channel["app"]), str(channel["stream"])) in online_keys]
    for action in actions:
        if action["status"] == "succeeded" and not retry:
            continue
        action_type = str(action["action_type"])
        if action_type == "live_video":
            detail = {"device_ids": device_ids, "streams": [{"vhost": item.get("vhost") or "__defaultVhost__", "app": item["app"], "stream": item["stream"]} for item in online_channels]}
            if online_channels:
                db_update_alarm_linkage_action(action_id=int(action["id"]), status="succeeded", detail=detail)
            else:
                db_update_alarm_linkage_action(action_id=int(action["id"]), status="failed", detail={"reason": "未找到在线且已配置的设备视频流", "device_ids": device_ids})
        elif action_type == "alarm_record":
            if not online_channels:
                db_update_alarm_linkage_action(action_id=int(action["id"]), status="failed", detail={"reason": "未找到可录制的在线视频流"})
                continue
            channel = online_channels[0]
            vhost = str(channel.get("vhost") or "__defaultVhost__")
            path = f"alarms/{int(alarm['id'])}/{channel['app']}-{channel['stream']}-{int(time.time())}.mp4"
            try:
                response = await client.get(f"{ZLM_SERVER}/index/api/startRecordTask", params={"secret": ZLM_SECRET, "vhost": vhost, "app": channel["app"], "stream": channel["stream"], "path": path, "back_ms": "30000", "forward_ms": "60000"})
                raw = response.json()
                if raw.get("code") == 0:
                    db_update_alarm_linkage_action(action_id=int(action["id"]), status="succeeded", detail={"recording_path": path, "vhost": vhost, "app": channel["app"], "stream": channel["stream"], "back_ms": 30000, "forward_ms": 60000})
                else:
                    db_update_alarm_linkage_action(action_id=int(action["id"]), status="failed", detail={"reason": str(raw.get("msg") or raw), "app": channel["app"], "stream": channel["stream"]})
            except (httpx.HTTPError, ValueError) as error:
                db_update_alarm_linkage_action(action_id=int(action["id"]), status="failed", detail={"reason": f"录像联动请求失败: {error}"})
        elif action_type == "snapshot":
            db_update_alarm_linkage_action(action_id=int(action["id"]), status="failed", detail={"reason": "未配置设备抓图接口，无法生成可审计抓拍"})
        elif action_type == "video_wall":
            db_update_alarm_linkage_action(action_id=int(action["id"]), status="failed", detail={"reason": "未配置专用报警上墙目标，避免改写用户的视频墙布局"})
        elif action_type == "led_push":
            db_update_alarm_linkage_action(action_id=int(action["id"]), status="failed", detail={"reason": "未配置 LED 控制器协议或网关"})


def _queue_alarm_linkages(alarm: dict, *, retry: bool = False) -> None:
    asyncio.create_task(_execute_alarm_linkages(alarm, retry=retry))


@app.get("/api/alarms", summary="查询报警记录", tags=["紧急报警"])
async def get_alarms(status: str = Query("", max_length=20)):
    if status and status not in {"active", "acknowledged", "resolved"}:
        return {"code": -1, "msg": "报警状态无效"}
    return {"code": 0, "data": db_list_alarm_events(status=status or None)}


@app.post("/api/alarms", summary="人工创建紧急报警", tags=["紧急报警"])
async def post_alarm(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    source_type = str(body.get("source_type") or "manual").strip()
    severity = str(body.get("severity") or "urgent").strip()
    message = str(body.get("message") or "").strip()
    try:
        room_id = int(body["room_id"]) if body.get("room_id") not in (None, "") else None
    except (TypeError, ValueError):
        return {"code": -1, "msg": "房间信息不合法"}
    device_id = str(body.get("device_id") or "").strip() or None
    if source_type not in ALARM_SOURCE_TYPES or severity not in ALARM_SEVERITIES or not message or len(message) > 500:
        return {"code": -1, "msg": "报警来源、级别或内容不合法"}
    saved = db_create_alarm_event(room_id=room_id, device_id=device_id, source_type=source_type, severity=severity, message=message, detail={"reported_by": str((_request_user(request) or {}).get("username", "unknown"))})
    if saved:
        _queue_alarm_linkages(saved)
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "房间或设备不存在"}


@app.post("/api/device/alarms", summary="设备上报紧急报警", tags=["紧急报警"])
async def post_device_alarm(request: Request, access_key: str = Header(..., alias="X-Device-Access-Key")):
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    if not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    source_type = str(body.get("source_type") or "alarm_host").strip()
    severity = str(body.get("severity") or "urgent").strip()
    message = str(body.get("message") or "").strip()
    try:
        room_id = int(body["room_id"]) if body.get("room_id") not in (None, "") else None
    except (TypeError, ValueError):
        return {"code": -1, "msg": "房间信息不合法"}
    if source_type not in ALARM_SOURCE_TYPES or severity not in ALARM_SEVERITIES or not message or len(message) > 500:
        return {"code": -1, "msg": "报警来源、级别或内容不合法"}
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
    saved = db_create_alarm_event(room_id=room_id, device_id=device_id, source_type=source_type, severity=severity, message=message, detail=detail)
    if saved:
        _queue_alarm_linkages(saved)
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "房间或设备不存在"}


@app.post("/api/alarms/{alarm_id}/status", summary="确认或解除报警", tags=["紧急报警"])
async def post_alarm_status(alarm_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    status = str((await request.json()).get("status") or "").strip()
    saved = db_update_alarm_event_status(alarm_id=alarm_id, status=status, actor=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "报警不存在或状态流转无效"}


@app.get("/api/alarms/{alarm_id}/linkages", summary="获取报警联动任务", tags=["紧急报警"])
async def get_alarm_linkages(alarm_id: int):
    if not db_get_alarm_event(alarm_id=alarm_id):
        return {"code": -1, "msg": "报警不存在"}
    return {"code": 0, "data": db_list_alarm_linkage_actions(alarm_id=alarm_id)}


@app.post("/api/alarms/{alarm_id}/linkages/execute", summary="重试报警联动", tags=["紧急报警"])
async def post_alarm_linkages_execute(alarm_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    alarm = db_get_alarm_event(alarm_id=alarm_id)
    if not alarm:
        return {"code": -1, "msg": "报警不存在"}
    _queue_alarm_linkages(alarm, retry=True)
    return {"code": 0, "msg": "报警联动已重新排队"}


@app.put("/api/alarms/linkages/{action_id}", summary="更新报警联动任务", tags=["紧急报警"])
async def put_alarm_linkage(action_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    status = str(body.get("status") or "").strip()
    if status not in {"queued", "running", "succeeded", "failed"}:
        return {"code": -1, "msg": "联动任务状态无效"}
    saved = db_update_alarm_linkage_action(action_id=action_id, status=status, detail=body.get("detail") if isinstance(body.get("detail"), dict) else {})
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "联动任务不存在"}


@app.get("/api/alarm-recipients", summary="获取报警推送对象", tags=["紧急报警"])
async def get_alarm_recipients():
    return {"code": 0, "data": db_list_alarm_recipients()}


@app.post("/api/alarm-recipients", summary="创建报警推送对象", tags=["紧急报警"])
async def post_alarm_recipient(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    username = str(body.get("username") or "").strip()
    target_ip = str(body.get("target_ip") or "").strip()
    if (not username and not target_ip) or (username and not db_get_user(username=username)) or (target_ip and not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", target_ip)):
        return {"code": -1, "msg": "推送用户或 IP 地址不合法"}
    saved = db_upsert_alarm_recipient(recipient_id=None, username=username, target_ip=target_ip, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "推送对象已存在"}


@app.delete("/api/alarm-recipients/{recipient_id}", summary="删除报警推送对象", tags=["紧急报警"])
async def delete_alarm_recipient(recipient_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    return {"code": 0, "deleted": db_delete_alarm_recipient(recipient_id=recipient_id)}


ACCESS_AUTH_METHODS = {"card", "face", "fingerprint", "card_face", "card_fingerprint"}


@app.get("/api/access-points", summary="获取门禁点", tags=["门禁管理"])
async def get_access_points():
    return {"code": 0, "data": db_list_access_points()}


@app.post("/api/access-points", summary="创建门禁点", tags=["门禁管理"])
async def post_access_point(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    name = str(body.get("name") or "").strip()
    point_code = str(body.get("point_code") or "").strip().upper()
    device_id = str(body.get("device_id") or "").strip() or None
    try:
        room_id = int(body["room_id"]) if body.get("room_id") not in (None, "") else None
    except (TypeError, ValueError):
        return {"code": -1, "msg": "关联房间不合法"}
    if not name or len(name) > 80 or not re.fullmatch(r"[A-Z0-9_-]{2,64}", point_code) or (device_id and not db_get_device(device_id=device_id)) or (room_id and not db_get_interview_room(room_id=room_id)):
        return {"code": -1, "msg": "门禁点名称、编码、设备或房间不合法"}
    saved = db_create_access_point(device_id=device_id, room_id=room_id, name=name, point_code=point_code, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "门禁点编码已存在"}


@app.put("/api/access-points/{point_id}", summary="更新门禁点", tags=["门禁管理"])
async def put_access_point(point_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    name = str(body.get("name") or "").strip()
    point_code = str(body.get("point_code") or "").strip().upper()
    device_id = str(body.get("device_id") or "").strip() or None
    try:
        room_id = int(body["room_id"]) if body.get("room_id") not in (None, "") else None
    except (TypeError, ValueError):
        return {"code": -1, "msg": "关联房间不合法"}
    if not name or len(name) > 80 or not re.fullmatch(r"[A-Z0-9_-]{2,64}", point_code) or (device_id and not db_get_device(device_id=device_id)) or (room_id and not db_get_interview_room(room_id=room_id)):
        return {"code": -1, "msg": "门禁点名称、编码、设备或房间不合法"}
    saved = db_update_access_point(point_id=point_id, device_id=device_id, room_id=room_id, name=name, point_code=point_code, enabled=bool(body.get("enabled", True)))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "门禁点不存在或编码已存在"}


@app.delete("/api/access-points/{point_id}", summary="删除门禁点", tags=["门禁管理"])
async def delete_access_point(point_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    return {"code": 0, "deleted": db_delete_access_point(point_id=point_id)}


@app.get("/api/access-permissions", summary="查询门禁权限", tags=["门禁管理"])
async def get_access_permissions(personnel_id: int | None = None):
    return {"code": 0, "data": db_list_access_permissions(personnel_id=personnel_id)}


@app.post("/api/access-permissions", summary="配置门禁权限", tags=["门禁管理"])
async def post_access_permission(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    try:
        point_id = int(body.get("access_point_id"))
        personnel_id = int(body.get("personnel_id"))
    except (TypeError, ValueError):
        return {"code": -1, "msg": "门禁点或人员不合法"}
    valid_from = str(body.get("valid_from") or "").strip() or None
    valid_to = str(body.get("valid_to") or "").strip() or None
    schedule_template = str(body.get("schedule_template") or "").strip()[:80]
    holiday_plan = str(body.get("holiday_plan") or "").strip()[:80]
    auth_method = str(body.get("auth_method") or "card").strip()
    if auth_method not in ACCESS_AUTH_METHODS or (valid_from and valid_to and valid_to <= valid_from):
        return {"code": -1, "msg": "认证方式或有效期不合法"}
    saved = db_upsert_access_permission(point_id=point_id, personnel_id=personnel_id, valid_from=valid_from, valid_to=valid_to, schedule_template=schedule_template, holiday_plan=holiday_plan, auth_method=auth_method)
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "门禁点或人员不存在"}


@app.put("/api/access-permissions/{permission_id}/delivery", summary="更新权限下发状态", tags=["门禁管理"])
async def put_access_permission_delivery(permission_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    status = str((await request.json()).get("delivery_status") or "").strip()
    if status not in {"pending", "delivering", "succeeded", "failed"}:
        return {"code": -1, "msg": "下发状态无效"}
    saved = db_update_access_permission_delivery(permission_id=permission_id, status=status)
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "权限不存在"}


@app.delete("/api/access-permissions/{permission_id}", summary="撤销门禁权限", tags=["门禁管理"])
async def delete_access_permission(permission_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    return {"code": 0, "deleted": db_delete_access_permission(permission_id=permission_id)}


@app.get("/api/access-events", summary="查询人员进出事件", tags=["门禁管理"])
async def get_access_events():
    return {"code": 0, "data": db_list_access_events()}


@app.post("/api/device/access-events", summary="设备上报进出事件", tags=["门禁管理"])
async def post_device_access_event(request: Request, access_key: str = Header(..., alias="X-Device-Access-Key")):
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    if not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    try:
        point_id = int(body.get("access_point_id"))
        personnel_id = int(body["personnel_id"]) if body.get("personnel_id") not in (None, "") else None
    except (TypeError, ValueError):
        return {"code": -1, "msg": "门禁点或人员不合法"}
    direction = str(body.get("direction") or "").strip()
    event_time = str(body.get("event_time") or _now_iso()).strip()
    snapshot_url = str(body.get("snapshot_url") or "").strip()[:500]
    if direction not in {"in", "out"}:
        return {"code": -1, "msg": "进出方向无效"}
    saved = db_create_access_event(point_id=point_id, personnel_id=personnel_id, direction=direction, event_time=event_time, snapshot_url=snapshot_url, detail=body.get("detail") if isinstance(body.get("detail"), dict) else {})
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "门禁点不存在"}


@app.get("/api/case-sessions/{session_id}/remote-commands", summary="获取会话远程指挥", tags=["远程指挥"])
async def get_remote_commands(session_id: int):
    if not db_get_case_session(session_id=session_id):
        return {"code": -1, "msg": "办案会话不存在"}
    return {"code": 0, "data": db_list_remote_commands(session_id=session_id)}


@app.post("/api/case-sessions/{session_id}/remote-commands", summary="发送远程指挥", tags=["远程指挥"])
async def post_remote_command(session_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    command_type = str(body.get("command_type") or "text").strip()
    content = str(body.get("content") or "").strip()
    if command_type != "text" or not content or len(content) > 1000:
        return {"code": -1, "msg": "仅支持文字指令；实时语音请使用语音指挥通道"}
    saved = db_create_remote_command(session_id=session_id, command_type=command_type, content=content, sent_by=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "办案会话不存在或当前不允许远程指挥"}


def _device_webrtc_publish_target(device: dict) -> dict | None:
    raw_address = str(device.get("web_url") or device.get("address") or "").strip()
    parsed = urlparse(raw_address if "://" in raw_address else f"http://{raw_address}")
    if not parsed.hostname:
        return None
    host = parsed.hostname
    host_for_url = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return {"publish_url": f"http://{host_for_url}:1985/rtc/v1/publish/", "stream_host": host_for_url}


@app.post("/api/case-sessions/{session_id}/voice-commands", summary="创建实时语音指挥通道", tags=["远程指挥"])
async def post_voice_command(session_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    session = db_get_case_session(session_id=session_id)
    if not session or session["status"] not in {"active", "finalizing"}:
        return {"code": -1, "msg": "办案会话不存在或当前不允许语音指挥"}
    device = db_get_device(device_id=str(session["device_id"]))
    target = _device_webrtc_publish_target(device or {})
    if not target:
        return {"code": -1, "msg": "设备未配置可用的 Web 地址或 IP 地址"}
    channel_token = secrets.token_hex(8)
    stream_name = f"talkback_{session_id}_{channel_token}"
    stream_url = f"webrtc://{target['stream_host']}/live/{stream_name}"
    detail = {"transport": "webrtc", "stream_name": stream_name, "stream_url": stream_url, "direction": "platform_to_device", "device_receiver_required": True}
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    saved = db_create_remote_command(session_id=session_id, command_type="voice", content="实时语音指挥通道", sent_by=actor, detail=detail)
    if not saved:
        return {"code": -1, "msg": "语音指挥通道创建失败"}
    return {"code": 0, "data": {"command": saved, "channel": {"signal_url": f"/api/case-sessions/{session_id}/voice-commands/{saved['id']}/offer", "stream_name": stream_name, "device_receiver_required": True}}}


@app.post("/api/case-sessions/{session_id}/voice-commands/{command_id}/offer", summary="转发语音 WebRTC 信令", tags=["远程指挥"])
async def post_voice_command_offer(session_id: int, command_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    sdp = str(body.get("sdp") or "")
    if not sdp or len(sdp) > 100000:
        return {"code": -1, "msg": "WebRTC SDP 不合法"}
    session = db_get_case_session(session_id=session_id)
    command = next((item for item in db_list_remote_commands(session_id=session_id) if int(item["id"]) == command_id and item["command_type"] == "voice" and item["status"] == "sent"), None)
    if not session or not command:
        return {"code": -1, "msg": "办案会话或语音指挥通道不存在"}
    detail = command.get("detail") or {}
    if detail.get("transport") != "webrtc" or not detail.get("stream_url"):
        return {"code": -1, "msg": "语音指挥通道配置无效"}
    target = _device_webrtc_publish_target(db_get_device(device_id=str(session["device_id"])) or {})
    if not target:
        return {"code": -1, "msg": "设备未配置可用的 Web 地址或 IP 地址"}
    try:
        response = await client.post(target["publish_url"], json={"api": target["publish_url"], "streamurl": detail["stream_url"], "clientip": None, "sdp": sdp})
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return {"code": -1, "msg": f"设备 WebRTC 信令失败: {error}"}
    if result.get("code") not in (0, None) or not result.get("sdp"):
        return {"code": -1, "msg": str(result.get("msg") or "设备拒绝 WebRTC 发布")}
    return {"code": 0, "data": {"sdp": result["sdp"]}}


@app.delete("/api/case-sessions/{session_id}/remote-commands/{command_id}", summary="取消待确认远程指挥", tags=["远程指挥"])
async def delete_remote_command(session_id: int, command_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    command = next((item for item in db_list_remote_commands(session_id=session_id) if int(item["id"]) == command_id), None)
    if not command:
        return {"code": -1, "msg": "远程指挥不存在"}
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    saved = db_cancel_remote_command(command_id=command_id, actor=actor)
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "仅可取消设备尚未确认的指挥"}


@app.get("/api/device/case-sessions/{session_id}/remote-commands", summary="设备获取远程指挥", tags=["远程指挥"])
async def get_device_remote_commands(session_id: int, device_id: str = Query(...), access_key: str = Header(..., alias="X-Device-Access-Key")):
    session = db_get_case_session(session_id=session_id)
    if not session or session["device_id"] != device_id or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证或会话归属无效"}
    return {"code": 0, "data": db_list_remote_commands(session_id=session_id, include_acknowledged=False)}


@app.post("/api/device/case-sessions/{session_id}/remote-commands/{command_id}/ack", summary="设备确认远程指挥", tags=["远程指挥"])
async def post_device_remote_command_ack(session_id: int, command_id: int, request: Request, access_key: str = Header(..., alias="X-Device-Access-Key")):
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    session = db_get_case_session(session_id=session_id)
    if not session or session["device_id"] != device_id or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证或会话归属无效"}
    command = next((item for item in db_list_remote_commands(session_id=session_id) if int(item["id"]) == command_id), None)
    if not command:
        return {"code": -1, "msg": "指挥指令不存在"}
    result = str(body.get("result") or "acknowledged").strip()
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
    if result not in {"acknowledged", "completed", "failed"} or len(json.dumps(detail, ensure_ascii=True)) > 4000:
        return {"code": -1, "msg": "设备回执结果或详情不合法"}
    saved = db_complete_remote_command(command_id=command_id, actor=f"device:{device_id}", status=result, detail=detail)
    return {"code": 0, "data": saved} if saved else {"code": -1, "msg": "指挥指令已完成或状态无效"}


CASE_TYPES = {"criminal", "administrative", "other"}
DEVICE_CASE_STATUSES = {"pending", "received", "handling", "completed"}
CASE_SESSION_TYPES = {"interrogation", "inquiry", "identification", "other"}
CASE_SESSION_STATUSES = {"planned", "active", "finalizing", "ended", "cancelled"}
CASE_RECORDING_MODES = {"disk", "sync_burn"}
TRANSCRIPT_TYPES = {"interrogation", "inquiry", "identification", "other"}
MEDIA_TYPES = {"audio", "video"}
TRANSCRIPT_TEMPLATES = {"interrogation": "讯问笔录", "inquiry": "询问笔录", "identification": "辨认笔录", "other": "通用笔录"}


def _tiptap_text(value: object) -> dict:
    return {"type": "text", "text": str(value)}


def _tiptap_paragraph(value: object = "") -> dict:
    return {"type": "paragraph", "content": [_tiptap_text(value)]} if value else {"type": "paragraph"}


def _default_transcript_content(transcript: dict) -> dict:
    title = TRANSCRIPT_TEMPLATES.get(str(transcript.get("template_key") or transcript.get("transcript_type")), "通用笔录")
    return {"type": "doc", "content": [{"type": "heading", "attrs": {"level": 1}, "content": [_tiptap_text(title)]}, _tiptap_paragraph(f"案件编号：{transcript.get('case_no') or ''}"), _tiptap_paragraph(f"案件名称：{transcript.get('case_name') or ''}"), _tiptap_paragraph(f"办案会话：{transcript.get('session_no') or ''}"), _tiptap_paragraph("时间："), _tiptap_paragraph("地点："), {"type": "qaLine", "attrs": {"kind": "question"}}, {"type": "qaLine", "attrs": {"kind": "answer"}}, _tiptap_paragraph("以上笔录经核对无误。"), _tiptap_paragraph("记录人：                         被询问人：")]}


def _tiptap_docx_lines(content: dict) -> list[str]:
    def text(node: object) -> str:
        if not isinstance(node, dict):
            return ""
        if node.get("type") == "text":
            return str(node.get("text") or "")
        if node.get("type") == "hardBreak":
            return "\n"
        return "".join(text(item) for item in node.get("content", []))

    lines: list[str] = []
    for node in content.get("content", []):
        if not isinstance(node, dict):
            continue
        kind = node.get("type")
        value = text(node)
        if kind == "qaLine":
            lines.append(f"{'答：' if (node.get('attrs') or {}).get('kind') == 'answer' else '问：'}{value}")
        elif kind in {"bulletList", "orderedList"}:
            for item in node.get("content", []):
                lines.append(f"{'• ' if kind == 'bulletList' else '1. '}{text(item)}")
        elif kind != "horizontalRule":
            lines.append(value)
    return lines or [""]


def _materialize_transcript_template(content: dict, transcript: dict) -> dict:
    values = {
        "{{case_no}}": str(transcript.get("case_no") or ""),
        "{{case_name}}": str(transcript.get("case_name") or ""),
        "{{session_no}}": str(transcript.get("session_no") or ""),
        "{{date}}": datetime.now().strftime("%Y年%m月%d日"),
    }

    def replace(node: object) -> object:
        if isinstance(node, list):
            return [replace(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = {key: replace(value) for key, value in node.items()}
        if result.get("type") == "text" and isinstance(result.get("text"), str):
            for token, value in values.items():
                result["text"] = result["text"].replace(token, value)
        return result

    return replace(content)


def _transcript_template_options() -> list[dict]:
    builtin = [{"key": key, "name": name, "transcript_type": key, "builtin": True} for key, name in TRANSCRIPT_TEMPLATES.items()]
    builtin.extend({"key": key, "name": item["name"], "transcript_type": item["transcript_type"], "builtin": True} for key, item in BUILTIN_TIPTAP_TEMPLATES.items())
    imported = [{"key": item["template_key"], "name": item["name"], "transcript_type": item["transcript_type"], "builtin": False, "updated_at": item["updated_at"]} for item in db_list_case_transcript_templates()]
    return builtin + imported


def _transcript_template_docx_path(template: dict) -> Path | None:
    relative_path = Path(str(template.get("source_docx_path") or ""))
    if not relative_path or relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    candidate = TRANSCRIPT_TEMPLATE_ROOT / relative_path
    try:
        candidate.resolve().relative_to(TRANSCRIPT_TEMPLATE_ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _preview_tiptap_template(content: dict) -> dict:
    values = {
        "{{case_no}}": "演示案件〔2026〕001号",
        "{{case_name}}": "笔录模板样式演示",
        "{{session_no}}": "演示会话001",
        "{{date}}": "2026年08月05日",
        "{{姓名}}": "张三",
        "{{性别}}": "男",
        "{{年龄}}": "28",
        "{{民族}}": "汉族",
        "{{身份证号}}": "110101199808080018",
        "{{工作单位}}": "示例单位",
        "{{职务}}": "职员",
        "{{住址}}": "北京市东城区示例路1号",
        "{{办案机关}}": "示例执法机关",
        "{{办案人员}}": "李四、王五",
        "{{开始时间}}": "09时00分",
        "{{结束时间}}": "10时00分",
        "{{地点}}": "第一询问室",
        "{{案由}}": "示例事项",
        "{{执法证件号1}}": "A001",
        "{{执法证件号2}}": "A002",
        "{{当事人签名}}": "张三",
        "{{办案人员签名}}": "李四",
        "{{记录人签名}}": "王五",
    }

    def replace(node: object) -> object:
        if isinstance(node, list):
            return [replace(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = {key: replace(value) for key, value in node.items()}
        if result.get("type") == "text" and isinstance(result.get("text"), str):
            for token, value in values.items():
                result["text"] = result["text"].replace(token, value)
        return result

    return replace(content)


_DOCX_FIELD_NAMES = ("身份证（有效身份证件）号码", "住址（联系地址）", "第二被约谈人身份证号", "第二被约谈人工作单位", "第二被约谈人单位职务", "谈话人1单位职务", "谈话人2单位职务", "办案人员签名", "当事人签名", "记录人签名", "执法证件号1", "执法证件号2", "办案机关", "办案人员", "开始时间", "结束时间", "身份证号", "工作单位", "联系电话", "联系地址", "谈话地点", "讯问地点", "询问地点", "约谈地点", "讯问机关", "询问机关", "讯问人员", "询问人员", "被讯问人", "被询问人", "被约谈人", "谈话人一", "谈话人二", "被约谈人一", "被约谈人二", "姓名", "性别", "年龄", "民族", "职务", "住址", "日期", "时间", "地点", "案由")


def _docx_field_name(before: str, ordinal: int, used: dict[str, int]) -> str:
    labels = tuple(_DOCX_FIELD_NAMES) + ("人员签名", "第页", "共页", "证件编号")
    label = max(labels, key=lambda item: before.rfind(item))
    if before.rfind(label) < 0:
        label = "填写字段"
    used[label] = used.get(label, 0) + 1
    return label if used[label] == 1 else f"{label}（{used[label]}）"


def _docx_time_inline_content(value: str) -> list[dict] | None:
    match = re.match(r"^(?P<prefix>.*?(?P<label>(?:讯问|询问|谈话|起止)?时间)[：:]?)(?P<tail>[\s\u3000_年月日时分至]+)$", value)
    if not match:
        return None
    result = [_tiptap_text(match.group("prefix"))]
    tail = match.group("tail")
    offset = 0
    segment = "开始"
    for field_match in re.finditer(r"[\s\u3000_]{3,}(?P<unit>[年月日时分])", tail):
        between = tail[offset:field_match.start()]
        if "至" in between:
            segment = "结束"
        if between:
            result.append(_tiptap_text(between))
        unit = field_match.group("unit")
        result.append({"type": "inputField", "attrs": {"name": f"{match.group('label')}{segment}时间（{unit}）"}})
        result.append(_tiptap_text(unit))
        offset = field_match.end()
    if offset == 0:
        return None
    if offset < len(tail):
        result.append(_tiptap_text(tail[offset:]))
    return result


def _docx_inline_content(value: str) -> list[dict]:
    time_content = _docx_time_inline_content(value)
    if time_content:
        return time_content
    pattern = re.compile(r"\{\{([^{}\n]{1,80})\}\}|(" + "|".join(re.escape(name) for name in _DOCX_FIELD_NAMES) + r")(：|:)?([\s\u3000_]{3,})")
    result: list[dict] = []
    offset = 0
    for match in pattern.finditer(value):
        if match.start() > offset:
            result.append(_tiptap_text(value[offset:match.start()]))
        if match.group(1):
            field_name = match.group(1).strip()
        else:
            field_name = match.group(2).strip()
            result.append(_tiptap_text(f"{match.group(2)}{match.group(3) or ''}"))
        result.append({"type": "inputField", "attrs": {"name": field_name}})
        offset = match.end()
    if offset < len(value):
        result.append(_tiptap_text(value[offset:]))
    return result or [_tiptap_text(value)]


def _docx_paragraph_inline_content(paragraph: Paragraph) -> list[dict]:
    value = paragraph.text.replace("\xa0", " ")
    time_content = _docx_time_inline_content(value)
    if time_content:
        return time_content
    if not any(run.font.underline and re.fullmatch(r"[\s\u3000_]+", run.text or "") for run in paragraph.runs):
        return _docx_inline_content(value)
    result: list[dict] = []
    before = ""
    used: dict[str, int] = {}
    ordinal = 0
    for run in paragraph.runs:
        text = run.text.replace("\xa0", " ")
        if run.font.underline and re.fullmatch(r"[\s\u3000_]+", text or ""):
            ordinal += 1
            result.append({"type": "inputField", "attrs": {"name": _docx_field_name(before, ordinal, used)}})
        elif text:
            result.append(_tiptap_text(text))
        before += text
    return result or [_tiptap_text(value)]


def _docx_append_text(nodes: list[dict], value: str, inline_content: list[dict] | None = None) -> None:
    value = value.replace("\xa0", " ").strip("\n")
    if not value.strip():
        return
    compact = value.strip()
    if compact.startswith("问："):
        text = compact[2:].strip()
        node = {"type": "qaLine", "attrs": {"kind": "question"}}
        if text:
            node["content"] = _docx_inline_content(text)
        nodes.append(node)
    elif compact.startswith("答："):
        text = compact[2:].strip()
        node = {"type": "qaLine", "attrs": {"kind": "answer"}}
        if text:
            node["content"] = _docx_inline_content(text)
        nodes.append(node)
    elif not nodes and "笔录" in re.sub(r"\s+", "", compact) and len(compact) <= 40:
        nodes.append({"type": "heading", "attrs": {"level": 1}, "content": [_tiptap_text(re.sub(r"\s+", "", compact))]})
    else:
        nodes.append({"type": "paragraph", "content": inline_content or _docx_inline_content(value)})


def _docx_template_content(payload: bytes) -> dict:
    if len(payload) > 10 * 1024 * 1024:
        raise ValueError("DOCX 模板不能超过 10MB")
    try:
        document = Document(io.BytesIO(payload))
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as error:
        raise ValueError("上传文件不是有效的 DOCX 文档") from error
    nodes: list[dict] = []
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            _docx_append_text(nodes, paragraph.text, _docx_paragraph_inline_content(paragraph))
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            for row in table.rows:
                _docx_append_text(nodes, "    ".join(cell.text.replace("\n", " ") for cell in row.cells))
    if not nodes:
        raise ValueError("DOCX 文档未包含可导入的正文")
    return _normalize_tiptap_content({"type": "doc", "content": nodes})


def _normalize_tiptap_content(value: object) -> dict:
    if not isinstance(value, dict) or value.get("type") != "doc" or not isinstance(value.get("content"), list):
        raise ValueError("笔录内容格式无效")
    allowed_nodes = {"doc", "paragraph", "heading", "text", "hardBreak", "bulletList", "orderedList", "listItem", "blockquote", "horizontalRule", "qaLine", "inputField"}
    allowed_marks = {"bold", "italic", "strike", "code"}
    count = 0

    def visit(node: object) -> dict:
        nonlocal count
        count += 1
        if count > 10000 or not isinstance(node, dict) or node.get("type") not in allowed_nodes:
            raise ValueError("笔录内容包含不支持的结构")
        kind = str(node["type"])
        result: dict = {"type": kind}
        if kind == "text":
            text = node.get("text")
            if not isinstance(text, str) or len(text) > 10000:
                raise ValueError("笔录文本无效")
            result["text"] = text
            marks = node.get("marks", [])
            if marks:
                if not isinstance(marks, list) or any(not isinstance(mark, dict) or mark.get("type") not in allowed_marks for mark in marks):
                    raise ValueError("笔录格式无效")
                result["marks"] = [{"type": mark["type"]} for mark in marks]
            return result
        if kind == "heading":
            level = int((node.get("attrs") or {}).get("level", 1))
            result["attrs"] = {"level": min(3, max(1, level))}
        if kind == "qaLine":
            result["attrs"] = {"kind": "answer" if (node.get("attrs") or {}).get("kind") == "answer" else "question"}
        if kind == "inputField":
            name = str((node.get("attrs") or {}).get("name") or "").strip()
            if not name or len(name) > 80:
                raise ValueError("笔录填写字段无效")
            result["attrs"] = {"name": name}
        content = node.get("content")
        if content is not None:
            if not isinstance(content, list):
                raise ValueError("笔录节点内容无效")
            result["content"] = [visit(item) for item in content]
        return result

    normalized = visit(value)
    if len(json.dumps(normalized, ensure_ascii=False)) > 500000:
        raise ValueError("笔录内容过大")
    return normalized


def _tiptap_plain_text(node: object) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return str(node.get("text") or "")
    return "".join(_tiptap_plain_text(item) for item in node.get("content", []))


def _transcript_quality_issues(transcript: dict, content: dict) -> list[str]:
    text = _tiptap_plain_text(content).strip()
    issues: list[str] = []
    placeholders = sorted(set(re.findall(r"\{\{[^{}\n]{1,80}\}\}", text)))
    if placeholders:
        issues.append(f"仍有未填写字段：{'、'.join(placeholders[:6])}{'等' if len(placeholders) > 6 else ''}")
    empty_fields: list[str] = []

    def collect_empty_fields(node: object) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "inputField" and not _tiptap_plain_text(node).strip():
            name = str((node.get("attrs") or {}).get("name") or "填写字段")
            if name not in empty_fields:
                empty_fields.append(name)
        for item in node.get("content", []):
            collect_empty_fields(item)

    collect_empty_fields(content)
    if empty_fields:
        issues.append(f"仍有未填写字段：{'、'.join(empty_fields[:6])}{'等' if len(empty_fields) > 6 else ''}")
    if len(re.sub(r"\s+", "", text)) < 30:
        issues.append("笔录正文内容不足，不能定稿")
    if transcript.get("transcript_type") in {"interrogation", "inquiry"}:
        question_count = 0
        answer_count = 0
        for item in content.get("content", []):
            if not isinstance(item, dict):
                continue
            value = _tiptap_plain_text(item).strip()
            if not value:
                continue
            if item.get("type") == "qaLine":
                if (item.get("attrs") or {}).get("kind") == "answer":
                    answer_count += 1
                else:
                    question_count += 1
            elif item.get("type") == "paragraph":
                if value.startswith("问："):
                    question_count += 1
                elif value.startswith("答："):
                    answer_count += 1
        if not question_count or not answer_count:
            issues.append("讯问或询问笔录至少需要一组已填写的问答")
        elif question_count != answer_count:
            issues.append("问答条目数量不一致，请补齐问答记录")
    return issues


def _render_tiptap_html(node: dict) -> str:
    kind = node["type"]
    if kind == "text":
        rendered = html.escape(node.get("text", ""))
        for mark in node.get("marks", []):
            tag = {"bold": "strong", "italic": "em", "strike": "s", "code": "code"}[mark["type"]]
            rendered = f"<{tag}>{rendered}</{tag}>"
        return rendered
    content = "".join(_render_tiptap_html(item) for item in node.get("content", []))
    if kind == "doc": return content
    if kind == "paragraph": return f"<p>{content or '<br>'}</p>"
    if kind == "heading":
        level = int((node.get("attrs") or {}).get("level", 1))
        return f"<h{level}>{content}</h{level}>"
    if kind == "hardBreak": return "<br>"
    if kind == "bulletList": return f"<ul>{content}</ul>"
    if kind == "orderedList": return f"<ol>{content}</ol>"
    if kind == "listItem": return f"<li>{content}</li>"
    if kind == "blockquote": return f"<blockquote>{content}</blockquote>"
    if kind == "horizontalRule": return "<hr>"
    if kind == "qaLine":
        label = "答：" if (node.get("attrs") or {}).get("kind") == "answer" else "问："
        return f"<p class=\"qa-line\"><strong>{label}</strong><span>{content or '<br>'}</span></p>"
    if kind == "inputField":
        name = html.escape(str((node.get("attrs") or {}).get("name") or ""))
        return f"<span class=\"input-field\" data-field-name=\"{name}\">{content or '<br>'}</span>"
    return ""


def _transcript_snapshot_html(transcript: dict, content: dict) -> str:
    body = _render_tiptap_html(content)
    return f"""<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>{html.escape(str(transcript['title']))}</title><style>body{{max-width:820px;margin:32px auto;font:16px/1.8 'Microsoft YaHei',sans-serif;color:#111}}h1{{text-align:center}}p{{margin:0 0 12px}}blockquote{{margin:12px 0;padding-left:16px;border-left:3px solid #999}}.qa-line{{display:flex;gap:8px}}.qa-line strong{{flex:0 0 2.5em}}.qa-line span{{flex:1;border-bottom:1px solid #333;min-height:1.8em}}.input-field{{display:inline-block;min-width:8em;border-bottom:1px solid #333}}@media print{{body{{margin:0}}}}</style></head><body>{body}</body></html>"""


def _transcript_pdf_bytes(transcript: dict, content: dict) -> bytes:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TranscriptTitle", parent=styles["Title"], fontName="STSong-Light", fontSize=18, leading=26, alignment=TA_CENTER, spaceAfter=12)
    body_style = ParagraphStyle("TranscriptBody", parent=styles["BodyText"], fontName="STSong-Light", fontSize=11, leading=20, spaceAfter=5, wordWrap="CJK")
    story = [PdfParagraph(html.escape(str(transcript["title"])), title_style)]
    for line in _tiptap_docx_lines(content):
        safe_line = html.escape(line).replace("\n", "<br/>") or "&#160;"
        story.append(PdfParagraph(safe_line, body_style))
    story.append(Spacer(1, 8))
    document.build(story)
    return output.getvalue()


@app.get("/api/cases", summary="获取案件列表", tags=["案件"])
async def get_cases(keyword: str = Query("", max_length=160), status: str = Query("", max_length=32)):
    if status and status not in {"created", "assigned", "handling", "closed", "archived"}:
        return {"code": -1, "msg": "案件状态无效"}
    return {"code": 0, "data": db_list_cases(keyword=keyword.strip(), status=status or None)}


@app.get("/api/cases/workflow/dashboard", summary="获取办案流程总览", tags=["案件"])
async def get_case_workflow_dashboard():
    return {"code": 0, "data": db_get_case_workflow_dashboard()}


@app.post("/api/cases", summary="创建案件", tags=["案件"])
async def post_case(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    case_no = str(body.get("case_no") or "").strip()
    name = str(body.get("name") or "").strip()
    case_type = str(body.get("case_type") or "criminal").strip()
    case_reference = str(body.get("case_reference") or "").strip()
    case_category = str(body.get("case_category") or "").strip()
    handling_unit = str(body.get("handling_unit") or "").strip()
    case_reason = str(body.get("case_reason") or "").strip()
    lead_investigator = str(body.get("lead_investigator") or "").strip()
    incident_at = str(body.get("incident_at") or "").strip()
    arrival_method = str(body.get("arrival_method") or "").strip()
    interviewer_one_unit = str(body.get("interviewer_one_unit") or "").strip()
    interviewer_two = str(body.get("interviewer_two") or "").strip()
    interviewer_two_unit = str(body.get("interviewer_two_unit") or "").strip()
    recorder_name = str(body.get("recorder_name") or "").strip()
    subject_name = str(body.get("subject_name") or "").strip()
    interview_location = str(body.get("interview_location") or "").strip()
    transcript_template = str(body.get("transcript_template") or "").strip()
    planned_start_at = str(body.get("planned_start_at") or "").strip()
    planned_end_at = str(body.get("planned_end_at") or "").strip()
    device_id = str(body.get("device_id") or "").strip()
    try:
        inquiry_count = max(1, int(body.get("inquiry_count") or 1))
    except (TypeError, ValueError):
        return {"code": -1, "msg": "问话次数不合法"}
    if not case_no:
        case_no = f"AJ-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    device = db_get_device(device_id=device_id)
    if not name or not device_id or not device or not device.get("enabled") or len(case_no) > 64 or len(name) > 160 or len(case_reference) > 128 or len(case_category) > 32 or len(handling_unit) > 128 or len(case_reason) > 1000 or any(len(value) > 160 for value in (lead_investigator, incident_at, arrival_method, interviewer_one_unit, interviewer_two, interviewer_two_unit, recorder_name, subject_name, interview_location, transcript_template, planned_start_at, planned_end_at)) or inquiry_count > 99 or case_type not in CASE_TYPES or case_category not in {"", "talk", "inquiry", "interrogation", "identification", "other"} or any(part in case_no for part in ("/", "\\", "..")):
        return {"code": -1, "msg": "案件编号、名称、类型、承办单位或主办人员不合法"}
    templates = await _device_note_templates(device)
    if not templates or not transcript_template or transcript_template not in templates:
        return {"code": -1, "msg": "所选笔录模板不在目标设备中，请重新选择"}
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    created = db_create_case(case_no=case_no, name=name, case_type=case_type, case_reference=case_reference, case_category=case_category, handling_unit=handling_unit, case_reason=case_reason, lead_investigator=lead_investigator, incident_at=incident_at, arrival_method=arrival_method, interviewer_one_unit=interviewer_one_unit, interviewer_two=interviewer_two, interviewer_two_unit=interviewer_two_unit, recorder_name=recorder_name, subject_name=subject_name, interview_location=interview_location, inquiry_count=inquiry_count, transcript_template=transcript_template, planned_start_at=planned_start_at, planned_end_at=planned_end_at, created_by=actor)
    if created:
        db_assign_case_to_device(case_id=int(created["id"]), device_id=device_id, assigned_by=actor)
        created = db_get_case(case_id=int(created["id"]))
    return {"code": 0, "data": created} if created else {"code": -1, "msg": "案件编号已存在"}


@app.get("/api/devices/{device_id}/note-templates", summary="获取设备笔录模板", tags=["案件"])
async def get_device_note_templates(device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    device = db_get_device(device_id=device_id)
    url = _lm700_control_url((device or {}).get("address") or (device or {}).get("web_url"))
    if not device or not device.get("enabled") or not url:
        return {"code": -1, "msg": "设备未启用或未配置有效控制地址"}
    templates = await _device_note_templates(device)
    if templates is None:
        return {"code": -1, "msg": "设备笔录模板读取失败"}
    return {"code": 0, "data": templates}


async def _device_note_templates(device: dict) -> list[str] | None:
    url = _lm700_control_url(device.get("address") or device.get("web_url"))
    if not url:
        return None
    payload = {"restfulApi": "WebAjax", "tokenKey": secrets.token_hex(16), "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], "authKey": LM700_AUTH_KEY, "interface": {"action": "noteTemplate", "matcher": "interQuery", "data": {}}}
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    templates = result.get("returnData") if int(result.get("returnVal", -1)) == 0 else []
    if not isinstance(templates, list):
        templates = []
    return [str(item) for item in templates if isinstance(item, str) and item]


@app.get("/api/cases/{case_id}", summary="获取案件办案全貌", tags=["案件"])
async def get_case_detail(case_id: int):
    case = db_get_case(case_id=case_id)
    if not case:
        return {"code": -1, "msg": "案件不存在"}
    return {"code": 0, "data": {
        "case": case,
        "assignments": db_list_case_assignments(case_id=case_id),
        "sessions": db_list_case_sessions(case_id=case_id),
        "commands": db_list_case_device_commands(case_id=case_id),
        "disc_evidence": {str(session["id"]): db_get_case_disc_evidence(session_id=int(session["id"])) for session in db_list_case_sessions(case_id=case_id)},
        "transcripts": db_list_case_transcripts(case_id=case_id),
        "media": db_list_case_media_assets(case_id=case_id),
        "archives": db_list_case_archive_files(case_id=case_id),
    }}


@app.get("/api/cases/{case_id}/archives", summary="获取案件归档材料", tags=["案件"])
async def get_case_archives(case_id: int):
    if not db_get_case(case_id=case_id):
        return {"code": -1, "msg": "案件不存在"}
    return {"code": 0, "data": db_list_case_archive_files(case_id=case_id)}


@app.get("/api/cases/{case_id}/archive-package", summary="下载案件归档包", tags=["案件"])
async def download_case_archive_package(case_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    case = db_get_case(case_id=case_id)
    if not case:
        return {"code": -1, "msg": "案件不存在"}
    archives = db_list_case_archive_files(case_id=case_id)
    handle, temporary_name = tempfile.mkstemp(prefix=f"case-{case_id}-", suffix=".zip")
    os.close(handle)
    package_path = Path(temporary_name)
    try:
        manifest = {"case_no": case["case_no"], "case_name": case["name"], "generated_at": _now_iso(), "files": []}
        with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as package:
            for archive in archives:
                try:
                    source = _archive_storage_path(str(archive["device_id"]), str(archive["stored_name"]))
                except ValueError:
                    continue
                if not source.is_file():
                    continue
                archive_name = f"materials/{int(archive['id']):04d}_{Path(str(archive['original_name'])).name}"
                package.write(source, archive_name)
                manifest["files"].append({"archive_id": archive["id"], "path": archive_name, "type": archive["archive_type"], "sha256": archive["sha256"], "size": archive["file_size"], "created_at": archive["created_at"]})
            package.writestr("归档清单.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    except OSError:
        package_path.unlink(missing_ok=True)
        return {"code": -1, "msg": "案件归档包生成失败"}
    safe_case_no = re.sub(r"[^A-Za-z0-9_-]+", "_", str(case["case_no"])) or f"case_{case_id}"
    return FileResponse(package_path, media_type="application/zip", filename=f"{safe_case_no}-归档资料.zip", background=BackgroundTask(package_path.unlink, missing_ok=True))


@app.get("/api/cases/{case_id}/audit-logs", summary="获取案件审计记录", tags=["案件"])
async def get_case_audit_logs(case_id: int):
    if not db_get_case(case_id=case_id):
        return {"code": -1, "msg": "案件不存在"}
    return {"code": 0, "data": db_list_case_audit_logs(case_id=case_id), "audit_chain_valid": db_verify_case_audit_chain(case_id=case_id)}


@app.get("/api/cases/{case_id}/completion-report", summary="获取案件办结完整性核验", tags=["案件"])
async def get_case_completion_report(case_id: int):
    report = db_get_case_completion_report(case_id=case_id)
    return {"code": 0, "data": report} if report else {"code": -1, "msg": "案件不存在"}


@app.post("/api/cases/{case_id}/close", summary="办结案件", tags=["案件"])
async def post_close_case(case_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "仅管理员可办结案件"}
    closed = db_close_case(case_id=case_id, actor=str((_request_user(request) or {}).get("username", "unknown")))
    if closed:
        return {"code": 0, "data": closed}
    report = db_get_case_completion_report(case_id=case_id)
    return {"code": -1, "msg": "案件尚未满足办结完整性要求", "data": report}


@app.post("/api/cases/{case_id}/archive", summary="归档已办结案件", tags=["案件"])
async def post_archive_case(case_id: int, request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "仅管理员可归档案件"}
    archived = db_archive_case(case_id=case_id, actor=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": archived} if archived else {"code": -1, "msg": "仅已办结案件可归档"}


@app.get("/api/cases/{case_id}/sessions", summary="获取案件办案会话", tags=["案件"])
async def get_case_sessions(case_id: int):
    if not db_get_case(case_id=case_id):
        return {"code": -1, "msg": "案件不存在"}
    return {"code": 0, "data": db_list_case_sessions(case_id=case_id)}


@app.post("/api/cases/{case_id}/sessions", summary="创建案件办案会话", tags=["案件"])
async def post_case_session(case_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    case = db_get_case(case_id=case_id)
    if not case or case["status"] in {"closed", "archived"}:
        return {"code": -1, "msg": "案件不存在或已结束"}
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    try:
        room_id = int(body["room_id"]) if body.get("room_id") not in (None, "") else None
    except (TypeError, ValueError):
        return {"code": -1, "msg": "谈话房间信息不合法"}
    session_type = str(body.get("session_type") or "interrogation").strip()
    recording_mode = str(body.get("recording_mode") or "disk").strip()
    planned_start_at = _parse_planned_time(body.get("planned_start_at"))
    planned_end_at = _parse_planned_time(body.get("planned_end_at"))
    session_no = str(body.get("session_no") or "").strip() or f"{case['case_no']}-S-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2).upper()}"
    location = str(body.get("location") or "").strip()
    host_name = str(body.get("host_name") or "").strip()
    participant_summary = str(body.get("participant_summary") or "").strip()
    subject_name = str(body.get("subject_name") or "").strip()
    interviewer_names = str(body.get("interviewer_names") or "").strip()
    recorder_name = str(body.get("recorder_name") or "").strip()
    if session_type not in CASE_SESSION_TYPES or recording_mode not in CASE_RECORDING_MODES or (body.get("planned_start_at") and not planned_start_at) or (body.get("planned_end_at") and not planned_end_at) or (planned_start_at and not planned_end_at) or (planned_end_at and (not planned_start_at or planned_end_at <= planned_start_at)) or len(session_no) > 96 or len(location) > 160 or len(host_name) > 80 or len(participant_summary) > 1000 or len(subject_name) > 160 or len(interviewer_names) > 500 or len(recorder_name) > 80:
        return {"code": -1, "msg": "会话信息不合法"}
    if not db_get_device(device_id=device_id) or not any(item["device_id"] == device_id and item["status"] in {"received", "handling"} for item in db_list_case_assignments(case_id=case_id)):
        return {"code": -1, "msg": "设备尚未接收案件或已完成，不能创建办案会话"}
    if room_id is not None:
        room = db_get_interview_room(room_id=room_id)
        if not room or not any(item["device_id"] == device_id for item in db_list_interview_room_devices(room_id=room_id)):
            return {"code": -1, "msg": "办案设备不属于所选谈话房间"}
        if not location:
            location = str(room.get("location") or room["name"])
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    created = db_create_case_session(case_id=case_id, device_id=device_id, room_id=room_id, session_no=session_no, session_type=session_type, recording_mode=recording_mode, planned_start_at=planned_start_at, planned_end_at=planned_end_at, location=location, host_name=host_name, participant_summary=participant_summary, subject_name=subject_name, interviewer_names=interviewer_names, recorder_name=recorder_name, created_by=actor)
    if created and planned_start_at:
        db_create_case_device_command(session_id=int(created["id"]), action="start", scheduled_at=planned_start_at, idempotency_key=f"session:{created['id']}:start", created_by=actor)
        db_create_case_device_command(session_id=int(created["id"]), action="stop", scheduled_at=str(planned_end_at), idempotency_key=f"session:{created['id']}:stop", created_by=actor)
    return {"code": 0, "data": created} if created else {"code": -1, "msg": "会话编号已存在"}


@app.post("/api/case-sessions/{session_id}/commands", summary="执行办案会话录制命令", tags=["案件"])
async def post_case_session_command(session_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    action = str(body.get("action") or "").strip()
    session = db_get_case_session(session_id=session_id)
    if not session or action not in {"start", "stop"}:
        return {"code": -1, "msg": "办案会话或命令无效"}
    if (action == "start" and session["status"] != "planned") or (action == "stop" and session["status"] != "active"):
        return {"code": -1, "msg": "当前会话状态不允许执行该命令"}
    now = _now_iso()
    if action == "start" and session.get("planned_start_at") and now < session["planned_start_at"]:
        return {"code": -1, "msg": "未到计划开始时间，不能提前启动办案会话"}
    if action == "start" and session.get("planned_end_at") and now >= session["planned_end_at"]:
        return {"code": -1, "msg": "已超过计划结束时间，请重新排期后再启动办案会话"}
    command = db_create_case_device_command(session_id=session_id, action=action, scheduled_at=_now_iso(), idempotency_key=f"session:{session_id}:{action}", created_by=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": command} if command else {"code": -1, "msg": "命令创建失败"}


@app.post("/api/case-sessions/{session_id}/reschedule", summary="重新排期未执行办案会话", tags=["案件"])
async def post_case_session_reschedule(session_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    planned_start_at = _parse_planned_time(body.get("planned_start_at"))
    planned_end_at = _parse_planned_time(body.get("planned_end_at"))
    if not planned_start_at or not planned_end_at or planned_end_at <= planned_start_at or planned_start_at <= _now_iso():
        return {"code": -1, "msg": "请设置未来的开始时间与晚于开始时间的结束时间"}
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    updated = db_reschedule_case_session(session_id=session_id, planned_start_at=planned_start_at, planned_end_at=planned_end_at, actor=actor)
    if not updated:
        return {"code": -1, "msg": "仅未开始的办案会话可以重新排期"}
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    db_create_case_device_command(session_id=session_id, action="start", scheduled_at=planned_start_at, idempotency_key=f"session:{session_id}:reschedule:{version}:start", created_by=actor)
    db_create_case_device_command(session_id=session_id, action="stop", scheduled_at=planned_end_at, idempotency_key=f"session:{session_id}:reschedule:{version}:stop", created_by=actor)
    return {"code": 0, "data": updated}


@app.post("/api/case-sessions/{session_id}/status", summary="更新办案会话状态", tags=["案件"])
async def post_case_session_status(session_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    status = str(body.get("status") or "").strip()
    occurred_at = str(body.get("occurred_at") or "").strip() or None
    if status not in CASE_SESSION_STATUSES:
        return {"code": -1, "msg": "会话状态无效"}
    session = db_get_case_session(session_id=session_id)
    if not session:
        return {"code": -1, "msg": "办案会话不存在"}
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    updated = db_update_case_session_status(session_id=session_id, status=status, occurred_at=occurred_at, actor=actor)
    if status == "ended" and (updated or session["status"] == "ended"):
        db_complete_case_assignment_if_ready(session_id=session_id, actor=actor)
        return {"code": 0, "data": updated or db_get_case_session(session_id=session_id)}
    return {"code": 0, "data": updated} if updated else {"code": -1, "msg": "办案会话状态不允许逆向流转"}


@app.post("/api/device/case-sessions/{session_id}/status", summary="设备回执办案会话状态", tags=["案件"])
async def post_device_case_session_status(session_id: int, request: Request, access_key: str = Header(..., alias="X-Device-Access-Key")):
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    status = str(body.get("status") or "").strip()
    occurred_at = str(body.get("occurred_at") or "").strip() or None
    session = db_get_case_session(session_id=session_id)
    if not session or session["device_id"] != device_id or status not in {"active", "ended"} or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证、会话归属或状态无效"}
    assignment = next((item for item in db_list_case_assignments(case_id=int(session["case_id"])) if item["device_id"] == device_id), None)
    if not assignment or assignment["status"] not in {"received", "handling"}:
        return {"code": -1, "msg": "设备未处于可办案状态"}
    now = _now_iso()
    if status == "active" and session.get("planned_start_at") and now < session["planned_start_at"]:
        return {"code": -1, "msg": "未到计划开始时间，设备不能启动办案会话"}
    if status == "active" and session.get("planned_end_at") and now >= session["planned_end_at"]:
        return {"code": -1, "msg": "已超过计划结束时间，请由平台重新排期"}
    if status == "active" and assignment["status"] == "received":
        db_update_case_assignment_status(assignment_id=int(assignment["id"]), status="handling", actor=f"device:{device_id}")
    actor = f"device:{device_id}"
    updated = db_update_case_session_status(session_id=session_id, status=status, occurred_at=occurred_at, actor=actor)
    if status == "ended" and (updated or session["status"] == "ended"):
        db_complete_case_assignment_if_ready(session_id=session_id, actor=actor)
        return {"code": 0, "data": updated or db_get_case_session(session_id=session_id)}
    return {"code": 0, "data": updated} if updated else {"code": -1, "msg": "办案会话状态不允许逆向流转"}


@app.get("/api/case-sessions/{session_id}/transcripts", summary="获取会话笔录", tags=["案件"])
async def get_session_transcripts(session_id: int):
    if not db_get_case_session(session_id=session_id):
        return {"code": -1, "msg": "办案会话不存在"}
    return {"code": 0, "data": db_list_case_transcripts(session_id=session_id)}


@app.post("/api/case-sessions/{session_id}/transcripts", summary="创建会话笔录", tags=["案件"])
async def post_case_transcript(session_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    if not ENABLE_PLATFORM_TIPTAP:
        return {"code": -1, "msg": "平台网页笔录已停用，请在办案设备端创建和完成笔录"}
    body = await request.json()
    title = str(body.get("title") or "").strip()
    transcript_type = str(body.get("transcript_type") or "interrogation").strip()
    template_key = str(body.get("template_key") or transcript_type).strip()
    editor_type = str(body.get("editor_type") or "tiptap").strip()
    builtin_template = BUILTIN_TIPTAP_TEMPLATES.get(template_key)
    template = db_get_case_transcript_template(template_key=template_key) if template_key not in TRANSCRIPT_TEMPLATES and not builtin_template else None
    if not title or len(title) > 160 or transcript_type not in TRANSCRIPT_TYPES or editor_type != "tiptap" or (template_key not in TRANSCRIPT_TEMPLATES and not builtin_template and not template):
        return {"code": -1, "msg": "笔录名称或类型不合法"}
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    created = db_create_case_transcript(session_id=session_id, title=title, transcript_type=transcript_type, template_key=template_key, editor_type=editor_type, created_by=actor)
    if created:
        content = _default_transcript_content(created)
        if template:
            try:
                content = _materialize_transcript_template(_normalize_tiptap_content(json.loads(str(template["content_json"]))), created)
            except (ValueError, TypeError, json.JSONDecodeError):
                return {"code": -1, "msg": "导入笔录模板已损坏"}
        elif builtin_template:
            content = _materialize_transcript_template(_normalize_tiptap_content(builtin_template["content"]), created)
        db_save_case_transcript_draft(transcript_id=int(created["id"]), content_json=json.dumps(content, ensure_ascii=False, separators=(",", ":")), actor=actor)
        created = db_get_case_transcript(transcript_id=int(created["id"]))
    return {"code": 0, "data": created} if created else {"code": -1, "msg": "办案会话不存在"}


@app.get("/api/transcript-templates", summary="获取在线笔录模板", tags=["案件"])
async def get_transcript_templates():
    if not ENABLE_PLATFORM_TIPTAP:
        return {"code": -1, "msg": "平台网页笔录已停用，请使用设备端笔录模板"}
    return {"code": 0, "data": _transcript_template_options()}


@app.get("/api/transcript-templates/{template_key}/preview", summary="预览内置网页笔录模板", tags=["案件"])
async def get_transcript_template_preview(template_key: str):
    template = BUILTIN_TIPTAP_TEMPLATES.get(template_key)
    if not template:
        return {"code": -1, "msg": "仅支持预览内置 Tiptap 模板"}
    content = _preview_tiptap_template(_normalize_tiptap_content(template["content"]))
    return {"code": 0, "data": {"name": template["name"], "content": content}}


@app.post("/api/transcript-templates", summary="导入在线笔录模板", tags=["案件"])
async def post_transcript_template(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "仅管理员可导入笔录模板"}
    if not ENABLE_PLATFORM_TIPTAP:
        return {"code": -1, "msg": "平台 JSON 笔录模板已停用，请在设备端管理 DOCX 模板"}
    body = await request.json()
    template_key = str(body.get("template_key") or "").strip()
    name = str(body.get("name") or "").strip()
    transcript_type = str(body.get("transcript_type") or "other").strip()
    raw_content = body.get("content")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", template_key) or template_key in TRANSCRIPT_TEMPLATES or not name or len(name) > 80 or transcript_type not in TRANSCRIPT_TYPES:
        return {"code": -1, "msg": "模板标识、名称或笔录类型不合法"}
    try:
        content = _normalize_tiptap_content(json.loads(raw_content) if isinstance(raw_content, str) else raw_content)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return {"code": -1, "msg": f"模板 JSON 无效：{error}"}
    saved = db_upsert_case_transcript_template(template_key=template_key, name=name, transcript_type=transcript_type, content_json=json.dumps(content, ensure_ascii=False, separators=(",", ":")), actor=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": saved}


@app.post("/api/transcript-templates/docx", summary="导入 DOCX 笔录模板", tags=["案件"])
async def post_transcript_template_docx(request: Request, file: UploadFile = File(...), template_key: str = Form(...), name: str = Form(""), transcript_type: str = Form("other")):
    if not _is_admin(request):
        return {"code": 403, "msg": "仅管理员可导入笔录模板"}
    key = template_key.strip()
    title = name.strip() or Path(file.filename or "").stem.strip()
    kind = transcript_type.strip()
    if not (file.filename or "").lower().endswith(".docx"):
        return {"code": -1, "msg": "仅支持 DOCX 格式笔录模板"}
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", key) or key in TRANSCRIPT_TEMPLATES or not title or len(title) > 80 or kind not in TRANSCRIPT_TYPES:
        return {"code": -1, "msg": "模板标识、名称或笔录类型不合法"}
    try:
        payload = await file.read()
        content = _docx_template_content(payload)
    except ValueError as error:
        return {"code": -1, "msg": str(error)}
    digest = hashlib.sha256(payload).hexdigest()
    source_name = Path(file.filename or f"{title}.docx").name
    if not source_name.lower().endswith(".docx"):
        return {"code": -1, "msg": "DOCX 模板文件名不合法"}
    stored_name = f"{key}-{digest[:16]}.docx"
    TRANSCRIPT_TEMPLATE_ROOT.mkdir(parents=True, exist_ok=True)
    (TRANSCRIPT_TEMPLATE_ROOT / stored_name).write_bytes(payload)
    saved = db_upsert_case_transcript_template(template_key=key, name=title, transcript_type=kind, content_json=json.dumps(content, ensure_ascii=False, separators=(",", ":")), actor=str((_request_user(request) or {}).get("username", "unknown")), source_docx_name=source_name, source_docx_path=stored_name, source_docx_sha256=digest)
    return {"code": 0, "data": saved}


@app.get("/api/transcripts/{transcript_id}/editor", summary="获取在线笔录编辑内容", tags=["案件"])
async def get_case_transcript_editor(transcript_id: int):
    transcript = db_get_case_transcript(transcript_id=transcript_id)
    if not transcript or transcript.get("editor_type") != "tiptap":
        return {"code": -1, "msg": "网页笔录不存在"}
    try:
        content = _normalize_tiptap_content(json.loads(str(transcript["draft_content_json"])))
    except (ValueError, TypeError, json.JSONDecodeError):
        content = _default_transcript_content(transcript)
    return {"code": 0, "data": {"transcript": transcript, "content": content, "quality_issues": _transcript_quality_issues(transcript, content), "templates": _transcript_template_options()}}


@app.put("/api/transcripts/{transcript_id}/content", summary="保存在线笔录草稿", tags=["案件"])
async def put_case_transcript_content(transcript_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    transcript = db_get_case_transcript(transcript_id=transcript_id)
    if not transcript or transcript.get("editor_type") != "tiptap":
        return {"code": -1, "msg": "网页笔录不存在"}
    body = await request.json()
    try:
        content = _normalize_tiptap_content(body.get("content"))
    except ValueError as error:
        return {"code": -1, "msg": str(error)}
    updated = db_save_case_transcript_draft(transcript_id=transcript_id, content_json=json.dumps(content, ensure_ascii=False, separators=(",", ":")), actor=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": updated} if updated else {"code": -1, "msg": "笔录不存在或已定稿"}


@app.post("/api/transcripts/{transcript_id}/publish", summary="生成在线笔录版本或定稿", tags=["案件"])
async def post_publish_case_transcript(transcript_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    transcript = db_get_case_transcript(transcript_id=transcript_id)
    if not transcript or transcript.get("editor_type") != "tiptap" or transcript["status"] == "finalized":
        return {"code": -1, "msg": "笔录不存在或已定稿"}
    try:
        content = _normalize_tiptap_content(json.loads(str(transcript["draft_content_json"])))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"code": -1, "msg": "笔录草稿损坏"}
    if bool(body.get("finalize")):
        quality_issues = _transcript_quality_issues(transcript, content)
        if quality_issues:
            return {"code": -1, "msg": "笔录尚未满足定稿要求", "data": {"issues": quality_issues}}
    document = _transcript_pdf_bytes(transcript, content)
    digest = hashlib.sha256(document).hexdigest()
    next_version = int(transcript["current_version"]) + 1
    original_name = f"{transcript['session_no']}-{transcript['title']}-V{next_version}.pdf"[:240]
    stored_name = f"{uuid.uuid4().hex}.pdf"
    try:
        target = _archive_storage_path(str(transcript["device_id"]), stored_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(document)
        archive = db_create_archive_file(device_id=str(transcript["device_id"]), case_id=int(transcript["case_id"]), session_id=int(transcript["session_id"]), folder_id=None, archive_type="transcript", status="closed", title=str(transcript["title"]), original_name=original_name, stored_name=stored_name, file_size=len(document), content_type="application/pdf", sha256=digest, uploaded_by=actor)
        versioned = db_add_case_transcript_version(transcript_id=transcript_id, archive_id=int((archive or {})["id"]), content_hash=digest, note=str(body.get("note") or "在线笔录版本")[:500], created_by=actor) if archive else None
    except OSError:
        return {"code": -1, "msg": "笔录版本归档失败"}
    if not versioned:
        target.unlink(missing_ok=True)
        return {"code": -1, "msg": "笔录版本生成失败"}
    if bool(body.get("finalize")):
        versioned = db_finalize_case_transcript(transcript_id=transcript_id, actor=actor) or versioned
    return {"code": 0, "data": versioned}


@app.post("/api/transcripts/{transcript_id}/versions", summary="保存笔录版本", tags=["案件"])
async def post_case_transcript_version(transcript_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    try:
        archive_id = int(body.get("archive_id"))
    except (TypeError, ValueError):
        return {"code": -1, "msg": "笔录文件无效"}
    archive = db_get_archive_file(archive_id=archive_id)
    content_hash = str(body.get("content_hash") or (archive or {}).get("sha256") or "").strip().lower()
    note = str(body.get("note") or "").strip()[:500]
    if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
        return {"code": -1, "msg": "笔录版本必须提供 SHA-256"}
    updated = db_add_case_transcript_version(transcript_id=transcript_id, archive_id=archive_id, content_hash=content_hash, note=note, created_by=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": updated} if updated else {"code": -1, "msg": "笔录已定稿，或文件未绑定到同一办案会话"}


@app.post("/api/transcripts/{transcript_id}/finalize", summary="定稿笔录", tags=["案件"])
async def post_finalize_case_transcript(transcript_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    finalized = db_finalize_case_transcript(transcript_id=transcript_id, actor=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": finalized} if finalized else {"code": -1, "msg": "笔录不存在、尚无版本或已经定稿"}


@app.get("/api/transcripts/{transcript_id}/onlyoffice/config", summary="获取 OnlyOffice 笔录配置", tags=["案件"])
async def get_onlyoffice_config(transcript_id: int, request: Request):
    if not ENABLE_ONLYOFFICE:
        return {"code": -1, "msg": "OnlyOffice 功能已停用"}
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    if not ONLYOFFICE_JWT_SECRET:
        return {"code": -1, "msg": "OnlyOffice 未配置 JWT 密钥"}
    transcript = db_get_case_transcript(transcript_id=transcript_id)
    if not transcript or transcript.get("editor_type") != "onlyoffice":
        return {"code": -1, "msg": "OnlyOffice 笔录不存在"}
    draft = _onlyoffice_draft_path(transcript_id)
    if not draft.exists():
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_bytes(_onlyoffice_docx_bytes(transcript))
    expires = int(time.time()) + 600
    signature = _onlyoffice_document_signature(transcript_id, expires)
    document_url = f"{ONLYOFFICE_PLATFORM_URL}/api/onlyoffice/transcripts/{transcript_id}/document?expires={expires}&signature={signature}"
    user = _request_user(request) or {}
    configuration = {"documentType": "word", "document": {"fileType": "docx", "key": f"streamui-{transcript_id}-{int(draft.stat().st_mtime_ns)}", "title": f"{transcript['title']}.docx", "url": document_url, "permissions": {"edit": transcript["status"] != "finalized", "download": True, "print": True}}, "editorConfig": {"mode": "edit" if transcript["status"] != "finalized" else "view", "lang": "zh-CN", "callbackUrl": f"{ONLYOFFICE_PLATFORM_URL}/api/onlyoffice/transcripts/{transcript_id}/callback", "user": {"id": str(user.get("id", "unknown")), "name": str(user.get("full_name") or user.get("username") or "办案人员")}, "customization": {"forcesave": True}}}
    configuration["token"] = _onlyoffice_token(configuration)
    return {"code": 0, "data": {"document_server_url": ONLYOFFICE_DOCUMENT_SERVER_URL, "config": configuration, "transcript": transcript}}


@app.get("/api/onlyoffice/demo/config", summary="获取 OnlyOffice 模板预览配置", tags=["案件"])
async def get_onlyoffice_demo_config(request: Request):
    if not ENABLE_ONLYOFFICE:
        return {"code": -1, "msg": "OnlyOffice 功能已停用"}
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    if not ONLYOFFICE_JWT_SECRET:
        return {"code": -1, "msg": "OnlyOffice 未配置 JWT 密钥"}
    filename = "讯问模板.docx"
    expires = int(time.time()) + 600
    signature = _onlyoffice_demo_document_signature(expires)
    document_url = f"{ONLYOFFICE_PLATFORM_URL}/api/onlyoffice/demo/document?expires={expires}&signature={signature}"
    user = _request_user(request) or {}
    configuration = {"documentType": "word", "document": {"fileType": "docx", "key": "streamui-onlyoffice-template-preview", "title": filename, "url": document_url, "permissions": {"edit": False, "download": False, "print": True}}, "editorConfig": {"mode": "view", "lang": "zh-CN", "user": {"id": str(user.get("id", "unknown")), "name": str(user.get("full_name") or user.get("username") or "办案人员")}}}
    configuration["token"] = _onlyoffice_token(configuration)
    return {"code": 0, "data": {"document_server_url": ONLYOFFICE_DOCUMENT_SERVER_URL, "config": configuration}}


@app.get("/api/onlyoffice/demo/document", summary="下载 OnlyOffice 模板预览文件", tags=["案件"])
async def get_onlyoffice_demo_document(expires: int, signature: str):
    if not ENABLE_ONLYOFFICE:
        return {"code": -1, "msg": "OnlyOffice 功能已停用"}
    if expires < int(time.time()) or not hmac.compare_digest(signature, _onlyoffice_demo_document_signature(expires)):
        return {"code": 403, "msg": "预览文档链接无效或已过期"}
    filename = "讯问模板.docx"
    document_path = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "onlyoffice-demo" / filename
    if not document_path.is_file() or not document_path.read_bytes().startswith(b"PK"):
        return {"code": -1, "msg": "模板文件不可用"}
    return FileResponse(document_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=filename, content_disposition_type="inline")


@app.get("/api/onlyoffice/transcripts/{transcript_id}/document", summary="OnlyOffice 下载笔录 DOCX", tags=["案件"])
async def get_onlyoffice_document(transcript_id: int, expires: int, signature: str):
    if not ENABLE_ONLYOFFICE:
        return {"code": -1, "msg": "OnlyOffice 功能已停用"}
    if expires < int(time.time()) or not hmac.compare_digest(signature, _onlyoffice_document_signature(transcript_id, expires)):
        return {"code": 403, "msg": "文档访问链接无效或已过期"}
    transcript = db_get_case_transcript(transcript_id=transcript_id)
    draft = _onlyoffice_draft_path(transcript_id)
    if not transcript or not draft.is_file():
        return {"code": -1, "msg": "笔录文件不存在"}
    return FileResponse(draft, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=f"{transcript['title']}.docx")


@app.post("/api/onlyoffice/transcripts/{transcript_id}/callback", summary="OnlyOffice 保存笔录回调", tags=["案件"])
async def post_onlyoffice_callback(transcript_id: int, request: Request, authorization: str = Header("")):
    if not ENABLE_ONLYOFFICE:
        return {"error": 1}
    body = await request.json()
    token = authorization.removeprefix("Bearer ").strip() or str(body.get("token") or "")
    claims = _verify_onlyoffice_token(token)
    if not claims or claims.get("key") != body.get("key") or claims.get("url") != body.get("url") or claims.get("status") != body.get("status") or not str(body.get("key") or "").startswith(f"streamui-{transcript_id}-"):
        return {"error": 1}
    transcript = db_get_case_transcript(transcript_id=transcript_id)
    status = int(body.get("status") or 0)
    if not transcript or transcript.get("editor_type") != "onlyoffice" or transcript["status"] == "finalized":
        return {"error": 1}
    if status not in {2, 6} or not body.get("url"):
        return {"error": 0}
    try:
        document_url = urlparse(str(body["url"]))
        if document_url.scheme not in {"http", "https"} or not document_url.hostname or document_url.hostname.lower() not in ONLYOFFICE_CALLBACK_HOSTS:
            raise ValueError("OnlyOffice 保存地址不受信任")
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as onlyoffice_client:
            response = await onlyoffice_client.get(str(body["url"]))
            response.raise_for_status()
            document = response.content
        if not document.startswith(b"PK") or len(document) > MAX_ARCHIVE_FILE_SIZE:
            raise ValueError("OnlyOffice 返回的 DOCX 无效")
        draft = _onlyoffice_draft_path(transcript_id)
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_bytes(document)
        users = body.get("users") if isinstance(body.get("users"), list) else []
        actor = f"onlyoffice:{users[-1]}" if users else "onlyoffice"
        saved = _save_onlyoffice_version(transcript, document, actor, "OnlyOffice 自动保存" if status == 2 else "OnlyOffice 强制保存")
        if not saved:
            raise ValueError("OnlyOffice 版本归档失败")
        db_save_case_transcript_draft(transcript_id=transcript_id, content_json=str(transcript["draft_content_json"]), actor=actor)
    except (httpx.HTTPError, OSError, ValueError):
        return {"error": 1}
    return {"error": 0}


@app.post("/api/case-sessions/{session_id}/media", summary="登记同步音视频材料", tags=["案件"])
async def post_case_media_asset(session_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    media_type = str(body.get("media_type") or "").strip()
    source_stream = str(body.get("source_stream") or "").strip()[:256]
    sha256 = str(body.get("sha256") or "").strip().lower()
    archive_value = body.get("archive_id")
    try:
        archive_id = int(archive_value) if archive_value not in (None, "") else None
    except (TypeError, ValueError):
        return {"code": -1, "msg": "音视频文件无效"}
    if media_type not in MEDIA_TYPES or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        return {"code": -1, "msg": "音视频类型或 SHA-256 无效"}
    created = db_create_case_media_asset(session_id=session_id, archive_id=archive_id, media_type=media_type, source_stream=source_stream, started_at=str(body.get("started_at") or "").strip() or None, ended_at=str(body.get("ended_at") or "").strip() or None, sha256=sha256, created_by=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": created} if created else {"code": -1, "msg": "音视频文件与办案会话不匹配"}


def _recording_file_path(recording_path: str) -> Path:
    root = RECORD_ROOT.resolve()
    target = (root / recording_path).resolve()
    if root not in target.parents or target.suffix.lower() != ".mp4":
        raise ValueError("录像路径无效")
    return target


def _recording_directory_path(app: str, stream: str, date: str | None = None) -> Path:
    root = RECORD_ROOT.resolve()
    target = (root / app / stream).resolve()
    if root not in target.parents:
        raise ValueError("录像目录无效")
    if date is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("录像日期无效")
        target = (target / date).resolve()
        if root not in target.parents:
            raise ValueError("录像目录无效")
    return target


def _file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@app.post("/api/case-sessions/{session_id}/recordings", summary="绑定办案会话录像片段", tags=["案件"])
async def post_case_recording_binding(session_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    session = db_get_case_session(session_id=session_id)
    if not session or session["status"] not in {"active", "ended"}:
        return {"code": -1, "msg": "办案会话不存在或尚未开始"}
    body = await request.json()
    recording_path = str(body.get("recording_path") or "").strip().replace("\\", "/")
    try:
        file_path = _recording_file_path(recording_path)
        relative = file_path.relative_to(RECORD_ROOT.resolve()).as_posix()
        parts = relative.split("/")
        if len(parts) < 4:
            raise ValueError("录像路径层级无效")
        app_name, stream_name = parts[0], parts[1]
        if not file_path.is_file():
            raise ValueError("录像文件不存在")
    except ValueError as error:
        return {"code": -1, "msg": str(error)}
    channel = next((item for item in db_list_channels(device_id=str(session["device_id"])) if item.get("app") == app_name and item.get("stream") == stream_name), None)
    if not channel:
        return {"code": -1, "msg": "录像流不属于该办案会话设备"}
    started_at = str(body.get("started_at") or "").strip()
    ended_at = str(body.get("ended_at") or "").strip()
    if not started_at or not ended_at:
        return {"code": -1, "msg": "必须提供录像片段起止时间"}
    file_hash = _file_sha256(file_path)
    created = db_create_case_recording_binding(session_id=session_id, app=app_name, stream=stream_name, recording_path=relative, started_at=started_at, ended_at=ended_at, sha256=file_hash, integrity_status="verified", created_by=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": created} if created else {"code": -1, "msg": "录像片段已绑定或会话不存在"}


@app.get("/api/cases/{case_id}/assignments", summary="获取案件下发任务", tags=["案件"])
async def get_case_assignments(case_id: int):
    if not db_get_case(case_id=case_id):
        return {"code": -1, "msg": "案件不存在"}
    return {"code": 0, "data": db_list_case_assignments(case_id=case_id)}


@app.post("/api/cases/{case_id}/assignments", summary="向设备下发案件", tags=["案件"])
async def post_case_assignment(case_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    if not db_get_case(case_id=case_id):
        return {"code": -1, "msg": "案件不存在"}
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    device = db_get_device(device_id=device_id)
    if not device:
        return {"code": -1, "msg": "设备不存在"}
    if not device.get("enabled"):
        return {"code": -1, "msg": "设备接入未启用，不能下发案件"}
    assignment = db_assign_case_to_device(case_id=case_id, device_id=device_id, assigned_by=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": assignment}


@app.get("/api/device/cases", summary="设备获取下发案件", tags=["案件"])
async def get_device_cases(device_id: str = Query(...), access_key: str = Header(..., alias="X-Device-Access-Key")):
    device = db_get_device(device_id=device_id)
    if not device or not device.get("enabled") or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    assignments = [item for item in db_list_case_assignments(device_id=device_id) if item["status"] != "completed" and item["case_status"] not in {"closed", "archived"}]
    return {"code": 0, "data": assignments}


@app.get("/api/device/transcript-templates", summary="设备获取平台 DOCX 笔录模板清单", tags=["案件"])
async def get_device_transcript_templates(device_id: str = Query(...), access_key: str = Header(..., alias="X-Device-Access-Key")):
    device = db_get_device(device_id=device_id)
    if not device or not device.get("enabled") or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    templates = []
    for template in db_list_case_transcript_templates():
        source_path = _transcript_template_docx_path(template)
        source_name = str(template.get("source_docx_name") or "")
        digest = str(template.get("source_docx_sha256") or "")
        if source_path and source_name and re.fullmatch(r"[0-9a-f]{64}", digest):
            templates.append({"template_key": template["template_key"], "name": template["name"], "transcript_type": template["transcript_type"], "file_name": source_name, "sha256": digest, "updated_at": template["updated_at"]})
    return {"code": 0, "data": templates}


@app.get("/api/device/transcript-templates/{template_key}/download", summary="设备下载平台 DOCX 笔录模板", tags=["案件"])
async def download_device_transcript_template(template_key: str, device_id: str = Query(...), access_key: str = Header(..., alias="X-Device-Access-Key")):
    device = db_get_device(device_id=device_id)
    if not device or not device.get("enabled") or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    template = db_get_case_transcript_template(template_key=template_key)
    source_path = _transcript_template_docx_path(template or {})
    if not template or not source_path:
        return {"code": -1, "msg": "平台 DOCX 模板不存在"}
    return FileResponse(source_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=str(template.get("source_docx_name") or source_path.name))


@app.post("/api/device/cases/{case_id}/delete", summary="设备管理员删除已下发案件", tags=["案件"])
async def post_device_delete_case(case_id: int, request: Request, access_key: str = Header(..., alias="X-Device-Access-Key")):
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    if not device_id or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    case = db_get_case(case_id=case_id)
    if not case or not any(item["device_id"] == device_id for item in db_list_case_assignments(case_id=case_id)):
        return {"code": -1, "msg": "案件不存在或未下发至本设备"}
    return {"code": 0, "data": {"case_id": case_id}} if db_delete_case(case_id=case_id) else {"code": -1, "msg": "案件删除失败"}


@app.post("/api/device/offline-cases", summary="设备上报离线办案案件", tags=["案件"])
async def post_device_offline_case(request: Request, access_key: str = Header(..., alias="X-Device-Access-Key")):
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    device = db_get_device(device_id=device_id)
    if not device or not device.get("enabled") or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    case_no = str(body.get("case_no") or "").strip()
    name = str(body.get("name") or "").strip()
    if not case_no or not name or len(case_no) > 64 or len(name) > 160 or any(part in case_no for part in ("/", "\\", "..")):
        return {"code": -1, "msg": "离线案件编号或名称不合法"}
    case_category = str(body.get("case_category") or "other").strip()
    if case_category == "talk":
        case_category = "other"
    if case_category not in CASE_SESSION_TYPES:
        case_category = "other"
    case = db_get_case_by_no(case_no=case_no)
    actor = f"device:{device_id}:offline"
    if not case:
        case = db_create_case(
            case_no=case_no, name=name, case_type=str(body.get("case_type") or "other") if str(body.get("case_type") or "other") in CASE_TYPES else "other",
            case_reference=str(body.get("case_reference") or "").strip(), case_category=case_category,
            handling_unit=str(body.get("handling_unit") or "").strip(), case_reason=str(body.get("case_reason") or "").strip(),
            lead_investigator=str(body.get("lead_investigator") or "").strip(), incident_at=str(body.get("incident_at") or "").strip(),
            arrival_method=str(body.get("arrival_method") or "").strip(), interviewer_one_unit=str(body.get("interviewer_one_unit") or "").strip(),
            interviewer_two=str(body.get("interviewer_two") or "").strip(), interviewer_two_unit=str(body.get("interviewer_two_unit") or "").strip(),
            recorder_name=str(body.get("recorder_name") or "").strip(), subject_name=str(body.get("subject_name") or "").strip(),
            interview_location=str(body.get("interview_location") or "").strip(), inquiry_count=max(1, min(99, int(body.get("inquiry_count") or 1))),
            transcript_template=str(body.get("transcript_template") or "").strip(), planned_start_at=str(body.get("planned_start_at") or "").strip(),
            planned_end_at=str(body.get("planned_end_at") or "").strip(), created_by=actor,
        )
        if not case:
            return {"code": -1, "msg": "离线案件创建失败"}
    assignment = db_assign_case_to_device(case_id=int(case["id"]), device_id=device_id, assigned_by=actor)
    if assignment and assignment["status"] == "pending":
        db_update_case_assignment_status(assignment_id=int(assignment["id"]), status="received", actor=actor)
    sessions = [item for item in db_list_case_sessions(case_id=int(case["id"])) if item["device_id"] == device_id]
    session = sessions[0] if sessions else db_create_case_session(
        case_id=int(case["id"]), device_id=device_id, room_id=None,
        session_no=str(body.get("session_no") or f"{case_no}-OFFLINE-1")[:128], session_type=case_category,
        recording_mode="disk", planned_start_at=None, planned_end_at=None,
        location=str(body.get("interview_location") or "").strip(), host_name="", participant_summary="离线办案",
        subject_name=str(body.get("subject_name") or "").strip(),
        interviewer_names="、".join(item for item in (str(body.get("lead_investigator") or "").strip(), str(body.get("interviewer_two") or "").strip()) if item),
        recorder_name=str(body.get("recorder_name") or "").strip(), created_by=actor,
    )
    if not session:
        return {"code": -1, "msg": "离线办案会话创建失败"}
    return {"code": 0, "data": {"case_id": int(case["id"]), "session_id": int(session["id"]), "case_no": case["case_no"], "source": "offline"}}


@app.get("/api/device/case-history", summary="设备获取历史下发案件", tags=["案件"])
async def get_device_case_history(device_id: str = Query(...), access_key: str = Header(..., alias="X-Device-Access-Key")):
    device = db_get_device(device_id=device_id)
    if not device or not device.get("enabled") or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    assignments = db_list_case_assignments(device_id=device_id)[:100]
    for assignment in assignments:
        device_sessions = [item for item in db_list_case_sessions(case_id=int(assignment["case_id"])) if item["device_id"] == device_id]
        assignment["session_count"] = len(device_sessions)
        if device_sessions:
            latest_session = device_sessions[0]
            assignment["latest_session_no"] = latest_session["session_no"]
            assignment["latest_session_status"] = latest_session["status"]
            assignment["latest_session_type"] = latest_session["session_type"]
            assignment["latest_recording_mode"] = latest_session["recording_mode"]
            assignment["latest_session_started_at"] = latest_session.get("started_at")
            assignment["latest_session_ended_at"] = latest_session.get("ended_at")
            assignment["latest_planned_start_at"] = latest_session.get("planned_start_at")
            assignment["latest_planned_end_at"] = latest_session.get("planned_end_at")
            assignment["latest_session_location"] = latest_session.get("location")
            assignment["latest_subject_name"] = latest_session.get("subject_name")
            assignment["latest_interviewer_names"] = latest_session.get("interviewer_names")
            assignment["latest_recorder_name"] = latest_session.get("recorder_name")
    return {"code": 0, "data": assignments}


@app.get("/api/device/case-sessions", summary="设备获取可处理办案会话", tags=["案件"])
async def get_device_case_sessions(device_id: str = Query(...), access_key: str = Header(..., alias="X-Device-Access-Key")):
    device = db_get_device(device_id=device_id)
    if not device or not device.get("enabled") or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    sessions = []
    for assignment in db_list_case_assignments(device_id=device_id):
        if assignment["status"] not in {"received", "handling"} or assignment["case_status"] in {"closed", "archived"}:
            continue
        sessions.extend(session for session in db_list_case_sessions(case_id=int(assignment["case_id"])) if session["device_id"] == device_id and session["status"] in {"planned", "active", "finalizing"})
    return {"code": 0, "data": sessions}


REMOTE_HEARING_DEVICE_STATES = {"ready", "running", "ended", "failed"}


def _remote_hearing_media_payload(task: dict, device_id: str) -> dict | None:
    if not REMOTE_HEARING_RTMP_BASE:
        return None
    participant = next((item for item in task.get("participants", []) if item["device_id"] == device_id), None)
    peer = next((item for item in task.get("participants", []) if item["device_id"] != device_id), None)
    if not participant or not peer:
        return None
    app = str(task.get("media_app") or "hearing")
    prefix = str(task["stream_prefix"])
    own_stream = f"{prefix}_{participant['role']}"
    peer_stream = f"{prefix}_{peer['role']}"
    return {
        "role": participant["role"],
        "peer_device_id": peer["device_id"],
        "publish_url": f"{REMOTE_HEARING_RTMP_BASE}/{app}/{own_stream}",
        "pull_url": f"{REMOTE_HEARING_RTMP_BASE}/{app}/{peer_stream}",
        "stream_app": app,
        "publish_stream": own_stream,
        "pull_stream": peer_stream,
    }


@app.get("/api/remote-hearing-tasks", summary="查询远程提审任务", tags=["远程提审"])
async def get_remote_hearing_tasks(request: Request, case_id: int | None = None):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    return {"code": 0, "data": db_list_remote_hearing_tasks(case_id=case_id)}


@app.get("/api/remote-hearing-tasks/{task_id}", summary="获取远程提审任务", tags=["远程提审"])
async def get_remote_hearing_task(task_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    task = db_get_remote_hearing_task(task_id=task_id)
    return {"code": 0, "data": task} if task else {"code": -1, "msg": "远程提审任务不存在"}


@app.post("/api/remote-hearing-tasks", summary="创建远程提审任务", tags=["远程提审"])
async def post_remote_hearing_task(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    if not REMOTE_HEARING_RTMP_BASE.startswith("rtmp://"):
        return {"code": -1, "msg": "未配置 STREAMUI_REMOTE_HEARING_RTMP_BASE RTMP 汇聚地址"}
    body = await request.json()
    try:
        case_id = int(body.get("case_id"))
    except (TypeError, ValueError):
        return {"code": -1, "msg": "必须关联有效案件"}
    questioning_device_id = str(body.get("questioning_device_id") or "").strip()
    subject_device_id = str(body.get("subject_device_id") or "").strip()
    title = str(body.get("title") or "").strip()
    task_no = str(body.get("task_no") or "").strip() or f"RH-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3).upper()}"
    scheduled_start_at = _parse_planned_time(body.get("scheduled_start_at"))
    scheduled_end_at = _parse_planned_time(body.get("scheduled_end_at"))
    if not db_get_case(case_id=case_id) or not title or len(title) > 160 or not re.fullmatch(r"[A-Za-z0-9_.-]{3,96}", task_no) or not re.fullmatch(r"[A-Za-z0-9_.:-]{3,64}", questioning_device_id) or not re.fullmatch(r"[A-Za-z0-9_.:-]{3,64}", subject_device_id) or questioning_device_id == subject_device_id or (body.get("scheduled_start_at") and not scheduled_start_at) or (body.get("scheduled_end_at") and not scheduled_end_at) or (scheduled_start_at and scheduled_end_at and scheduled_end_at <= scheduled_start_at):
        return {"code": -1, "msg": "任务名称、设备、时间或任务编号不合法"}
    actor = str((_request_user(request) or {}).get("username", "unknown"))
    task = db_create_remote_hearing_task(case_id=case_id, task_no=task_no, title=title, questioning_device_id=questioning_device_id, subject_device_id=subject_device_id, scheduled_start_at=scheduled_start_at, scheduled_end_at=scheduled_end_at, stream_prefix=f"rh_{secrets.token_hex(12)}", created_by=actor)
    return {"code": 0, "data": task} if task else {"code": -1, "msg": "案件或设备不可用，或任务编号重复"}


@app.post("/api/remote-hearing-tasks/{task_id}/{action}", summary="启动、停止或取消远程提审任务", tags=["远程提审"])
async def post_remote_hearing_task_action(task_id: int, action: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    state = {"start": "starting", "stop": "stopping", "cancel": "cancelled"}.get(action)
    if not state:
        return {"code": -1, "msg": "远程提审任务动作无效"}
    task = db_set_remote_hearing_task_state(task_id=task_id, state=state, actor=str((_request_user(request) or {}).get("username", "unknown")))
    return {"code": 0, "data": task} if task else {"code": -1, "msg": "当前任务状态不允许该动作"}


@app.get("/api/device/remote-hearing-tasks", summary="设备获取远程提审任务", tags=["远程提审"])
async def get_device_remote_hearing_tasks(device_id: str = Query(...), access_key: str = Header(..., alias="X-Device-Access-Key")):
    device = db_get_device(device_id=device_id)
    if not device or not device.get("enabled") or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    tasks = []
    for task in db_list_remote_hearing_tasks(device_id=device_id):
        if task["status"] not in {"starting", "active", "stopping"}:
            continue
        detail = db_get_remote_hearing_task(task_id=int(task["id"]))
        media = _remote_hearing_media_payload(detail or {}, device_id)
        if media:
            tasks.append({"id": detail["id"], "task_no": detail["task_no"], "title": detail["title"], "status": detail["status"], "desired_action": "start" if detail["status"] in {"starting", "active"} else "stop", "media": media})
    return {"code": 0, "data": tasks}


@app.post("/api/device/remote-hearing-tasks/{task_id}/status", summary="设备回执远程提审状态", tags=["远程提审"])
async def post_device_remote_hearing_task_status(task_id: int, request: Request, access_key: str = Header(..., alias="X-Device-Access-Key")):
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    status = str(body.get("status") or "").strip()
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
    if status not in REMOTE_HEARING_DEVICE_STATES or len(json.dumps(detail, ensure_ascii=True)) > 4000 or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证或远程提审状态无效"}
    task = db_update_remote_hearing_participant(task_id=task_id, device_id=device_id, status=status, detail=detail)
    return {"code": 0, "data": task} if task else {"code": -1, "msg": "任务不存在、设备不属于任务或状态无效"}


@app.post("/api/device/case-assignments/{assignment_id}/ack", summary="设备回执案件状态", tags=["案件"])
async def post_device_case_ack(assignment_id: int, request: Request, access_key: str = Header(..., alias="X-Device-Access-Key")):
    body = await request.json()
    device_id = str(body.get("device_id") or "").strip()
    status = str(body.get("status") or "received").strip()
    assignment = db_get_case_assignment(assignment_id=assignment_id)
    if not assignment or assignment["device_id"] != device_id:
        return {"code": -1, "msg": "下发任务不存在"}
    if status not in DEVICE_CASE_STATUSES - {"pending"} or not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证或任务状态无效"}
    if status == "completed":
        return {"code": -1, "msg": "案件完成状态由平台在会话证据核验后自动生成"}
    updated = db_update_case_assignment_status(assignment_id=assignment_id, status=status, actor=f"device:{device_id}")
    return {"code": 0, "data": updated} if updated else {"code": -1, "msg": "案件下发状态不允许逆向流转"}


ARCHIVE_TYPES = {"transcript", "document", "audio", "video"}
TRANSCRIPT_STATUSES = {"not_started", "in_progress", "closed"}


def _archive_storage_path(device_id: str, stored_name: str) -> Path:
    root = ARCHIVE_ROOT.resolve()
    target = (root / device_id / stored_name).resolve()
    if root not in target.parents:
        raise ValueError("无效的归档文件路径")
    return target


def _archive_folder_for_device(folder_id: int | None, device_id: str) -> dict | None:
    if folder_id is None:
        return None
    folder = db_get_archive_folder(folder_id=folder_id)
    if not folder or folder["device_id"] != device_id:
        raise ValueError("二级目录不属于所选设备")
    return folder


@app.get("/api/archives/folders", summary="获取设备档案目录", tags=["档案"])
async def get_archive_folders(device_id: str | None = None):
    return {"code": 0, "data": db_list_archive_folders(device_id=device_id)}


@app.post("/api/archives/folders", summary="创建设备档案二级目录", tags=["档案"])
async def post_archive_folder(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    device_id = str(body.get("device_id", "")).strip()
    name = str(body.get("name", "")).strip()
    if not db_get_device(device_id=device_id):
        return {"code": -1, "msg": "设备不存在"}
    if not name or len(name) > 80 or any(part in name for part in ("/", "\\", "..")):
        return {"code": -1, "msg": "二级目录名称不合法"}
    folder = db_create_archive_folder(device_id=device_id, name=name)
    return {"code": 0, "data": folder} if folder else {"code": -1, "msg": "该设备下已存在同名目录"}


@app.get("/api/archives", summary="获取设备档案", tags=["档案"])
async def get_archives(device_id: str | None = None):
    return {"code": 0, "data": db_list_archive_files(device_id=device_id)}


@app.post("/api/archives/upload", summary="上传设备档案", tags=["档案"])
async def post_archive_upload(
    request: Request,
    device_id: str = Form(...),
    access_key: str = Form(""),
    archive_type: str = Form("document"),
    status: str = Form("not_started"),
    title: str = Form(""),
    case_id: str = Form(""),
    session_id: str = Form(""),
    sha256: str = Form(""),
    folder_id: str = Form(""),
    file: UploadFile = File(...),
):
    device_id = device_id.strip()
    current_user = _request_user(request)
    device_key = access_key.strip() or request.headers.get("X-Device-Access-Key", "").strip()
    device_upload = bool(device_key) and db_verify_device_key(device_id=device_id, access_key=device_key)
    if not _can_manage(request) and not device_upload:
        return {"code": 403, "msg": "需要管理员或操作员权限，或有效的设备接入密钥"}
    archive_type = archive_type.strip()
    status = status.strip()
    if not db_get_device(device_id=device_id):
        return {"code": -1, "msg": "设备不存在"}
    if archive_type not in ARCHIVE_TYPES or (archive_type == "transcript" and status not in TRANSCRIPT_STATUSES):
        return {"code": -1, "msg": "档案类型或笔录状态无效"}
    try:
        parsed_case_id = int(case_id) if case_id.strip() else None
        parsed_session_id = int(session_id) if session_id.strip() else None
        if parsed_case_id is not None:
            if not db_get_case(case_id=parsed_case_id) or not any(item["device_id"] == device_id for item in db_list_case_assignments(case_id=parsed_case_id)):
                raise ValueError("案件未下发至该设备")
        if parsed_session_id is not None:
            session = db_get_case_session(session_id=parsed_session_id)
            if not session or parsed_case_id != session["case_id"] or session["device_id"] != device_id:
                raise ValueError("办案会话与案件或设备不匹配")
        if archive_type in {"transcript", "audio", "video"} and parsed_session_id is None:
            raise ValueError("笔录和音视频材料必须关联办案会话")
        parsed_folder_id = int(folder_id) if folder_id.strip() else None
        _archive_folder_for_device(parsed_folder_id, device_id)
    except (ValueError, TypeError) as error:
        return {"code": -1, "msg": str(error) or "案件、会话或二级目录无效"}
    original_name = Path(file.filename or "").name
    if not original_name or len(original_name) > 255:
        return {"code": -1, "msg": "文件名无效"}
    stored_name = f"{uuid.uuid4().hex}{Path(original_name).suffix[:20]}"
    target = _archive_storage_path(device_id, stored_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    digest = hashlib.sha256()
    try:
        with target.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                output.write(chunk)
                digest.update(chunk)
    except (OSError, ValueError) as error:
        target.unlink(missing_ok=True)
        return {"code": -1, "msg": str(error) if isinstance(error, ValueError) else "归档文件写入失败"}
    finally:
        await file.close()
    declared_hash = sha256.strip().lower()
    if declared_hash and (not re.fullmatch(r"[0-9a-f]{64}", declared_hash) or declared_hash != digest.hexdigest()):
        target.unlink(missing_ok=True)
        return {"code": -1, "msg": "归档文件 SHA-256 校验失败"}
    saved = db_create_archive_file(
        device_id=device_id, case_id=parsed_case_id, session_id=parsed_session_id, folder_id=parsed_folder_id, archive_type=archive_type,
        status=status if archive_type == "transcript" else "not_started",
        title=title.strip()[:160] or Path(original_name).stem[:160], original_name=original_name,
        stored_name=stored_name, file_size=size, content_type=file.content_type, sha256=digest.hexdigest(),
        uploaded_by=str(current_user.get("username") if current_user else f"device:{device_id}"),
    )
    if not saved:
        target.unlink(missing_ok=True)
        return {"code": -1, "msg": "归档建档失败，文件未保留"}
    return {"code": 0, "data": saved}


@app.put("/api/archives/{archive_id}", summary="更新设备档案", tags=["档案"])
async def put_archive(archive_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    archive = db_get_archive_file(archive_id=archive_id)
    if not archive:
        return {"code": -1, "msg": "档案不存在"}
    if db_archive_is_immutable(archive_id=archive_id):
        return {"code": -1, "msg": "文件已成为笔录版本或音视频证据，关联源文件不可修改"}
    body = await request.json()
    status = str(body["status"]).strip() if "status" in body else None
    title = str(body["title"]).strip()[:160] if "title" in body else None
    if status is not None and (archive["archive_type"] != "transcript" or status not in TRANSCRIPT_STATUSES):
        return {"code": -1, "msg": "笔录状态无效"}
    try:
        update_folder = "folder_id" in body
        folder_id = int(body["folder_id"]) if body.get("folder_id") not in (None, "") else None
        if update_folder:
            _archive_folder_for_device(folder_id, str(archive["device_id"]))
    except (ValueError, TypeError):
        return {"code": -1, "msg": "二级目录无效"}
    result = db_update_archive_file(archive_id=archive_id, status=status, title=title, folder_id=folder_id, update_folder=update_folder)
    return {"code": 0, "data": result} if result else {"code": -1, "msg": "案件已办结或归档，档案不可修改"}


@app.get("/api/archives/{archive_id}/download", summary="下载设备档案", tags=["档案"])
async def download_archive(archive_id: int, request: Request):
    archive = db_get_archive_file(archive_id=archive_id)
    if not archive:
        return {"code": -1, "msg": "档案不存在"}
    try:
        file_path = _archive_storage_path(str(archive["device_id"]), str(archive["stored_name"]))
    except ValueError:
        return {"code": -1, "msg": "档案路径无效"}
    if not file_path.is_file():
        return {"code": -1, "msg": "归档文件不存在"}
    db_log_case_archive_event(archive_id=archive_id, action="evidence.downloaded", actor=str((_request_user(request) or {}).get("username", "unknown")))
    return FileResponse(file_path, media_type=archive.get("content_type") or "application/octet-stream", filename=str(archive["original_name"]))


@app.get("/api/archives/{archive_id}/preview", summary="在线预览笔录档案", tags=["档案"])
async def preview_transcript_archive(archive_id: int, request: Request):
    archive = db_get_archive_file(archive_id=archive_id)
    if not archive:
        return {"code": -1, "msg": "档案不存在"}
    file_name = str(archive["original_name"])
    suffix = Path(file_name).suffix.lower()
    if suffix not in {".pdf", ".html", ".htm", ".mp4", ".webm", ".mov", ".ogg"}:
        return {"code": -1, "msg": "仅支持在线预览 PDF、HTML 或视频文件"}
    try:
        file_path = _archive_storage_path(str(archive["device_id"]), str(archive["stored_name"]))
    except ValueError:
        return {"code": -1, "msg": "档案路径无效"}
    if not file_path.is_file():
        return {"code": -1, "msg": "归档文件不存在"}
    db_log_case_archive_event(archive_id=archive_id, action="evidence.previewed", actor=str((_request_user(request) or {}).get("username", "unknown")))
    media_type = "application/pdf" if suffix == ".pdf" else "text/html; charset=utf-8" if suffix in {".html", ".htm"} else archive.get("content_type") or "video/mp4"
    return FileResponse(file_path, media_type=media_type, filename=file_name, content_disposition_type="inline")


@app.get("/api/device/archives/{archive_id}/download", summary="设备下载自身档案", tags=["档案"])
async def device_download_archive(archive_id: int, device_id: str = Query(...), access_key: str = Header(..., alias="X-Device-Access-Key")):
    if not db_verify_device_key(device_id=device_id, access_key=access_key):
        return {"code": 403, "msg": "设备认证失败"}
    archive = db_get_archive_file(archive_id=archive_id)
    if not archive or archive["device_id"] != device_id:
        return {"code": -1, "msg": "档案不存在"}
    file_path = _archive_storage_path(device_id, str(archive["stored_name"]))
    if not file_path.is_file():
        return {"code": -1, "msg": "归档文件不存在"}
    db_log_case_archive_event(archive_id=archive_id, action="evidence.downloaded", actor=f"device:{device_id}")
    return FileResponse(file_path, media_type=archive.get("content_type") or "application/octet-stream", filename=str(archive["original_name"]))


@app.delete("/api/archives/{archive_id}", summary="删除设备档案", tags=["档案"])
async def delete_archive(archive_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    archive = db_get_archive_file(archive_id=archive_id)
    if not archive:
        return {"code": -1, "msg": "档案不存在"}
    if db_archive_is_immutable(archive_id=archive_id):
        return {"code": -1, "msg": "文件已成为笔录版本或音视频证据，关联源文件不可删除"}
    db_log_case_archive_event(archive_id=archive_id, action="evidence.delete_requested", actor=str((_request_user(request) or {}).get("username", "unknown")))
    deleted = db_delete_archive_file(archive_id=archive_id)
    if not deleted:
        return {"code": -1, "msg": "案件已办结或归档，档案不可删除"}
    if deleted:
        _archive_storage_path(str(archive["device_id"]), str(archive["stored_name"])).unlink(missing_ok=True)
    return {"code": 0, "deleted": deleted}


@app.get("/api/devices/{device_id}")
async def get_device(device_id: str):
    device = db_get_device(device_id=device_id)
    if not device:
        return {"code": -1, "msg": "设备不存在"}
    device["channels"] = db_list_channels(device_id=device_id)
    return {"code": 0, "data": device}


@app.put("/api/devices/{device_id}/channels")
async def put_device_channel(device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    if not db_get_device(device_id=device_id):
        return {"code": -1, "msg": "设备不存在"}
    try:
        channel_no = int(body["channel_no"])
    except (KeyError, ValueError, TypeError):
        return {"code": -1, "msg": "通道号无效"}
    app = str(body.get("app") or "")
    stream = str(body.get("stream") or "")
    if channel_no < 0 or channel_no > 1024 or (app and not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", app)) or (stream and not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", stream)):
        return {"code": -1, "msg": "通道号、应用名或流 ID 无效"}
    result = db_upsert_channel(device_id=device_id, channel_no=channel_no, name=str(body.get("name") or f"通道 {channel_no}")[:128], vhost=str(body.get("vhost") or "__defaultVhost__"), app=app or None, stream=stream or None, keywords=str(body.get("keywords") or "")[:256])
    return {"code": 0, "data": result}


@app.get("/api/channels")
async def get_channels(device_id: str | None = None):
    return {"code": 0, "data": db_list_channels(device_id=device_id)}


@app.get("/api/gb28181/status", summary="GB28181 SIP 服务状态", tags=["GB28181"])
async def get_gb28181_status(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    status = GB28181_SERVER.status()
    status["devices"] = db_list_gb28181_devices()
    return {"code": 0, "data": status}


@app.post("/api/gb28181/devices/{device_id}/query", summary="查询 GB28181 设备信息", tags=["GB28181"])
async def query_gb28181_device(device_id: str, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    command = str((await request.json()).get("command") or "Catalog").strip()
    try:
        GB28181_SERVER.query_device(device_id=device_id, command=command, sender_host=str(_gb28181_settings(include_password=True).get("media_host") or ""))
    except (RuntimeError, ValueError) as error:
        return {"code": -1, "msg": str(error)}
    return {"code": 0, "msg": f"已发送 {command} 查询"}


@app.get("/api/record-schedules")
async def get_record_schedules():
    return {"code": 0, "data": db_list_record_schedules()}


@app.post("/api/record-schedules")
async def post_record_schedule(request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    body = await request.json()
    try:
        channel_id = int(body["channel_id"])
        retention_days = int(body.get("retention_days", 7))
    except (KeyError, ValueError, TypeError):
        return {"code": -1, "msg": "录像计划参数无效"}
    try:
        weekday_values = {int(day) for day in body.get("weekdays", [0, 1, 2, 3, 4, 5, 6])}
    except (TypeError, ValueError):
        return {"code": -1, "msg": "工作日无效"}
    if not weekday_values or not weekday_values.issubset(set(range(7))) or not any(channel["id"] == channel_id for channel in db_list_channels()):
        return {"code": -1, "msg": "通道或工作日无效"}
    weekdays = ",".join(str(day) for day in sorted(weekday_values))
    start_time, end_time = str(body.get("start_time", "00:00")), str(body.get("end_time", "23:59"))
    if not _valid_time(start_time) or not _valid_time(end_time) or not 1 <= retention_days <= 365:
        return {"code": -1, "msg": "时间或保留天数无效"}
    return {"code": 0, "data": db_upsert_record_schedule(schedule_id=body.get("id"), channel_id=channel_id, weekdays=weekdays, start_time=start_time, end_time=end_time, retention_days=retention_days, enabled=bool(body.get("enabled", True)))}


@app.delete("/api/record-schedules/{schedule_id}")
async def delete_schedule(schedule_id: int, request: Request):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    return {"code": 0, "deleted": db_delete_record_schedule(schedule_id=schedule_id)}


@app.get("/api/video-wall")
async def get_video_wall(request: Request):
    user = _request_user(request) or {}
    owner_username = str(user.get("username"))
    wall = db_get_video_wall(owner_username=owner_username, name="default")
    if wall and wall.get("layout_size") == 64 and not any(
        isinstance(cell, dict) and (cell.get("app") or cell.get("stream"))
        for cell in wall.get("cells", [])
    ):
        wall = db_save_video_wall(
            owner_username=owner_username,
            name="default",
            layout_size=9,
            cells=[],
            polling_seconds=int(wall.get("polling_seconds") or 0),
            enabled=bool(wall.get("enabled", True)),
        )
    return {"code": 0, "data": wall}


@app.put("/api/video-wall")
async def put_video_wall(request: Request):
    user = _request_user(request) or {}
    body = await request.json()
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    try:
        layout_size = int(body.get("layout_size", 9))
        polling_seconds = int(body.get("polling_seconds", 0))
    except (TypeError, ValueError):
        return {"code": -1, "msg": "分屏数量或轮询间隔无效"}
    if layout_size not in {1, 4, 9, 16, 32, 64}:
        return {"code": -1, "msg": "不支持的分屏数量"}
    cells = body.get("cells", [])
    if not isinstance(cells, list):
        return {"code": -1, "msg": "分屏数据无效"}
    return {"code": 0, "data": db_save_video_wall(owner_username=str(user.get("username")), name="default", layout_size=layout_size, cells=cells[:layout_size], polling_seconds=max(0, min(polling_seconds, 3600)), enabled=bool(body.get("enabled", True)))}


async def _add_stream_proxy_to_zlm(
    *,
    vhost: str,
    app: str,
    stream: str,
    url: str,
    audio_type: int | None,
) -> dict:
    query_params = {
        "secret": ZLM_SECRET,
        "vhost": vhost,
        "app": app,
        "stream": stream,
        "url": url,
    }
    query_params.update(_audio_type_to_zlm_params(audio_type))
    try:
        response = await client.get(f"{ZLM_SERVER}/index/api/addStreamProxy", params=query_params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return {"code": -1, "msg": f"ZLMediaKit 请求失败: {error}"}
    if payload.get("code") != 0:
        return {"code": -1, "msg": str(payload.get("msg") or "ZLMediaKit 拒绝创建拉流代理"), "detail": payload}
    return {"code": 0, "data": payload}


async def _del_stream_proxy_from_zlm(*, vhost: str, app: str, stream: str) -> None:
    query_params = {"secret": ZLM_SECRET}
    query_params["key"] = _stream_proxy_key(vhost, app, stream)
    try:
        await client.get(f"{ZLM_SERVER}/index/api/delStreamProxy", params=query_params)
    except Exception:
        return


async def sync_pull_proxies_from_db() -> None:
    rows = db_list_pull_proxies()
    if not rows:
        return

    existing_keys: set[str] = set()
    try:
        query_params = {"secret": ZLM_SECRET}
        response = await client.get(
            f"{ZLM_SERVER}/index/api/listStreamProxy", params=query_params
        )
        raw_data = response.json()
        if raw_data.get("code") == 0:
            for item in raw_data.get("data", []) or []:
                if isinstance(item, dict) and item.get("key"):
                    existing_keys.add(str(item["key"]))
                    continue
                src = (item or {}).get("src") or {}
                vhost = src.get("vhost")
                app = src.get("app")
                stream = src.get("stream")
                if vhost and app and stream:
                    existing_keys.add(_stream_proxy_key(vhost, app, stream))
    except Exception:
        existing_keys = set()

    for row in rows:
        vhost = row["vhost"]
        app = row["app"]
        stream = row["stream"]
        key = _stream_proxy_key(vhost, app, stream)
        if key in existing_keys:
            continue

        query_params = {
            "secret": ZLM_SECRET,
            "vhost": vhost,
            "app": app,
            "stream": stream,
            "url": row["url"],
        }
        query_params.update(_audio_type_to_zlm_params(row.get("audio_type")))
        try:
            await client.get(
                f"{ZLM_SERVER}/index/api/addStreamProxy", params=query_params
            )
        except Exception:
            continue


# =============================================================================


@app.get("/api/perf/statistic", summary="获取主要对象个数", tags=["性能"])
async def get_statistic():
    query_params = {"secret": ZLM_SECRET}
    response = await client.get(
        f"{ZLM_SERVER}/index/api/getStatistic", params=query_params
    )
    return response.json()


@app.get("/api/perf/work-threads-load", summary="获取后台线程负载", tags=["性能"])
async def get_work_threads_load():
    query_params = {"secret": ZLM_SECRET}
    response = await client.get(
        f"{ZLM_SERVER}/index/api/getWorkThreadsLoad", params=query_params
    )
    return response.json()


@app.get("/api/perf/threads-load", summary="获取网络线程负载", tags=["性能"])
async def get_threads_load():
    query_params = {"secret": ZLM_SECRET}
    response = await client.get(
        f"{ZLM_SERVER}/index/api/getThreadsLoad", params=query_params
    )
    return response.json()


@app.get(
    "/api/perf/host-stats",
    summary="获取当前系统资源使用率",
    tags=["性能"],
)
async def get_host_stats():
    timestamp = datetime.now().strftime("%H:%M:%S")

    # CPU 使用率
    cpu_percent = psutil.cpu_percent(interval=None)

    # 内存使用率
    memory = psutil.virtual_memory()
    memory_info = {
        "used": round(memory.used / (1024**3), 2),
        "total": round(memory.total / (1024**3), 2),
    }

    # 磁盘使用率
    disks: list[dict] = []
    seen_devices: set[str] = set()
    try:
        for part in psutil.disk_partitions(all=False):
            if not part.device or not part.fstype:
                continue
            if not (
                part.device.startswith("/dev/sd")
                or part.device.startswith("/dev/nvme")
                or part.device.startswith("/dev/vd")
            ):
                continue
            if part.device in seen_devices:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except PermissionError:
                continue
            seen_devices.add(part.device)
            disks.append(
                {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "used": round(usage.used / (1024**3), 2),
                    "total": round(usage.total / (1024**3), 2),
                }
            )
    except Exception:
        disks = []

    if disks:
        total_used = sum(d["used"] for d in disks)
        total_total = sum(d["total"] for d in disks)
        disk_info = {
            "used": round(total_used, 2),
            "total": round(total_total, 2),
        }
    else:
        disk = psutil.disk_usage("/")
        disk_info = {
            "used": round(disk.used / (1024**3), 2),
            "total": round(disk.total / (1024**3), 2),
        }

    net = psutil.net_io_counters()
    net_io = {
        "sent": int(net.bytes_sent),
        "recv": int(net.bytes_recv),
    }

    return {
        "code": 0,
        "data": {
            "time": timestamp,
            "ts_ms": int(datetime.now().timestamp() * 1000),
            "cpu": round(cpu_percent, 2),
            "memory": memory_info,
            "disk": disk_info,
            "disks": disks,
            "net_io": net_io,
        },
    }


@app.get("/api/system/maintenance", summary="获取系统维护信息", tags=["系统"])
async def get_system_maintenance():
    zlm_status = "不可用"
    zlm_version = "-"
    try:
        response = await client.get(
            f"{ZLM_SERVER}/index/api/getServerConfig", params={"secret": ZLM_SECRET}
        )
        result = response.json()
        if response.is_success and result.get("code") == 0:
            config = result.get("data")
            config = config if isinstance(config, dict) else {}
            general = config.get("general")
            general = general if isinstance(general, dict) else {}
            zlm_status = "正常"
            zlm_version = str(general.get("version", "-"))
    except (httpx.HTTPError, ValueError):
        pass

    licensed, license_status = _license_status()
    return {
        "code": 0,
        "data": {
            "product_name": "国产高清同步录音录像集中管理平台",
            "software_version": "V3.0.10 Build5000 D 2026/08/01",
            "serial_number": _machine_serial_number(),
            "license_status": license_status,
            "licensed": licensed,
            "zlm_status": zlm_status,
            "zlm_version": zlm_version,
        },
    }


@app.post("/api/system/license", summary="导入系统授权码", tags=["系统"])
async def post_system_license(request: Request):
    if not _is_admin(request):
        return {"code": 403, "msg": "需要管理员权限"}
    body = await request.json()
    success, message = _install_license(str(body.get("license_code", "")))
    return {"code": 0 if success else -1, "msg": message}


# =============================================================================
@app.post("/api/stream/pull-proxy", summary="添加拉流代理", tags=["流"])
async def post_pull_proxy(
    vhost: str = Query("__defaultVhost__", description="虚拟主机"),
    app: str = Query(..., description="应用名"),
    stream: str = Query(..., description="流ID"),
    url: str = Query(..., description="源流地址"),
    audio_type: int | None = Query(None, description="音频设置"),
):
    if not re.match(r"^[a-zA-Z0-9._-]+$", app):
        return {
            "code": -1,
            "msg": "app 只能包含字母、数字、下划线(_)、短横线(-) 或英文句点(.)",
        }
    if not re.match(r"^[a-zA-Z0-9._-]+$", stream):
        return {
            "code": -1,
            "msg": "stream 只能包含字母、数字、下划线(_)、短横线(-) 或英文句点(.)",
        }

    # 验证 url 前缀
    if not any(
        url.startswith(prefix)
        for prefix in ["rtsp://", "rtmp://", "http://", "https://"]
    ):
        return {
            "code": -1,
            "msg": "源流地址必须以 rtsp://、rtmp://、http:// 或 https:// 开头",
        }

    zlm_result = await _add_stream_proxy_to_zlm(
        vhost=vhost,
        app=app,
        stream=stream,
        url=url,
        audio_type=audio_type,
    )
    if zlm_result["code"] != 0:
        return {"code": -1, "msg": zlm_result["msg"], "detail": zlm_result.get("detail")}

    db_row = db_upsert_pull_proxy(
        vhost=vhost,
        app=app,
        stream=stream,
        url=url,
        audio_type=audio_type,
    )

    warning = summarize_existing_recordings(
        record_root=RECORD_ROOT, app=app, stream=stream
    )
    return {"code": 0, "msg": "拉流代理已创建", "db": db_row, "warning": warning}


@app.delete("/api/stream/pull-proxy", summary="删除拉流代理", tags=["流"])
async def delete_pull_proxy(
    vhost: str = Query("__defaultVhost__", description="虚拟主机"),
    app: str = Query(..., description="应用名"),
    stream: str = Query(..., description="流id"),
):
    deleted = db_delete_pull_proxy(vhost=vhost, app=app, stream=stream)
    db_delete_record_policy(vhost=vhost, app=app, stream=stream)
    asyncio.create_task(_del_stream_proxy_from_zlm(vhost=vhost, app=app, stream=stream))
    return {"code": 0, "msg": "已删除，后台同步中", "db_deleted": deleted}


# @app.get("/api/stream/pull-proxy-list", summary="获取拉流代理列表", tags=["流"])
# async def get_pull_proxy_list():
#     rows = db_list_pull_proxies()

#     repull_count_map: dict[str, int] = {}
#     try:
#         query_params = {"secret": ZLM_SECRET}
#         response = await client.get(
#             f"{ZLM_SERVER}/index/api/listStreamProxy", params=query_params
#         )
#         raw_data = response.json()
#         if raw_data.get("code") == 0:
#             for item in raw_data.get("data", []) or []:
#                 src = (item or {}).get("src") or {}
#                 vhost = src.get("vhost")
#                 app = src.get("app")
#                 stream = src.get("stream")
#                 if not (vhost and app and stream):
#                     continue
#                 key = _stream_proxy_key(vhost, app, stream)
#                 try:
#                     repull_count_map[key] = int(item.get("rePullCount", 0) or 0)
#                 except Exception:
#                     repull_count_map[key] = 0
#     except Exception:
#         repull_count_map = {}

#     data: list[dict] = []
#     for row in rows:
#         vhost = row["vhost"]
#         app = row["app"]
#         stream = row["stream"]
#         key = _stream_proxy_key(vhost, app, stream)
#         data.append(
#             {
#                 "key": key,
#                 "src": {"vhost": vhost, "app": app, "stream": stream},
#                 "url": row["url"],
#                 "rePullCount": repull_count_map.get(key, 0),
#                 "audio_type": row.get("audio_type"),
#             }
#         )

#     return {"code": 0, "data": data}


@app.get(
    "/api/stream/pull-proxy-table",
    summary="获取拉流列表（含在线状态）",
    tags=["流"],
)
async def get_pull_proxy_table(
    vhost: str = Query("__defaultVhost__", description="筛选虚拟主机"),
    app: str | None = Query(None, description="筛选应用名"),
    stream: str | None = Query(None, description="筛选流id"),
):
    rows = db_list_pull_proxies()
    if vhost:
        rows = [r for r in rows if r.get("vhost") == vhost]
    if app:
        rows = [r for r in rows if app in str(r.get("app", ""))]
    if stream:
        rows = [r for r in rows if stream in str(r.get("stream", ""))]

    repull_count_map: dict[str, int] = {}
    active_stream_map: dict[str, dict] = {}

    try:
        list_params = {"secret": ZLM_SECRET}
        media_params = {"secret": ZLM_SECRET, "vhost": vhost}
        list_resp, media_resp = await asyncio.gather(
            client.get(f"{ZLM_SERVER}/index/api/listStreamProxy", params=list_params),
            client.get(f"{ZLM_SERVER}/index/api/getMediaList", params=media_params),
        )

        list_raw = list_resp.json()
        if list_raw.get("code") == 0:
            for item in list_raw.get("data", []) or []:
                src = (item or {}).get("src") or {}
                src_vhost = src.get("vhost")
                src_app = src.get("app")
                src_stream = src.get("stream")
                if not (src_vhost and src_app and src_stream):
                    continue
                key = _stream_proxy_key(src_vhost, src_app, src_stream)
                try:
                    repull_count_map[key] = int(item.get("rePullCount", 0) or 0)
                except Exception:
                    repull_count_map[key] = 0

        media_raw = media_resp.json()
        if media_raw.get("code") == 0:
            for media in media_raw.get("data", []) or []:
                if not isinstance(media, dict):
                    continue
                if media.get("originTypeStr") != "pull":
                    continue

                media_vhost = str(media.get("vhost", ""))
                media_app = str(media.get("app", ""))
                media_stream = str(media.get("stream", ""))
                if not (media_vhost and media_app and media_stream):
                    continue

                key = _stream_proxy_key(media_vhost, media_app, media_stream)
                if key not in active_stream_map:
                    active_stream_map[key] = {
                        "vhost": media_vhost,
                        "app": media_app,
                        "stream": media_stream,
                        "originTypeStr": media.get("originTypeStr"),
                        "originUrl": media.get("originUrl"),
                        "originSock": media.get("originSock"),
                        "aliveSecond": media.get("aliveSecond"),
                        "isRecordingMP4": media.get("isRecordingMP4"),
                        "isRecordingHLS": media.get("isRecordingHLS"),
                        "totalReaderCount": media.get("totalReaderCount"),
                        "schemas": [],
                    }

                active_stream_map[key]["schemas"].append(
                    {
                        "schema": media.get("schema"),
                        "bytesSpeed": media.get("bytesSpeed"),
                        "readerCount": media.get("readerCount"),
                        "totalBytes": media.get("totalBytes"),
                        "tracks": media.get("tracks", []),
                    }
                )
    except Exception:
        repull_count_map = {}
        active_stream_map = {}

    data: list[dict] = []
    for row in rows:
        row_vhost = str(row.get("vhost", "__defaultVhost__"))
        row_app = str(row.get("app", ""))
        row_stream = str(row.get("stream", ""))
        key = _stream_proxy_key(row_vhost, row_app, row_stream)
        active = active_stream_map.get(key)
        data.append(
            {
                "vhost": row_vhost,
                "app": row_app,
                "stream": row_stream,
                "url": row.get("url"),
                "audio_type": row.get("audio_type"),
                "rePullCount": repull_count_map.get(key, 0),
                "isOnline": bool(active),
                "totalReaderCount": active.get("totalReaderCount") if active else "-",
                "aliveSecond": active.get("aliveSecond") if active else "-",
                "isRecordingMP4": active.get("isRecordingMP4") if active else "-",
                "schemas": active.get("schemas") if active else "-",
            }
        )

    return {"code": 0, "data": data}


@app.get(
    "/api/stream/streamid-list",
    summary="获取当前在线流ID列表（包括拉流和推流）",
    tags=["流"],
)
async def get_streamid_list(
    vhost: str = Query("__defaultVhost__", description="筛选虚拟主机"),
    schema: str | None = Query(None, description="筛选协议，例如 rtsp或rtmp"),
    app: str | None = Query(None, description="筛选应用名"),
    stream: str | None = Query(None, description="筛选流id"),
):
    query_params = {"secret": ZLM_SECRET}

    if schema:
        query_params["schema"] = schema
    if vhost:
        query_params["vhost"] = vhost
    if app:
        query_params["app"] = app
    if stream:
        query_params["stream"] = stream

    response = await client.get(
        f"{ZLM_SERVER}/index/api/getMediaList", params=query_params
    )
    raw_data = response.json()

    if raw_data["code"] != 0:
        return raw_data  # 错误直接返回

    media_list = raw_data.get("data", [])
    stream_map = {}

    for media in media_list:
        key = (media["vhost"], media["app"], media["stream"])
        if key not in stream_map:
            # 初始化主信息（这些字段在同一个流中应该一致）
            stream_map[key] = {
                "vhost": media["vhost"],
                "app": media["app"],
                "stream": media["stream"],
                "originTypeStr": media["originTypeStr"],
                "originUrl": media["originUrl"],
                "originSock": media["originSock"],
                "aliveSecond": media["aliveSecond"],
                "isRecordingMP4": media["isRecordingMP4"],
                "isRecordingHLS": media["isRecordingHLS"],
                "totalReaderCount": media["totalReaderCount"],
                "schemas": [],
            }

        # 添加当前 schema 的信息
        stream_map[key]["schemas"].append(
            {
                "schema": media["schema"],
                "bytesSpeed": media["bytesSpeed"],
                "readerCount": media["readerCount"],
                "totalBytes": media["totalBytes"],
                "tracks": media.get("tracks", []),
            }
        )

    # 转为列表返回
    result = list(stream_map.values())
    return {"code": 0, "data": result}


@app.delete(
    "/api/stream/streamid", summary="删除在线流ID（包括拉流和推流）", tags=["流"]
)
async def delete_streamid(
    vhost: str = Query("__defaultVhost__", description="虚拟主机"),
    app: str = Query(..., description="应用名"),
    stream: str = Query(..., description="流ID"),
):
    query_params = {"secret": ZLM_SECRET}
    query_params["vhost"] = str(vhost)
    query_params["app"] = str(app)
    query_params["stream"] = str(stream)
    query_params["force"] = "1"

    response = await client.get(
        f"{ZLM_SERVER}/index/api/close_streams", params=query_params
    )
    return response.json()


# =============================================================================
@app.get("/api/playback/start-record", summary="开启录制", tags=["录制"])
async def get_start_record(
    vhost: str = Query("__defaultVhost__", description="虚拟主机"),
    app: str = Query(..., description="应用名"),
    stream: str = Query(..., description="流ID"),
    record_days: str = Query(..., description="录制天数"),
):
    url = f"{ZLM_SERVER}/index/api/startRecord"

    query = {"secret": ZLM_SECRET}
    query["vhost"] = str(vhost)
    query["app"] = str(app)
    query["stream"] = str(stream)
    query["type"] = "1"
    try:
        retention_days = int(record_days)
    except Exception:
        return {"code": -1, "msg": "record_days 必须是整数"}
    if retention_days <= 0 or retention_days > 30:
        return {"code": -1, "msg": "录像天数范围建议 1-30 天"}

    query["max_second"] = "300"

    # 先启动录制，避免数据库偶发异常阻断真实录制动作
    response = await client.get(url, params=query)

    raw = response.json()

    if raw.get("code") == 0:
        try:
            db_row = db_upsert_record_policy(
                vhost=str(vhost),
                app=str(app),
                stream=str(stream),
                retention_days=retention_days,
                enabled=True,
            )
            raw["record_policy"] = db_row
        except Exception as e:
            raw["record_policy"] = None
            raw["record_policy_warning"] = f"录制已开启，但策略写入数据库失败: {e}"

    return raw


@app.get("/api/playback/stop-record", summary="停止录制", tags=["录制"])
async def get_stop_record(
    vhost: str = Query("__defaultVhost__", description="虚拟主机"),
    app: str = Query(..., description="应用名"),
    stream: str = Query(..., description="流ID"),
):
    url = f"{ZLM_SERVER}/index/api/stopRecord"

    query = {"secret": ZLM_SECRET}
    query["vhost"] = str(vhost)
    query["app"] = str(app)
    query["stream"] = str(stream)
    query["type"] = "1"

    response = await client.get(url, params=query)
    raw = response.json()
    existing = db_get_record_policy(vhost=str(vhost), app=str(app), stream=str(stream))
    if existing:
        try:
            retention_days = int(existing.get("retention_days", 0) or 0)
        except Exception:
            retention_days = 0
        db_upsert_record_policy(
            vhost=str(vhost),
            app=str(app),
            stream=str(stream),
            retention_days=retention_days,
            enabled=False,
        )
    return raw


@app.get("/api/playback/event-record", summary="开启事件视频录制", tags=["录制"])
async def get_event_record(
    vhost: str = Query("__defaultVhost__", description="虚拟主机"),
    app: str = Query(..., description="应用名"),
    stream: str = Query(..., description="流ID"),
    path: str = Query(..., description="录像保存相对路径，如 person/test.mp4"),
    back_ms: str = Query(..., description="回溯录制时长"),
    forward_ms: str = Query(..., description="后续录制时长"),
):
    url = f"{ZLM_SERVER}/index/api/startRecordTask"

    query = {"secret": ZLM_SECRET}
    query["vhost"] = str(vhost)
    query["app"] = str(app)
    query["stream"] = str(stream)
    query["path"] = path
    query["back_ms"] = back_ms
    query["forward_ms"] = forward_ms

    response = await client.get(url, params=query)
    return response.json()


@app.get(
    "/api/playback/streamid-record-list",
    summary="获取本地所有流ID的录制信息",
    tags=["录制"],
)
async def get_streamid_record_list(
    request: Request,
    device_name: str | None = Query(None, description="设备名称"),
    keyword: str | None = Query(None, description="通道名称、流 ID 或关键词"),
    case_keyword: str | None = Query(None, description="案件编号、名称或承办单位"),
    date_start: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    date_end: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
):
    if not _request_user(request):
        return {"code": 403, "msg": "请先登录"}
    result = []

    if not RECORD_ROOT.exists() or not RECORD_ROOT.is_dir():
        return {"code": -1, "msg": f"{RECORD_ROOT} 目录不存在或不是目录"}

    # 正则匹配 YYYY-MM-DD 格式
    date_pattern = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

    policy_map: dict[tuple[str, str, str], dict] = {}
    try:
        for row in db_list_record_policies(enabled_only=False) or []:
            vhost = str(row.get("vhost") or "__defaultVhost__")
            app_name = str(row.get("app") or "")
            stream_name = str(row.get("stream") or "")
            if not (app_name and stream_name):
                continue
            policy_map[(vhost, app_name, stream_name)] = dict(row)
    except Exception:
        policy_map = {}

    channel_map: dict[tuple[str, str], dict] = {}
    try:
        for channel in db_list_channels():
            app_name = str(channel.get("app") or "")
            stream_name = str(channel.get("stream") or "")
            if app_name and stream_name:
                channel_map[(app_name, stream_name)] = channel
    except Exception:
        channel_map = {}

    recording_bindings = db_list_case_recording_bindings(keyword=(case_keyword or "").strip())
    bound_recording_paths = {str(item["recording_path"]) for item in recording_bindings}
    case_labels_by_stream: dict[tuple[str, str], list[str]] = {}
    for binding in recording_bindings:
        key = (str(binding["app"]), str(binding["stream"]))
        label = f"{binding['case_no']} {binding['case_name']}"
        if label not in case_labels_by_stream.setdefault(key, []):
            case_labels_by_stream[key].append(label)

    active_keys: set[tuple[str, str, str]] = set()
    recording_map: dict[tuple[str, str, str], bool] = {}
    try:
        query_params = {"secret": ZLM_SECRET, "vhost": "__defaultVhost__"}
        response = await client.get(
            f"{ZLM_SERVER}/index/api/getMediaList", params=query_params
        )
        raw = response.json()
        if raw.get("code") == 0:
            for media in raw.get("data", []) or []:
                if not isinstance(media, dict):
                    continue
                vhost = str(media.get("vhost") or "__defaultVhost__")
                app_name = str(media.get("app") or "")
                stream_name = str(media.get("stream") or "")
                if not (app_name and stream_name):
                    continue
                key = (vhost, app_name, stream_name)
                active_keys.add(key)
                try:
                    is_recording = bool(media.get("isRecordingMP4"))
                except Exception:
                    is_recording = False
                if is_recording:
                    recording_map[key] = True
                else:
                    recording_map.setdefault(key, False)
    except Exception:
        active_keys = set()
        recording_map = {}

    try:
        for app_name in os.listdir(RECORD_ROOT):
            app_path = RECORD_ROOT / app_name
            if not app_path.is_dir():
                continue

            for stream_name in os.listdir(app_path):
                stream_path = app_path / stream_name
                if not stream_path.is_dir():
                    continue
                channel = channel_map.get((app_name, stream_name), {})
                stream_case_labels = case_labels_by_stream.get((app_name, stream_name), [])
                if case_keyword and not stream_case_labels:
                    continue
                current_device_name = str(channel.get("device_name") or "")
                search_text = " ".join([app_name, stream_name, current_device_name, str(channel.get("name") or ""), str(channel.get("keywords") or "")]).lower()
                if device_name and device_name.lower() not in current_device_name.lower():
                    continue
                if keyword and keyword.lower() not in search_text:
                    continue

                total_slices = 0
                total_size_bytes = 0
                dates = set()

                # 遍历 stream_path 下所有子项
                for item in os.listdir(stream_path):
                    item_path = stream_path / item

                    if not item_path.is_dir():
                        continue

                    # 使用正则匹配 YYYY-MM-DD
                    match = date_pattern.match(item)
                    if not match:
                        continue  # 不符合格式
                    if date_start and item < date_start:
                        continue
                    if date_end and item > date_end:
                        continue

                    # 检查该日期目录下是否有 .mp4 文件
                    try:
                        mp4_files = [
                            f
                            for f in os.listdir(item_path)
                            if f.lower().endswith(".mp4")
                        ]
                        if case_keyword:
                            mp4_files = [f for f in mp4_files if f"{app_name}/{stream_name}/{item}/{f}" in bound_recording_paths]
                    except Exception:
                        continue

                    if not mp4_files:
                        # 空目录：删除
                        try:
                            shutil.rmtree(item_path)
                            print(f"已删除空录像目录: {item_path}")
                        except Exception as e:
                            print(f"删除空目录失败 {item_path}: {e}")
                        continue

                    # 统计文件数量和大小
                    for fname in mp4_files:
                        file_path = item_path / fname
                        if not file_path.is_file():
                            continue
                        try:
                            size = file_path.stat().st_size
                            total_size_bytes += size
                            total_slices += 1
                        except OSError as e:
                            print(f"读取文件大小失败 {file_path}: {e}")

                    # 添加有效日期
                    dates.add(item)

                # 只有存在录像片段才加入结果
                if total_slices == 0:
                    continue

                policy = (
                    policy_map.get(("__defaultVhost__", app_name, stream_name)) or {}
                )
                try:
                    enabled = int(policy.get("enabled", 0) or 0)
                except Exception:
                    enabled = 0
                record_days = policy.get("retention_days", "-") if enabled == 1 else "-"

                result.append(
                    {
                        "app": app_name,
                        "stream": stream_name,
                        "device_name": current_device_name or "未关联设备",
                        "channel_name": channel.get("name") or "-",
                        "recording_name": f"{current_device_name or '未关联设备'} - {channel.get('name') or stream_name}",
                        "case_labels": "、".join(stream_case_labels) or "-",
                        "slice_num": total_slices,
                        "total_storage_gb": round(total_size_bytes / (1024**3), 2),
                        "dates": sorted(dates),
                        "record_days": record_days,
                        "isOnline": ("__defaultVhost__", app_name, stream_name)
                        in active_keys,
                        "isRecordingMP4": recording_map.get(
                            ("__defaultVhost__", app_name, stream_name), False
                        ),
                    }
                )

        return {"code": 0, "data": result}

    except Exception as e:
        return {"code": -1, "msg": f"目录遍历异常 {e}"}


@app.get(
    "/api/playback/streamid-record", summary="获取指定流ID的全部录制信息", tags=["录制"]
)
async def get_streamid_record(
    request: Request,
    app: str = Query(..., description="应用名"),
    stream: str = Query(..., description="流ID"),
    date: str = Query(..., description="日期格式 YYYY-MM-DD"),
    case_keyword: str | None = Query(None, description="案件编号、名称或承办单位"),
):
    if not _request_user(request):
        return {"code": 403, "msg": "请先登录"}
    try:
        target_dir = _recording_directory_path(app, stream, date)
    except ValueError as error:
        return {"code": -1, "msg": str(error)}

    if not target_dir.exists():
        return {"code": 1, "msg": f"目录不存在: {target_dir}"}

    if not target_dir.is_dir():
        return {"code": 1, "msg": f"路径不是目录: {target_dir}"}

    tz_shanghai = ZoneInfo("Asia/Shanghai")
    parsed: list[tuple[Path, datetime]] = []
    fallback_files: list[Path] = []

    for file_path in target_dir.iterdir():
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() != ".mp4":
            continue
        if file_path.name.startswith("."):
            continue

        m = re.match(
            r"(\d{4})-(\d{1,2})-(\d{1,2})-(\d{1,2})-(\d{1,2})-(\d{1,2})",
            file_path.name,
        )
        if not m:
            fallback_files.append(file_path)
            continue
        year, month, day, hour, minute, second = map(int, m.groups())
        try:
            start_dt = datetime(
                year, month, day, hour, minute, second, tzinfo=tz_shanghai
            )
        except ValueError:
            fallback_files.append(file_path)
            continue
        parsed.append((file_path, start_dt))

    parsed.sort(key=lambda x: x[1])

    results: list[dict] = []
    default_duration = 300.0
    for i, (file_path, start_dt) in enumerate(parsed):
        duration = default_duration
        if i + 1 < len(parsed):
            next_start = parsed[i + 1][1]
            delta = (next_start - start_dt).total_seconds()
            if 1 <= delta <= 600:
                duration = float(delta)
        end_dt = start_dt + timedelta(seconds=duration)

        try:
            rel_path = file_path.relative_to(RECORD_ROOT)
        except ValueError:
            continue

        results.append(
            {
                "filename": str(rel_path),
                "duration": round(duration, 3),
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
            }
        )

    for file_path in fallback_files:
        data = get_video_shanghai_time(file_path)
        if not data:
            continue
        try:
            rel_path = file_path.relative_to(RECORD_ROOT)
            data["filename"] = str(rel_path)
        except ValueError:
            continue
        results.append(data)

    results.sort(key=lambda x: x["start"])
    channel = next(
        (
            item
            for item in db_list_channels()
            if item.get("app") == app and item.get("stream") == stream
        ),
        {},
    )
    bindings = db_list_case_recording_bindings(app=app, stream=stream)
    case_labels_by_path: dict[str, list[str]] = {}
    for binding in bindings:
        label = f"{binding['case_no']} {binding['case_name']}"
        labels = case_labels_by_path.setdefault(str(binding["recording_path"]), [])
        if label not in labels:
            labels.append(label)
    if case_keyword:
        matched_paths = {str(item["recording_path"]) for item in db_list_case_recording_bindings(keyword=case_keyword.strip(), app=app, stream=stream)}
        results = [item for item in results if str(item["filename"]) in matched_paths]
    for item in results:
        item["device_name"] = str(channel.get("device_name") or "未关联设备")
        item["channel_name"] = str(channel.get("name") or stream)
        item["format"] = "MP4"
        item["case_labels"] = "、".join(case_labels_by_path.get(str(item["filename"]), [])) or "-"

    return {"code": 0, "data": results}


@app.get("/api/playback/recordings/file", summary="播放或下载录像片段", tags=["录制"])
async def get_recording_file(
    request: Request,
    path: str = Query(..., description="录像相对路径"),
    download: bool = Query(False, description="是否以附件下载"),
):
    if not _request_user(request):
        return {"code": 403, "msg": "请先登录"}
    try:
        file_path = _recording_file_path(path)
    except ValueError:
        return {"code": -1, "msg": "录像路径无效"}
    if not file_path.is_file():
        return {"code": -1, "msg": "录像文件不存在"}
    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=file_path.name if download else None,
    )


@app.post("/api/playback/recordings-download-zip", summary="打包下载录像片段", tags=["录制"])
async def download_recordings_zip(request: Request):
    if not _request_user(request):
        return {"code": 403, "msg": "请先登录"}
    try:
        paths = (await request.json()).get("paths", [])
    except (json.JSONDecodeError, AttributeError):
        return {"code": -1, "msg": "请求参数无效"}
    if not isinstance(paths, list) or not 1 <= len(paths) <= 50:
        return {"code": -1, "msg": "请选择 1 至 50 个录像片段"}

    files: list[tuple[Path, str]] = []
    total_size = 0
    seen_paths: set[str] = set()
    for recording_path in paths:
        if not isinstance(recording_path, str) or recording_path in seen_paths:
            continue
        seen_paths.add(recording_path)
        try:
            file_path = _recording_file_path(recording_path)
        except ValueError:
            return {"code": -1, "msg": "录像路径无效"}
        if not file_path.is_file():
            return {"code": -1, "msg": f"录像文件不存在: {recording_path}"}
        total_size += file_path.stat().st_size
        if total_size > 2 * 1024 * 1024 * 1024:
            return {"code": -1, "msg": "所选录像总大小不能超过 2 GB"}
        files.append((file_path, recording_path))
    if not files:
        return {"code": -1, "msg": "没有可下载的录像文件"}

    handle = tempfile.NamedTemporaryFile(prefix="streamui-recordings-", suffix=".zip", delete=False)
    archive_path = Path(handle.name)
    handle.close()
    def build_archive() -> None:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, (file_path, recording_path) in enumerate(files, start=1):
                archive.write(file_path, arcname=f"{index:02d}_{Path(recording_path).name}")

    try:
        await asyncio.to_thread(build_archive)
    except OSError:
        archive_path.unlink(missing_ok=True)
        return {"code": -1, "msg": "录像打包失败"}
    filename = f"录像片段_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
    return FileResponse(archive_path, media_type="application/zip", filename=filename, background=BackgroundTask(archive_path.unlink, missing_ok=True))


@app.delete(
    "/api/playback/streamid-record", summary="删除指定流ID的全部录制文件", tags=["录制"]
)
async def delete_streamid_record(
    request: Request,
    app: str = Query(..., description="应用名"),
    stream: str = Query(..., description="流ID"),
):
    if not _can_manage(request):
        return {"code": 403, "msg": "需要管理员或操作员权限"}
    bindings = db_list_case_recording_bindings(app=app, stream=stream)
    if bindings:
        return {"code": -1, "msg": "该流存在已绑定案件会话的录像，不能删除"}
    try:
        base_dir = _recording_directory_path(app, stream)
    except ValueError as error:
        return {"code": -1, "msg": str(error)}

    if not base_dir.exists():
        return {"code": -1, "msg": f"目录不存在: {base_dir}"}

    if not base_dir.is_dir():
        return {"code": -1, "msg": f"路径不是目录: {base_dir}"}

    # 匹配 YYYY-MM-DD 格式
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    deleted_count = 0

    for item in base_dir.iterdir():
        if item.is_dir() and date_pattern.match(item.name):
            shutil.rmtree(item)
            deleted_count += 1

    return {"code": 0, "msg": f"已删除 {deleted_count} 个录像目录"}


# =============================================================================


@app.get("/api/server/config", summary="获取服务器配置", tags=["配置"])
async def get_server_config():
    query_params = {"secret": ZLM_SECRET}
    response = await client.get(
        f"{ZLM_SERVER}/index/api/getServerConfig", params=query_params
    )
    return response.json()


@app.put("/api/server/config", summary="修改服务器配置", tags=["配置"])
async def put_server_config(request: Request):
    query_params = dict(request.query_params)
    query_params["secret"] = ZLM_SECRET

    response = await client.get(
        f"{ZLM_SERVER}/index/api/setServerConfig", params=query_params
    )
    return response.json()


@app.get(
    "/api/server/restart",
    summary="重启 ZLMediaKit（同时重启管理平台）",
    tags=["配置"],
)
async def get_restart_zlm(delay_ms: int = Query(0, description="延迟重启（毫秒）")):
    await asyncio.sleep(max(delay_ms, 0) / 1000)

    try:
        client = docker.DockerClient(base_url="unix://var/run/docker.sock")
        zlm_container = client.containers.get(ZLM_CONTAINER_NAME)
        zlm_container.restart()

        if STREAMUI_CONTAINER_NAME:

            async def _restart_self():
                try:
                    c = docker.DockerClient(base_url="unix://var/run/docker.sock")
                    self_container = c.containers.get(STREAMUI_CONTAINER_NAME)
                    self_container.restart()
                except Exception:
                    return

            asyncio.create_task(_restart_self())

        return {
            "code": 0,
            "msg": "重启成功",
            "via": "docker",
            "restart_self": True,
        }
    except Exception as e:
        return {"code": -1, "msg": "重启失败", "error": str(e), "via": "docker"}


if __name__ == "__main__":
    import uvicorn

    # uvicorn.run("main:app", host="0.0.0.0", port=10801, reload=True)
    uvicorn.run("main:app", host="0.0.0.0", port=10801, reload=False)
