import json
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from typing import Iterator
from typing import TypedDict


DB_PATH = Path(os.getenv("STREAMUI_DB_PATH", str(Path(__file__).resolve().parent / "streamui.db")))
BUILTIN_ADMIN_ID = 1000
RESERVED_ADMIN_ID_END = 1005
FIRST_REGULAR_USER_ID = RESERVED_ADMIN_ID_END + 1


class PullProxyRow(TypedDict):
    vhost: str
    app: str
    stream: str
    url: str
    audio_type: int | None
    created_at: str
    updated_at: str


class RecordPolicyRow(TypedDict):
    vhost: str
    app: str
    stream: str
    retention_days: int
    enabled: int
    created_at: str
    updated_at: str


class DeviceRow(TypedDict):
    device_id: str
    name: str
    serial_number: str | None
    address: str | None
    web_url: str | None
    status: str
    last_seen_at: str | None
    created_at: str
    updated_at: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_access_key(access_key: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", access_key.encode(), salt.encode(), 200_000)
    return f"pbkdf2${salt}${digest.hex()}"


def _verify_access_key(access_key: str, stored: str) -> bool:
    try:
        marker, salt, expected = stored.split("$", 2)
    except ValueError:
        # Supports devices registered before key hashing was introduced.
        return hmac.compare_digest(access_key, stored)
    if marker != "pbkdf2":
        return False
    return hmac.compare_digest(_hash_access_key(access_key, salt), stored)


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS pull_proxy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vhost TEXT NOT NULL,
                app TEXT NOT NULL,
                stream TEXT NOT NULL,
                url TEXT NOT NULL,
                audio_type INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(vhost, app, stream)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS record_policy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vhost TEXT NOT NULL,
                app TEXT NOT NULL,
                stream TEXT NOT NULL,
                retention_days INTEGER NOT NULL,
                enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(vhost, app, stream)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                nickname TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'operator',
                enabled INTEGER NOT NULL DEFAULT 1,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                bound_mac TEXT NOT NULL DEFAULT '',
                bound_ip TEXT NOT NULL DEFAULT '',
                password_changed_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        user_columns = {row[1] for row in db.execute("PRAGMA table_info(user)").fetchall()}
        if "must_change_password" not in user_columns:
            db.execute("ALTER TABLE user ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
        if "full_name" not in user_columns:
            db.execute("ALTER TABLE user ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
        if "nickname" not in user_columns:
            db.execute("ALTER TABLE user ADD COLUMN nickname TEXT NOT NULL DEFAULT ''")
        if "bound_mac" not in user_columns:
            db.execute("ALTER TABLE user ADD COLUMN bound_mac TEXT NOT NULL DEFAULT ''")
        if "bound_ip" not in user_columns:
            db.execute("ALTER TABLE user ADD COLUMN bound_ip TEXT NOT NULL DEFAULT ''")
        if "password_changed_at" not in user_columns:
            db.execute("ALTER TABLE user ADD COLUMN password_changed_at TEXT NOT NULL DEFAULT ''")
        db.execute("UPDATE user SET password_changed_at=created_at WHERE password_changed_at='' OR password_changed_at IS NULL")
        db.execute("UPDATE user SET full_name=username WHERE full_name='' OR full_name IS NULL")
        db.execute("UPDATE user SET nickname=username WHERE nickname='' OR nickname IS NULL")
        reserved_regulars = db.execute(
            "SELECT id FROM user WHERE id BETWEEN ? AND ? AND role<>'admin' ORDER BY id",
            (BUILTIN_ADMIN_ID, RESERVED_ADMIN_ID_END),
        ).fetchall()
        next_regular_id = max(
            FIRST_REGULAR_USER_ID,
            int(db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM user").fetchone()[0]),
        )
        for row in reserved_regulars:
            db.execute("UPDATE user SET id=? WHERE id=?", (next_regular_id, int(row["id"])))
            next_regular_id += 1
        admin_row = db.execute("SELECT id FROM user WHERE username='admin'").fetchone()
        if admin_row and int(admin_row["id"]) != BUILTIN_ADMIN_ID:
            occupied = db.execute("SELECT username FROM user WHERE id=?", (BUILTIN_ADMIN_ID,)).fetchone()
            if occupied:
                free_reserved_ids = [
                    candidate
                    for candidate in range(BUILTIN_ADMIN_ID + 1, RESERVED_ADMIN_ID_END + 1)
                    if not db.execute("SELECT 1 FROM user WHERE id=?", (candidate,)).fetchone()
                ]
                next_id = free_reserved_ids[0] if free_reserved_ids else int(db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM user").fetchone()[0])
                db.execute("UPDATE user SET id=? WHERE id=?", (next_id, BUILTIN_ADMIN_ID))
            db.execute("UPDATE user SET id=? WHERE username='admin'", (BUILTIN_ADMIN_ID,))
        max_user_id = int(db.execute("SELECT COALESCE(MAX(id), 0) FROM user").fetchone()[0])
        next_sequence = max(RESERVED_ADMIN_ID_END, max_user_id)
        sequence_row = db.execute("SELECT seq FROM sqlite_sequence WHERE name='user'").fetchone()
        if sequence_row:
            db.execute("UPDATE sqlite_sequence SET seq=? WHERE name='user'", (max(int(sequence_row["seq"]), next_sequence),))
        else:
            db.execute("INSERT INTO sqlite_sequence(name, seq) VALUES ('user', ?)", (next_sequence,))
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS organization (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(parent_id) REFERENCES organization(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_setting (
                setting_key TEXT PRIMARY KEY,
                setting_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS alarm_recipient (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL DEFAULT '',
                target_ip TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(username, target_ip)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS alarm_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER,
                device_id TEXT,
                source_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'urgent',
                status TEXT NOT NULL DEFAULT 'active',
                message TEXT NOT NULL,
                detail_json TEXT NOT NULL DEFAULT '{}',
                occurred_at TEXT NOT NULL,
                acknowledged_by TEXT NOT NULL DEFAULT '',
                acknowledged_at TEXT,
                resolved_by TEXT NOT NULL DEFAULT '',
                resolved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(room_id) REFERENCES interview_room(id) ON DELETE SET NULL,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE SET NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS alarm_linkage_action (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alarm_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                detail_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(alarm_id) REFERENCES alarm_event(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS access_point (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                room_id INTEGER,
                name TEXT NOT NULL,
                point_code TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE SET NULL,
                FOREIGN KEY(room_id) REFERENCES interview_room(id) ON DELETE SET NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS access_permission (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                access_point_id INTEGER NOT NULL,
                personnel_id INTEGER NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                schedule_template TEXT NOT NULL DEFAULT '',
                holiday_plan TEXT NOT NULL DEFAULT '',
                auth_method TEXT NOT NULL DEFAULT 'card',
                delivery_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(access_point_id, personnel_id),
                FOREIGN KEY(access_point_id) REFERENCES access_point(id) ON DELETE CASCADE,
                FOREIGN KEY(personnel_id) REFERENCES personnel(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS access_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                access_point_id INTEGER NOT NULL,
                personnel_id INTEGER,
                direction TEXT NOT NULL,
                event_time TEXT NOT NULL,
                snapshot_url TEXT NOT NULL DEFAULT '',
                detail_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(access_point_id) REFERENCES access_point(id) ON DELETE CASCADE,
                FOREIGN KEY(personnel_id) REFERENCES personnel(id) ON DELETE SET NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS remote_command (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                command_type TEXT NOT NULL,
                content TEXT NOT NULL,
                detail_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'sent',
                sent_by TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                acknowledged_by TEXT NOT NULL DEFAULT '',
                acknowledged_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES case_session(id) ON DELETE CASCADE
            )
            """
        )
        remote_command_columns = {row[1] for row in db.execute("PRAGMA table_info(remote_command)").fetchall()}
        if "detail_json" not in remote_command_columns:
            db.execute("ALTER TABLE remote_command ADD COLUMN detail_json TEXT NOT NULL DEFAULT '{}'")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS personnel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER,
                name TEXT NOT NULL,
                employee_no TEXT NOT NULL UNIQUE,
                identity_no TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                username TEXT UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(organization_id) REFERENCES organization(id) ON DELETE SET NULL,
                FOREIGN KEY(username) REFERENCES user(username) ON DELETE SET NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS device (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                serial_number TEXT,
                address TEXT,
                web_url TEXT,
                access_key TEXT NOT NULL,
                access_key_display TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'offline',
                last_seen_at TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        device_columns = {row[1] for row in db.execute("PRAGMA table_info(device)").fetchall()}
        if "enabled" not in device_columns:
            db.execute("ALTER TABLE device ADD COLUMN enabled INTEGER NOT NULL DEFAULT 0")
        if "access_key_display" not in device_columns:
            db.execute("ALTER TABLE device ADD COLUMN access_key_display TEXT NOT NULL DEFAULT ''")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS device_channel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                channel_no INTEGER NOT NULL,
                name TEXT NOT NULL,
                vhost TEXT NOT NULL DEFAULT '__defaultVhost__',
                app TEXT,
                stream TEXT,
                keywords TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(device_id, channel_no),
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS gb28181_device (
                device_id TEXT PRIMARY KEY,
                address TEXT NOT NULL,
                sip_port INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'offline',
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                keepalive_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS gb28181_channel (
                device_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ON',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(device_id, channel_id),
                FOREIGN KEY(device_id) REFERENCES gb28181_device(device_id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS record_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                weekdays TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                retention_days INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(channel_id) REFERENCES device_channel(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS video_wall_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_username TEXT NOT NULL,
                name TEXT NOT NULL,
                layout_size INTEGER NOT NULL,
                cells_json TEXT NOT NULL,
                polling_seconds INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_username, name)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS device_archive_folder (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(device_id, name),
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS business_directory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_area (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                directory_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(directory_id, name),
                FOREIGN KEY(directory_id) REFERENCES business_directory(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_room (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                room_type TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 0,
                location TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(area_id, name),
                FOREIGN KEY(area_id) REFERENCES interview_area(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_room_device (
                room_id INTEGER NOT NULL,
                device_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                PRIMARY KEY(room_id, device_id),
                FOREIGN KEY(room_id) REFERENCES interview_room(id) ON DELETE CASCADE,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_no TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                case_type TEXT NOT NULL DEFAULT 'criminal',
                handling_unit TEXT NOT NULL DEFAULT '',
                case_reason TEXT NOT NULL DEFAULT '',
                lead_investigator TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'created',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_device_assignment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_by TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                acknowledged_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(case_id, device_id),
                FOREIGN KEY(case_id) REFERENCES case_info(id) ON DELETE CASCADE,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                session_no TEXT NOT NULL,
                session_type TEXT NOT NULL DEFAULT 'interrogation',
                recording_mode TEXT NOT NULL DEFAULT 'disk',
                status TEXT NOT NULL DEFAULT 'planned',
                planned_start_at TEXT,
                planned_end_at TEXT,
                location TEXT NOT NULL DEFAULT '',
                host_name TEXT NOT NULL DEFAULT '',
                participant_summary TEXT NOT NULL DEFAULT '',
                started_at TEXT,
                ended_at TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(case_id, session_no),
                FOREIGN KEY(case_id) REFERENCES case_info(id) ON DELETE CASCADE,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE RESTRICT
            )
            """
        )
        session_columns = {row[1] for row in db.execute("PRAGMA table_info(case_session)").fetchall()}
        if "recording_mode" not in session_columns:
            db.execute("ALTER TABLE case_session ADD COLUMN recording_mode TEXT NOT NULL DEFAULT 'disk'")
        if "planned_start_at" not in session_columns:
            db.execute("ALTER TABLE case_session ADD COLUMN planned_start_at TEXT")
        if "planned_end_at" not in session_columns:
            db.execute("ALTER TABLE case_session ADD COLUMN planned_end_at TEXT")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS remote_hearing_task (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                task_no TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                scheduled_start_at TEXT,
                scheduled_end_at TEXT,
                media_app TEXT NOT NULL DEFAULT 'hearing',
                stream_prefix TEXT NOT NULL UNIQUE,
                created_by TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES case_info(id) ON DELETE RESTRICT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS remote_hearing_participant (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                detail_json TEXT NOT NULL DEFAULT '{}',
                started_at TEXT,
                ended_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(task_id, device_id),
                UNIQUE(task_id, role),
                FOREIGN KEY(task_id) REFERENCES remote_hearing_task(id) ON DELETE CASCADE,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE RESTRICT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_device_command (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                scheduled_at TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                request_json TEXT NOT NULL DEFAULT '{}',
                response_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT NOT NULL DEFAULT '',
                started_at TEXT,
                completed_at TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES case_session(id) ON DELETE CASCADE,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE RESTRICT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_disc_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'waiting',
                drive_name TEXT NOT NULL DEFAULT '',
                primary_hash TEXT NOT NULL DEFAULT '',
                verified_hash TEXT NOT NULL DEFAULT '',
                check_percent INTEGER NOT NULL DEFAULT 0,
                detail_json TEXT NOT NULL DEFAULT '{}',
                verified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES case_session(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_transcript (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                transcript_type TEXT NOT NULL DEFAULT 'interrogation',
                status TEXT NOT NULL DEFAULT 'draft',
                current_version INTEGER NOT NULL DEFAULT 0,
                template_key TEXT NOT NULL DEFAULT 'interrogation',
                editor_type TEXT NOT NULL DEFAULT 'tiptap',
                draft_content_json TEXT NOT NULL DEFAULT '{"type":"doc","content":[{"type":"paragraph"}]}',
                last_saved_by TEXT,
                last_saved_at TEXT,
                finalized_by TEXT,
                finalized_at TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES case_session(id) ON DELETE CASCADE
            )
            """
        )
        transcript_columns = {row[1] for row in db.execute("PRAGMA table_info(case_transcript)").fetchall()}
        if "template_key" not in transcript_columns:
            db.execute("ALTER TABLE case_transcript ADD COLUMN template_key TEXT NOT NULL DEFAULT 'interrogation'")
        if "editor_type" not in transcript_columns:
            db.execute("ALTER TABLE case_transcript ADD COLUMN editor_type TEXT NOT NULL DEFAULT 'tiptap'")
        if "draft_content_json" not in transcript_columns:
            db.execute("ALTER TABLE case_transcript ADD COLUMN draft_content_json TEXT NOT NULL DEFAULT '{\"type\":\"doc\",\"content\":[{\"type\":\"paragraph\"}]}'")
        if "last_saved_by" not in transcript_columns:
            db.execute("ALTER TABLE case_transcript ADD COLUMN last_saved_by TEXT")
        if "last_saved_at" not in transcript_columns:
            db.execute("ALTER TABLE case_transcript ADD COLUMN last_saved_at TEXT")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_transcript_template (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                transcript_type TEXT NOT NULL DEFAULT 'other',
                content_json TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_transcript_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transcript_id INTEGER NOT NULL,
                version_no INTEGER NOT NULL,
                archive_id INTEGER,
                content_hash TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(transcript_id, version_no),
                FOREIGN KEY(transcript_id) REFERENCES case_transcript(id) ON DELETE CASCADE,
                FOREIGN KEY(archive_id) REFERENCES device_archive_file(id) ON DELETE RESTRICT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                session_id INTEGER,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                detail_json TEXT NOT NULL DEFAULT '{}',
                previous_hash TEXT NOT NULL DEFAULT '',
                event_hash TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES case_info(id) ON DELETE CASCADE,
                FOREIGN KEY(session_id) REFERENCES case_session(id) ON DELETE SET NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS device_archive_file (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                case_id INTEGER,
                session_id INTEGER,
                folder_id INTEGER,
                archive_type TEXT NOT NULL DEFAULT 'document',
                status TEXT NOT NULL DEFAULT 'not_started',
                title TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                file_size INTEGER NOT NULL DEFAULT 0,
                content_type TEXT,
                sha256 TEXT NOT NULL DEFAULT '',
                uploaded_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE CASCADE,
                FOREIGN KEY(case_id) REFERENCES case_info(id) ON DELETE SET NULL,
                FOREIGN KEY(session_id) REFERENCES case_session(id) ON DELETE SET NULL,
                FOREIGN KEY(folder_id) REFERENCES device_archive_folder(id) ON DELETE SET NULL
            )
            """
        )
        archive_columns = {row[1] for row in db.execute("PRAGMA table_info(device_archive_file)").fetchall()}
        if "case_id" not in archive_columns:
            db.execute("ALTER TABLE device_archive_file ADD COLUMN case_id INTEGER")
        if "session_id" not in archive_columns:
            db.execute("ALTER TABLE device_archive_file ADD COLUMN session_id INTEGER")
        if "sha256" not in archive_columns:
            db.execute("ALTER TABLE device_archive_file ADD COLUMN sha256 TEXT NOT NULL DEFAULT ''")
        case_columns = {row[1] for row in db.execute("PRAGMA table_info(case_info)").fetchall()}
        if "case_reason" not in case_columns:
            db.execute("ALTER TABLE case_info ADD COLUMN case_reason TEXT NOT NULL DEFAULT ''")
        if "lead_investigator" not in case_columns:
            db.execute("ALTER TABLE case_info ADD COLUMN lead_investigator TEXT NOT NULL DEFAULT ''")
        audit_columns = {row[1] for row in db.execute("PRAGMA table_info(case_audit_log)").fetchall()}
        if "previous_hash" not in audit_columns:
            db.execute("ALTER TABLE case_audit_log ADD COLUMN previous_hash TEXT NOT NULL DEFAULT ''")
        if "event_hash" not in audit_columns:
            db.execute("ALTER TABLE case_audit_log ADD COLUMN event_hash TEXT NOT NULL DEFAULT ''")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_media_asset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                archive_id INTEGER,
                media_type TEXT NOT NULL,
                source_stream TEXT NOT NULL DEFAULT '',
                started_at TEXT,
                ended_at TEXT,
                sha256 TEXT NOT NULL,
                integrity_status TEXT NOT NULL DEFAULT 'verified',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES case_info(id) ON DELETE CASCADE,
                FOREIGN KEY(session_id) REFERENCES case_session(id) ON DELETE CASCADE,
                FOREIGN KEY(archive_id) REFERENCES device_archive_file(id) ON DELETE RESTRICT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_recording_binding (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                app TEXT NOT NULL,
                stream TEXT NOT NULL,
                recording_path TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                sha256 TEXT NOT NULL DEFAULT '',
                integrity_status TEXT NOT NULL DEFAULT 'pending',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES case_info(id) ON DELETE CASCADE,
                FOREIGN KEY(session_id) REFERENCES case_session(id) ON DELETE CASCADE,
                FOREIGN KEY(device_id) REFERENCES device(device_id) ON DELETE RESTRICT
            )
            """
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_case_info_status_updated ON case_info(status, updated_at DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_case_assignment_device_status ON case_device_assignment(device_id, status, updated_at DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_case_session_case_device ON case_session(case_id, device_id, updated_at DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_case_audit_case_id ON case_audit_log(case_id, id DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_case_recording_stream_time ON case_recording_binding(app, stream, started_at, ended_at)")


def list_pull_proxies() -> list[PullProxyRow]:
    with get_db() as db:
        rows = db.execute(
            """
            SELECT vhost, app, stream, url, audio_type, created_at, updated_at
            FROM pull_proxy
            ORDER BY id DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]  # type: ignore[return-value]


def upsert_pull_proxy(
    *,
    vhost: str,
    app: str,
    stream: str,
    url: str,
    audio_type: int | None,
) -> dict[str, Any]:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            db.execute(
                """
                INSERT INTO pull_proxy (vhost, app, stream, url, audio_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(vhost, app, stream) DO UPDATE SET
                    url=excluded.url,
                    audio_type=excluded.audio_type,
                    updated_at=excluded.updated_at
                """,
                (vhost, app, stream, url, audio_type, now, now),
            )
        except sqlite3.OperationalError:
            existing = db.execute(
                "SELECT 1 FROM pull_proxy WHERE vhost=? AND app=? AND stream=?",
                (vhost, app, stream),
            ).fetchone()
            if existing:
                db.execute(
                    """
                    UPDATE pull_proxy
                    SET url=?, audio_type=?, updated_at=?
                    WHERE vhost=? AND app=? AND stream=?
                    """,
                    (url, audio_type, now, vhost, app, stream),
                )
            else:
                db.execute(
                    """
                    INSERT INTO pull_proxy (vhost, app, stream, url, audio_type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (vhost, app, stream, url, audio_type, now, now),
                )

        row = db.execute(
            """
            SELECT vhost, app, stream, url, audio_type, created_at, updated_at
            FROM pull_proxy
            WHERE vhost=? AND app=? AND stream=?
            """,
            (vhost, app, stream),
        ).fetchone()

    return dict(row) if row else {}


def delete_pull_proxy(*, vhost: str, app: str, stream: str) -> int:
    with get_db() as db:
        cur = db.execute(
            "DELETE FROM pull_proxy WHERE vhost=? AND app=? AND stream=?",
            (vhost, app, stream),
        )
        return int(cur.rowcount or 0)


def list_record_policies(*, enabled_only: bool = False) -> list[RecordPolicyRow]:
    with get_db() as db:
        if enabled_only:
            rows = db.execute(
                """
                SELECT vhost, app, stream, retention_days, enabled, created_at, updated_at
                FROM record_policy
                WHERE enabled=1
                ORDER BY id DESC
                """
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT vhost, app, stream, retention_days, enabled, created_at, updated_at
                FROM record_policy
                ORDER BY id DESC
                """
            ).fetchall()

    return [dict(row) for row in rows]  # type: ignore[return-value]


def get_record_policy(*, vhost: str, app: str, stream: str) -> RecordPolicyRow | None:
    with get_db() as db:
        row = db.execute(
            """
            SELECT vhost, app, stream, retention_days, enabled, created_at, updated_at
            FROM record_policy
            WHERE vhost=? AND app=? AND stream=?
            """,
            (vhost, app, stream),
        ).fetchone()
    return dict(row) if row else None  # type: ignore[return-value]


def upsert_record_policy(
    *,
    vhost: str,
    app: str,
    stream: str,
    retention_days: int,
    enabled: bool,
) -> dict[str, Any]:
    now = _utc_now_iso()
    enabled_int = 1 if enabled else 0
    with get_db() as db:
        try:
            db.execute(
                """
                INSERT INTO record_policy (vhost, app, stream, retention_days, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(vhost, app, stream) DO UPDATE SET
                    retention_days=excluded.retention_days,
                    enabled=excluded.enabled,
                    updated_at=excluded.updated_at
                """,
                (vhost, app, stream, int(retention_days), enabled_int, now, now),
            )
        except sqlite3.OperationalError:
            existing = db.execute(
                "SELECT 1 FROM record_policy WHERE vhost=? AND app=? AND stream=?",
                (vhost, app, stream),
            ).fetchone()
            if existing:
                db.execute(
                    """
                    UPDATE record_policy
                    SET retention_days=?, enabled=?, updated_at=?
                    WHERE vhost=? AND app=? AND stream=?
                    """,
                    (int(retention_days), enabled_int, now, vhost, app, stream),
                )
            else:
                db.execute(
                    """
                    INSERT INTO record_policy (vhost, app, stream, retention_days, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (vhost, app, stream, int(retention_days), enabled_int, now, now),
                )

        row = db.execute(
            """
            SELECT vhost, app, stream, retention_days, enabled, created_at, updated_at
            FROM record_policy
            WHERE vhost=? AND app=? AND stream=?
            """,
            (vhost, app, stream),
        ).fetchone()

    return dict(row) if row else {}


def delete_record_policy(*, vhost: str, app: str, stream: str) -> int:
    with get_db() as db:
        cur = db.execute(
            "DELETE FROM record_policy WHERE vhost=? AND app=? AND stream=?",
            (vhost, app, stream),
        )
        return int(cur.rowcount or 0)


def create_user(*, username: str, full_name: str, nickname: str, password_hash: str, role: str, must_change_password: bool = False, user_id: int | None = None, bound_mac: str = "", bound_ip: str = "") -> dict[str, Any]:
    now = _utc_now_iso()
    with get_db() as db:
        if user_id is None and role == "admin":
            admin_id = next(
                (
                    candidate
                    for candidate in range(BUILTIN_ADMIN_ID, RESERVED_ADMIN_ID_END + 1)
                    if not db.execute("SELECT 1 FROM user WHERE id=?", (candidate,)).fetchone()
                ),
                None,
            )
            if admin_id is None:
                raise ValueError("管理员保留 ID（1000-1005）已用完")
            db.execute(
                "INSERT INTO user (id, username, full_name, nickname, password_hash, role, enabled, must_change_password, bound_mac, bound_ip, password_changed_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                (admin_id, username, full_name, nickname, password_hash, role, int(must_change_password), bound_mac, bound_ip, now, now, now),
            )
        elif user_id is None:
            db.execute(
                "INSERT INTO user (username, full_name, nickname, password_hash, role, enabled, must_change_password, bound_mac, bound_ip, password_changed_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                (username, full_name, nickname, password_hash, role, int(must_change_password), bound_mac, bound_ip, now, now, now),
            )
        else:
            db.execute(
                "INSERT INTO user (id, username, full_name, nickname, password_hash, role, enabled, must_change_password, bound_mac, bound_ip, password_changed_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                (user_id, username, full_name, nickname, password_hash, role, int(must_change_password), bound_mac, bound_ip, now, now, now),
            )
    return get_user(username=username) or {}


def get_user(*, username: str) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM user WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT id, username, full_name, nickname, role, enabled, must_change_password, bound_mac, bound_ip, created_at, updated_at FROM user ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def update_user(*, username: str, full_name: str | None = None, nickname: str | None = None, role: str | None = None, enabled: bool | None = None, password_hash: str | None = None, must_change_password: bool | None = None, bound_mac: str | None = None, bound_ip: str | None = None) -> dict[str, Any] | None:
    changes: list[str] = []
    values: list[Any] = []
    if full_name is not None:
        changes.append("full_name=?")
        values.append(full_name)
    if nickname is not None:
        changes.append("nickname=?")
        values.append(nickname)
    if role is not None:
        changes.append("role=?")
        values.append(role)
    if enabled is not None:
        changes.append("enabled=?")
        values.append(1 if enabled else 0)
    if password_hash is not None:
        changes.append("password_hash=?")
        values.append(password_hash)
        changes.append("password_changed_at=?")
        values.append(_utc_now_iso())
    if must_change_password is not None:
        changes.append("must_change_password=?")
        values.append(1 if must_change_password else 0)
    if bound_mac is not None:
        changes.append("bound_mac=?")
        values.append(bound_mac)
    if bound_ip is not None:
        changes.append("bound_ip=?")
        values.append(bound_ip)
    if not changes:
        return get_user(username=username)
    changes.append("updated_at=?")
    values.extend([_utc_now_iso(), username])
    with get_db() as db:
        db.execute(f"UPDATE user SET {', '.join(changes)} WHERE username=?", values)
    return get_user(username=username)


def delete_user(*, username: str) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM user WHERE username=? AND id<>?", (username, BUILTIN_ADMIN_ID))
        return int(cur.rowcount or 0)


def get_platform_settings() -> dict[str, Any]:
    with get_db() as db:
        rows = db.execute("SELECT setting_key, setting_json FROM platform_setting").fetchall()
    result: dict[str, Any] = {}
    for row in rows:
        try:
            result[str(row["setting_key"])] = json.loads(str(row["setting_json"]))
        except json.JSONDecodeError:
            continue
    return result


def upsert_platform_settings(*, values: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now_iso()
    with get_db() as db:
        for key, value in values.items():
            db.execute("INSERT INTO platform_setting (setting_key, setting_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_json=excluded.setting_json, updated_at=excluded.updated_at", (key, json.dumps(value, ensure_ascii=True, separators=(",", ":")), now))
    return get_platform_settings()


def list_alarm_recipients() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM alarm_recipient ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def upsert_alarm_recipient(*, recipient_id: int | None, username: str, target_ip: str, enabled: bool) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            if recipient_id is None:
                cur = db.execute("INSERT INTO alarm_recipient (username, target_ip, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", (username, target_ip, int(enabled), now, now))
                recipient_id = int(cur.lastrowid)
            else:
                db.execute("UPDATE alarm_recipient SET username=?, target_ip=?, enabled=?, updated_at=? WHERE id=?", (username, target_ip, int(enabled), now, recipient_id))
            row = db.execute("SELECT * FROM alarm_recipient WHERE id=?", (recipient_id,)).fetchone()
        except sqlite3.IntegrityError:
            return None
    return dict(row) if row else None


def delete_alarm_recipient(*, recipient_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM alarm_recipient WHERE id=?", (recipient_id,))
    return int(cur.rowcount or 0)


def _alarm_query() -> str:
    return """SELECT e.*, r.name AS room_name, a.name AS area_name, d.name AS device_name
              FROM alarm_event e LEFT JOIN interview_room r ON r.id=e.room_id
              LEFT JOIN interview_area a ON a.id=r.area_id LEFT JOIN device d ON d.device_id=e.device_id"""


def create_alarm_event(*, room_id: int | None, device_id: str | None, source_type: str, severity: str, message: str, detail: dict[str, Any]) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        if room_id is not None and not db.execute("SELECT 1 FROM interview_room WHERE id=?", (room_id,)).fetchone():
            return None
        if device_id and not db.execute("SELECT 1 FROM device WHERE device_id=?", (device_id,)).fetchone():
            return None
        cur = db.execute("INSERT INTO alarm_event (room_id, device_id, source_type, severity, message, detail_json, occurred_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (room_id, device_id or None, source_type, severity, message, json.dumps(detail, ensure_ascii=True, separators=(",", ":")), now, now, now))
        for action_type in ("live_video", "alarm_record", "snapshot", "video_wall", "led_push"):
            db.execute("INSERT INTO alarm_linkage_action (alarm_id, action_type, detail_json, created_at) VALUES (?, ?, ?, ?)", (int(cur.lastrowid), action_type, "{}", now))
        row = db.execute(f"{_alarm_query()} WHERE e.id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def list_alarm_events(*, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with get_db() as db:
        sql = _alarm_query()
        if status:
            sql += " WHERE e.status=?"
        sql += " ORDER BY e.occurred_at DESC, e.id DESC LIMIT ?"
        rows = db.execute(sql, (status, limit) if status else (limit,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["detail"] = json.loads(item.pop("detail_json"))
        except json.JSONDecodeError:
            item["detail"] = {}
        result.append(item)
    return result


def get_alarm_event(*, alarm_id: int) -> dict[str, Any] | None:
    return next((item for item in list_alarm_events(limit=500) if int(item["id"]) == alarm_id), None)


def update_alarm_event_status(*, alarm_id: int, status: str, actor: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        event = db.execute("SELECT status FROM alarm_event WHERE id=?", (alarm_id,)).fetchone()
        if not event or status not in {"acknowledged", "resolved"} or (status == "acknowledged" and event["status"] != "active") or (status == "resolved" and event["status"] not in {"active", "acknowledged"}):
            return None
        if status == "acknowledged":
            db.execute("UPDATE alarm_event SET status=?, acknowledged_by=?, acknowledged_at=?, updated_at=? WHERE id=?", (status, actor, now, now, alarm_id))
        else:
            db.execute("UPDATE alarm_event SET status=?, resolved_by=?, resolved_at=?, updated_at=? WHERE id=?", (status, actor, now, now, alarm_id))
    return get_alarm_event(alarm_id=alarm_id)


def list_alarm_linkage_actions(*, alarm_id: int) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM alarm_linkage_action WHERE alarm_id=? ORDER BY id", (alarm_id,)).fetchall()
    return [dict(row) for row in rows]


def update_alarm_linkage_action(*, action_id: int, status: str, detail: dict[str, Any]) -> dict[str, Any] | None:
    with get_db() as db:
        db.execute("UPDATE alarm_linkage_action SET status=?, detail_json=?, completed_at=CASE WHEN ? IN ('succeeded', 'failed') THEN ? ELSE completed_at END WHERE id=?", (status, json.dumps(detail, ensure_ascii=True, separators=(",", ":")), status, _utc_now_iso(), action_id))
        row = db.execute("SELECT * FROM alarm_linkage_action WHERE id=?", (action_id,)).fetchone()
    return dict(row) if row else None


def list_access_points() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT p.*, d.name AS device_name, r.name AS room_name FROM access_point p LEFT JOIN device d ON d.device_id=p.device_id LEFT JOIN interview_room r ON r.id=p.room_id ORDER BY p.name, p.id").fetchall()
    return [dict(row) for row in rows]


def create_access_point(*, device_id: str | None, room_id: int | None, name: str, point_code: str, enabled: bool) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            cur = db.execute("INSERT INTO access_point (device_id, room_id, name, point_code, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (device_id, room_id, name, point_code, int(enabled), now, now))
        except sqlite3.IntegrityError:
            return None
        row = db.execute("SELECT * FROM access_point WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def update_access_point(*, point_id: int, device_id: str | None, room_id: int | None, name: str, point_code: str, enabled: bool) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            db.execute("UPDATE access_point SET device_id=?, room_id=?, name=?, point_code=?, enabled=?, updated_at=? WHERE id=?", (device_id, room_id, name, point_code, int(enabled), now, point_id))
        except sqlite3.IntegrityError:
            return None
        row = db.execute("SELECT * FROM access_point WHERE id=?", (point_id,)).fetchone()
    return dict(row) if row else None


def delete_access_point(*, point_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM access_point WHERE id=?", (point_id,))
    return int(cur.rowcount or 0)


def list_access_permissions(*, personnel_id: int | None = None) -> list[dict[str, Any]]:
    with get_db() as db:
        sql = "SELECT ap.*, p.name AS personnel_name, p.employee_no, point.name AS point_name, point.point_code, r.name AS room_name FROM access_permission ap JOIN personnel p ON p.id=ap.personnel_id JOIN access_point point ON point.id=ap.access_point_id LEFT JOIN interview_room r ON r.id=point.room_id"
        if personnel_id is not None:
            sql += " WHERE ap.personnel_id=?"
        sql += " ORDER BY ap.updated_at DESC, ap.id DESC"
        rows = db.execute(sql, (personnel_id,) if personnel_id is not None else ()).fetchall()
    return [dict(row) for row in rows]


def upsert_access_permission(*, point_id: int, personnel_id: int, valid_from: str | None, valid_to: str | None, schedule_template: str, holiday_plan: str, auth_method: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        if not db.execute("SELECT 1 FROM access_point WHERE id=?", (point_id,)).fetchone() or not db.execute("SELECT 1 FROM personnel WHERE id=?", (personnel_id,)).fetchone():
            return None
        db.execute("INSERT INTO access_permission (access_point_id, personnel_id, valid_from, valid_to, schedule_template, holiday_plan, auth_method, delivery_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?) ON CONFLICT(access_point_id, personnel_id) DO UPDATE SET valid_from=excluded.valid_from, valid_to=excluded.valid_to, schedule_template=excluded.schedule_template, holiday_plan=excluded.holiday_plan, auth_method=excluded.auth_method, delivery_status='pending', updated_at=excluded.updated_at", (point_id, personnel_id, valid_from, valid_to, schedule_template, holiday_plan, auth_method, now, now))
        row = db.execute("SELECT * FROM access_permission WHERE access_point_id=? AND personnel_id=?", (point_id, personnel_id)).fetchone()
    return dict(row) if row else None


def update_access_permission_delivery(*, permission_id: int, status: str) -> dict[str, Any] | None:
    with get_db() as db:
        db.execute("UPDATE access_permission SET delivery_status=?, updated_at=? WHERE id=?", (status, _utc_now_iso(), permission_id))
        row = db.execute("SELECT * FROM access_permission WHERE id=?", (permission_id,)).fetchone()
    return dict(row) if row else None


def delete_access_permission(*, permission_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM access_permission WHERE id=?", (permission_id,))
    return int(cur.rowcount or 0)


def create_access_event(*, point_id: int, personnel_id: int | None, direction: str, event_time: str, snapshot_url: str, detail: dict[str, Any]) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        if not db.execute("SELECT 1 FROM access_point WHERE id=?", (point_id,)).fetchone():
            return None
        cur = db.execute("INSERT INTO access_event (access_point_id, personnel_id, direction, event_time, snapshot_url, detail_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (point_id, personnel_id, direction, event_time, snapshot_url, json.dumps(detail, ensure_ascii=True, separators=(",", ":")), now))
        row = db.execute("SELECT * FROM access_event WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def list_access_events(*, limit: int = 200) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT e.*, point.name AS point_name, point.point_code, p.name AS personnel_name, p.employee_no FROM access_event e JOIN access_point point ON point.id=e.access_point_id LEFT JOIN personnel p ON p.id=e.personnel_id ORDER BY e.event_time DESC, e.id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def create_remote_command(*, session_id: int, command_type: str, content: str, sent_by: str, detail: dict[str, Any] | None = None) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        session = db.execute("SELECT case_id FROM case_session WHERE id=? AND status IN ('active', 'finalizing')", (session_id,)).fetchone()
        if not session:
            return None
        cur = db.execute("INSERT INTO remote_command (session_id, command_type, content, detail_json, sent_by, sent_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (session_id, command_type, content, json.dumps(detail or {}, ensure_ascii=True, separators=(",", ":")), sent_by, now, now))
        _add_case_audit(db=db, case_id=int(session["case_id"]), session_id=session_id, action="remote_command.sent", actor=sent_by, detail={"command_id": int(cur.lastrowid), "command_type": command_type, "has_detail": bool(detail)})
        row = db.execute("SELECT * FROM remote_command WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def list_remote_commands(*, session_id: int, include_acknowledged: bool = True) -> list[dict[str, Any]]:
    with get_db() as db:
        sql = "SELECT * FROM remote_command WHERE session_id=?"
        if not include_acknowledged:
            sql += " AND status='sent'"
        rows = db.execute(sql + " ORDER BY id DESC", (session_id,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["detail"] = json.loads(item.pop("detail_json"))
        except (json.JSONDecodeError, TypeError):
            item["detail"] = {}
        result.append(item)
    return result


def acknowledge_remote_command(*, command_id: int, actor: str) -> dict[str, Any] | None:
    return complete_remote_command(command_id=command_id, actor=actor, status="acknowledged", detail={})


def complete_remote_command(*, command_id: int, actor: str, status: str, detail: dict[str, Any]) -> dict[str, Any] | None:
    if status not in {"acknowledged", "completed", "failed"}:
        return None
    now = _utc_now_iso()
    with get_db() as db:
        command = db.execute("SELECT c.session_id, c.detail_json, s.case_id FROM remote_command c JOIN case_session s ON s.id=c.session_id WHERE c.id=? AND c.status='sent'", (command_id,)).fetchone()
        if not command:
            return None
        try:
            command_detail = json.loads(str(command["detail_json"]))
        except json.JSONDecodeError:
            command_detail = {}
        command_detail["device_result"] = status
        command_detail["device_detail"] = detail
        db.execute("UPDATE remote_command SET status=?, detail_json=?, acknowledged_by=?, acknowledged_at=? WHERE id=?", (status, json.dumps(command_detail, ensure_ascii=True, separators=(",", ":")), actor, now, command_id))
        _add_case_audit(db=db, case_id=int(command["case_id"]), session_id=int(command["session_id"]), action=f"remote_command.{status}", actor=actor, detail={"command_id": command_id, "has_device_detail": bool(detail)})
        row = db.execute("SELECT * FROM remote_command WHERE id=?", (command_id,)).fetchone()
    return dict(row) if row else None


def cancel_remote_command(*, command_id: int, actor: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        command = db.execute("SELECT c.session_id, s.case_id FROM remote_command c JOIN case_session s ON s.id=c.session_id WHERE c.id=? AND c.status='sent'", (command_id,)).fetchone()
        if not command:
            return None
        db.execute("UPDATE remote_command SET status='cancelled', acknowledged_by=?, acknowledged_at=? WHERE id=?", (actor, now, command_id))
        _add_case_audit(db=db, case_id=int(command["case_id"]), session_id=int(command["session_id"]), action="remote_command.cancelled", actor=actor, detail={"command_id": command_id})
        row = db.execute("SELECT * FROM remote_command WHERE id=?", (command_id,)).fetchone()
    return dict(row) if row else None


def create_organization(*, parent_id: int | None, name: str, code: str, sort_order: int, enabled: bool) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        if parent_id is not None and not db.execute("SELECT 1 FROM organization WHERE id=?", (parent_id,)).fetchone():
            return None
        try:
            cur = db.execute("INSERT INTO organization (parent_id, name, code, sort_order, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (parent_id, name, code, sort_order, int(enabled), now, now))
        except sqlite3.IntegrityError:
            return None
    return get_organization(organization_id=int(cur.lastrowid))


def get_organization(*, organization_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT o.*, parent.name AS parent_name, COUNT(DISTINCT p.id) AS personnel_count FROM organization o LEFT JOIN organization parent ON parent.id=o.parent_id LEFT JOIN personnel p ON p.organization_id=o.id WHERE o.id=? GROUP BY o.id", (organization_id,)).fetchone()
    return dict(row) if row else None


def list_organizations() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT o.*, parent.name AS parent_name, COUNT(DISTINCT p.id) AS personnel_count FROM organization o LEFT JOIN organization parent ON parent.id=o.parent_id LEFT JOIN personnel p ON p.organization_id=o.id GROUP BY o.id ORDER BY COALESCE(o.parent_id, 0), o.sort_order, o.id").fetchall()
    return [dict(row) for row in rows]


def update_organization(*, organization_id: int, parent_id: int | None, name: str, code: str, sort_order: int, enabled: bool) -> dict[str, Any] | None:
    if parent_id == organization_id:
        return None
    with get_db() as db:
        if parent_id is not None and not db.execute("SELECT 1 FROM organization WHERE id=?", (parent_id,)).fetchone():
            return None
        try:
            updated = db.execute("UPDATE organization SET parent_id=?, name=?, code=?, sort_order=?, enabled=?, updated_at=? WHERE id=?", (parent_id, name, code, sort_order, int(enabled), _utc_now_iso(), organization_id)).rowcount
        except sqlite3.IntegrityError:
            return None
    return get_organization(organization_id=organization_id) if updated else None


def delete_organization(*, organization_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM organization WHERE id=?", (organization_id,))
    return int(cur.rowcount or 0)


def create_personnel(*, organization_id: int | None, name: str, employee_no: str, identity_no: str, phone: str, title: str, username: str | None, enabled: bool) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        if organization_id is not None and not db.execute("SELECT 1 FROM organization WHERE id=?", (organization_id,)).fetchone():
            return None
        try:
            cur = db.execute("INSERT INTO personnel (organization_id, name, employee_no, identity_no, phone, title, username, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, name, employee_no, identity_no, phone, title, username, int(enabled), now, now))
        except sqlite3.IntegrityError:
            return None
    return get_personnel(personnel_id=int(cur.lastrowid))


def get_personnel(*, personnel_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT p.*, o.name AS organization_name, u.role AS account_role, u.enabled AS account_enabled FROM personnel p LEFT JOIN organization o ON o.id=p.organization_id LEFT JOIN user u ON u.username=p.username WHERE p.id=?", (personnel_id,)).fetchone()
    return dict(row) if row else None


def list_personnel(*, keyword: str = "") -> list[dict[str, Any]]:
    with get_db() as db:
        if keyword:
            token = f"%{keyword}%"
            rows = db.execute("SELECT p.*, o.name AS organization_name, u.role AS account_role, u.enabled AS account_enabled FROM personnel p LEFT JOIN organization o ON o.id=p.organization_id LEFT JOIN user u ON u.username=p.username WHERE p.name LIKE ? OR p.employee_no LIKE ? OR p.phone LIKE ? ORDER BY p.id DESC", (token, token, token)).fetchall()
        else:
            rows = db.execute("SELECT p.*, o.name AS organization_name, u.role AS account_role, u.enabled AS account_enabled FROM personnel p LEFT JOIN organization o ON o.id=p.organization_id LEFT JOIN user u ON u.username=p.username ORDER BY p.id DESC").fetchall()
    return [dict(row) for row in rows]


def update_personnel(*, personnel_id: int, organization_id: int | None, name: str, employee_no: str, identity_no: str, phone: str, title: str, enabled: bool) -> dict[str, Any] | None:
    with get_db() as db:
        if organization_id is not None and not db.execute("SELECT 1 FROM organization WHERE id=?", (organization_id,)).fetchone():
            return None
        try:
            updated = db.execute("UPDATE personnel SET organization_id=?, name=?, employee_no=?, identity_no=?, phone=?, title=?, enabled=?, updated_at=? WHERE id=?", (organization_id, name, employee_no, identity_no, phone, title, int(enabled), _utc_now_iso(), personnel_id)).rowcount
        except sqlite3.IntegrityError:
            return None
    return get_personnel(personnel_id=personnel_id) if updated else None


def delete_personnel(*, personnel_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM personnel WHERE id=?", (personnel_id,))
    return int(cur.rowcount or 0)


def upsert_device(*, device_id: str, name: str, access_key: str, serial_number: str | None = None, address: str | None = None, web_url: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _utc_now_iso()
    with get_db() as db:
        db.execute(
                """INSERT INTO device (device_id, name, serial_number, address, web_url, access_key, access_key_display, status, last_seen_at, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'online', ?, ?, ?, ?)
               ON CONFLICT(device_id) DO UPDATE SET name=excluded.name, serial_number=excluded.serial_number,
                    address=excluded.address, web_url=excluded.web_url, access_key=excluded.access_key, access_key_display=excluded.access_key_display, status='online',
               last_seen_at=excluded.last_seen_at, metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
                (device_id, name, serial_number, address, web_url, _hash_access_key(access_key), access_key, now, json.dumps(metadata or {}, ensure_ascii=True), now, now),
        )
    return get_device(device_id=device_id) or {}


def create_device(*, device_id: str, name: str, access_key: str, serial_number: str | None = None, address: str | None = None, web_url: str | None = None, enabled: bool = False) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            db.execute(
                     """INSERT INTO device (device_id, name, serial_number, address, web_url, access_key, access_key_display, enabled, status, metadata_json, created_at, updated_at)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'offline', '{}', ?, ?)""",
                     (device_id, name, serial_number, address, web_url, _hash_access_key(access_key), access_key, int(enabled), now, now),
            )
        except sqlite3.IntegrityError:
            return None
    return get_device(device_id=device_id)


def update_device(*, device_id: str, name: str | None = None, serial_number: str | None = None, address: str | None = None, web_url: str | None = None, enabled: bool | None = None) -> dict[str, Any] | None:
    changes: list[str] = []
    values: list[Any] = []
    if name is not None:
        changes.append("name=?")
        values.append(name)
    if serial_number is not None:
        changes.append("serial_number=?")
        values.append(serial_number)
    if address is not None:
        changes.append("address=?")
        values.append(address)
    if web_url is not None:
        changes.append("web_url=?")
        values.append(web_url)
    if enabled is not None:
        changes.append("enabled=?")
        values.append(int(enabled))
        changes.append("status=CASE WHEN ? THEN status ELSE 'offline' END")
        values.append(int(enabled))
    if not changes:
        return get_device(device_id=device_id)
    now = _utc_now_iso()
    with get_db() as db:
        changes.append("updated_at=?")
        values.extend([now, device_id])
        db.execute(f"UPDATE device SET {', '.join(changes)} WHERE device_id=?", values)
    return get_device(device_id=device_id)


def delete_device(*, device_id: str) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM device WHERE device_id=?", (device_id,))
        return int(cur.rowcount or 0)


def get_device_access_key(*, device_id: str) -> str | None:
    with get_db() as db:
        row = db.execute("SELECT access_key_display FROM device WHERE device_id=?", (device_id,)).fetchone()
    return str(row["access_key_display"]) if row and row["access_key_display"] else None


def rotate_device_access_key(*, device_id: str, access_key: str) -> bool:
    now = _utc_now_iso()
    with get_db() as db:
        updated = db.execute(
            "UPDATE device SET access_key=?, access_key_display=?, updated_at=? WHERE device_id=?",
            (_hash_access_key(access_key), access_key, now, device_id),
        ).rowcount
    return bool(updated)


def get_device(*, device_id: str) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM device WHERE device_id=?", (device_id,)).fetchone()
    return _serialize_device(row)


def list_devices() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            """SELECT d.*,
               (SELECT COUNT(*) FROM case_device_assignment a WHERE a.device_id=d.device_id AND a.status='pending') AS pending_case_count,
               (SELECT COUNT(*) FROM case_device_assignment a WHERE a.device_id=d.device_id AND a.status IN ('received', 'handling')) AS active_case_count,
               (SELECT COUNT(*) FROM case_session s WHERE s.device_id=d.device_id AND s.status='active') AS active_session_count,
               (SELECT GROUP_CONCAT(c.case_no, '、') FROM case_device_assignment a JOIN case_info c ON c.id=a.case_id WHERE a.device_id=d.device_id AND a.status IN ('received', 'handling') AND c.status NOT IN ('closed', 'archived')) AS active_case_nos
               FROM device d ORDER BY d.updated_at DESC"""
        ).fetchall()
    return [result for row in rows if (result := _serialize_device(row))]


def device_has_active_case_work(*, device_id: str) -> bool:
    with get_db() as db:
        row = db.execute(
            """SELECT EXISTS(SELECT 1 FROM case_device_assignment WHERE device_id=? AND status IN ('received', 'handling'))
                     OR EXISTS(SELECT 1 FROM case_session WHERE device_id=? AND status='active') AS has_active_work""",
            (device_id, device_id),
        ).fetchone()
    return bool(row and row["has_active_work"])


def device_has_case_history(*, device_id: str) -> bool:
    with get_db() as db:
        row = db.execute(
            """SELECT EXISTS(SELECT 1 FROM case_device_assignment WHERE device_id=?)
                     OR EXISTS(SELECT 1 FROM case_session WHERE device_id=?)
                     OR EXISTS(SELECT 1 FROM case_recording_binding WHERE device_id=?) AS has_history""",
            (device_id, device_id, device_id),
        ).fetchone()
    return bool(row and row["has_history"])


def create_business_directory(*, name: str, code: str, description: str, sort_order: int, enabled: bool) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            cur = db.execute("INSERT INTO business_directory (name, code, description, sort_order, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, code, description, sort_order, int(enabled), now, now))
        except sqlite3.IntegrityError:
            return None
    return get_business_directory(directory_id=int(cur.lastrowid))


def get_business_directory(*, directory_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT d.*, COUNT(DISTINCT a.id) AS area_count, COUNT(DISTINCT r.id) AS room_count FROM business_directory d LEFT JOIN interview_area a ON a.directory_id=d.id LEFT JOIN interview_room r ON r.area_id=a.id WHERE d.id=? GROUP BY d.id", (directory_id,)).fetchone()
    return dict(row) if row else None


def list_business_directories() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT d.*, COUNT(DISTINCT a.id) AS area_count, COUNT(DISTINCT r.id) AS room_count FROM business_directory d LEFT JOIN interview_area a ON a.directory_id=d.id LEFT JOIN interview_room r ON r.area_id=a.id GROUP BY d.id ORDER BY d.sort_order, d.id").fetchall()
    return [dict(row) for row in rows]


def update_business_directory(*, directory_id: int, name: str, code: str, description: str, sort_order: int, enabled: bool) -> dict[str, Any] | None:
    with get_db() as db:
        try:
            updated = db.execute("UPDATE business_directory SET name=?, code=?, description=?, sort_order=?, enabled=?, updated_at=? WHERE id=?", (name, code, description, sort_order, int(enabled), _utc_now_iso(), directory_id)).rowcount
        except sqlite3.IntegrityError:
            return None
    return get_business_directory(directory_id=directory_id) if updated else None


def delete_business_directory(*, directory_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM business_directory WHERE id=?", (directory_id,))
    return int(cur.rowcount or 0)


def create_interview_area(*, directory_id: int, name: str, location: str, sort_order: int, enabled: bool) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            cur = db.execute("INSERT INTO interview_area (directory_id, name, location, sort_order, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (directory_id, name, location, sort_order, int(enabled), now, now))
        except sqlite3.IntegrityError:
            return None
    return get_interview_area(area_id=int(cur.lastrowid))


def get_interview_area(*, area_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT a.*, d.name AS directory_name, COUNT(r.id) AS room_count FROM interview_area a JOIN business_directory d ON d.id=a.directory_id LEFT JOIN interview_room r ON r.area_id=a.id WHERE a.id=? GROUP BY a.id", (area_id,)).fetchone()
    return dict(row) if row else None


def list_interview_areas(*, directory_id: int | None = None) -> list[dict[str, Any]]:
    with get_db() as db:
        sql = "SELECT a.*, d.name AS directory_name, COUNT(r.id) AS room_count FROM interview_area a JOIN business_directory d ON d.id=a.directory_id LEFT JOIN interview_room r ON r.area_id=a.id"
        if directory_id is not None:
            sql += " WHERE a.directory_id=?"
        sql += " GROUP BY a.id ORDER BY d.sort_order, a.sort_order, a.id"
        rows = db.execute(sql, (directory_id,) if directory_id is not None else ()).fetchall()
    return [dict(row) for row in rows]


def update_interview_area(*, area_id: int, directory_id: int, name: str, location: str, sort_order: int, enabled: bool) -> dict[str, Any] | None:
    with get_db() as db:
        try:
            updated = db.execute("UPDATE interview_area SET directory_id=?, name=?, location=?, sort_order=?, enabled=?, updated_at=? WHERE id=?", (directory_id, name, location, sort_order, int(enabled), _utc_now_iso(), area_id)).rowcount
        except sqlite3.IntegrityError:
            return None
    return get_interview_area(area_id=area_id) if updated else None


def delete_interview_area(*, area_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM interview_area WHERE id=?", (area_id,))
    return int(cur.rowcount or 0)


def create_interview_room(*, area_id: int, name: str, room_type: str, capacity: int, location: str, enabled: bool) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            cur = db.execute("INSERT INTO interview_room (area_id, name, room_type, capacity, location, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (area_id, name, room_type, capacity, location, int(enabled), now, now))
        except sqlite3.IntegrityError:
            return None
    return get_interview_room(room_id=int(cur.lastrowid))


def get_interview_room(*, room_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT r.*, a.name AS area_name, a.directory_id, d.name AS directory_name, COUNT(rd.device_id) AS device_count, GROUP_CONCAT(dev.name, '、') AS device_names FROM interview_room r JOIN interview_area a ON a.id=r.area_id JOIN business_directory d ON d.id=a.directory_id LEFT JOIN interview_room_device rd ON rd.room_id=r.id LEFT JOIN device dev ON dev.device_id=rd.device_id WHERE r.id=? GROUP BY r.id", (room_id,)).fetchone()
    return dict(row) if row else None


def list_interview_rooms(*, area_id: int | None = None) -> list[dict[str, Any]]:
    with get_db() as db:
        sql = "SELECT r.*, a.name AS area_name, a.directory_id, d.name AS directory_name, COUNT(rd.device_id) AS device_count, GROUP_CONCAT(dev.name, '、') AS device_names FROM interview_room r JOIN interview_area a ON a.id=r.area_id JOIN business_directory d ON d.id=a.directory_id LEFT JOIN interview_room_device rd ON rd.room_id=r.id LEFT JOIN device dev ON dev.device_id=rd.device_id"
        if area_id is not None:
            sql += " WHERE r.area_id=?"
        sql += " GROUP BY r.id ORDER BY d.sort_order, a.sort_order, r.name, r.id"
        rows = db.execute(sql, (area_id,) if area_id is not None else ()).fetchall()
    return [dict(row) for row in rows]


def update_interview_room(*, room_id: int, area_id: int, name: str, room_type: str, capacity: int, location: str, enabled: bool) -> dict[str, Any] | None:
    with get_db() as db:
        try:
            updated = db.execute("UPDATE interview_room SET area_id=?, name=?, room_type=?, capacity=?, location=?, enabled=?, updated_at=? WHERE id=?", (area_id, name, room_type, capacity, location, int(enabled), _utc_now_iso(), room_id)).rowcount
        except sqlite3.IntegrityError:
            return None
    return get_interview_room(room_id=room_id) if updated else None


def delete_interview_room(*, room_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM interview_room WHERE id=?", (room_id,))
    return int(cur.rowcount or 0)


def list_interview_room_devices(*, room_id: int) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT d.device_id, d.name, d.serial_number, d.address, d.status, d.enabled FROM interview_room_device rd JOIN device d ON d.device_id=rd.device_id WHERE rd.room_id=? ORDER BY d.name, d.device_id", (room_id,)).fetchall()
    return [dict(row) for row in rows]


def assign_device_to_interview_room(*, room_id: int, device_id: str) -> bool:
    now = _utc_now_iso()
    with get_db() as db:
        room = db.execute("SELECT 1 FROM interview_room WHERE id=?", (room_id,)).fetchone()
        device = db.execute("SELECT 1 FROM device WHERE device_id=?", (device_id,)).fetchone()
        active = db.execute("SELECT 1 FROM case_session WHERE device_id=? AND status NOT IN ('ended', 'cancelled') LIMIT 1", (device_id,)).fetchone()
        if not room or not device or active:
            return False
        db.execute("INSERT INTO interview_room_device (room_id, device_id, created_at) VALUES (?, ?, ?) ON CONFLICT(device_id) DO UPDATE SET room_id=excluded.room_id, created_at=excluded.created_at", (room_id, device_id, now))
    return True


def remove_device_from_interview_room(*, room_id: int, device_id: str) -> bool:
    with get_db() as db:
        active = db.execute("SELECT 1 FROM case_session WHERE device_id=? AND status NOT IN ('ended', 'cancelled') LIMIT 1", (device_id,)).fetchone()
        if active:
            return False
        return bool(db.execute("DELETE FROM interview_room_device WHERE room_id=? AND device_id=?", (room_id, device_id)).rowcount)


def _serialize_device(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if not row:
        return None
    result = dict(row)
    result.pop("access_key", None)
    result["access_key_masked"] = "********" if result.pop("access_key_display", "") else "需重新生成"
    try:
        result["metadata"] = json.loads(result.pop("metadata_json", "{}"))
    except json.JSONDecodeError:
        result["metadata"] = {}
    return result


def verify_device_key(*, device_id: str, access_key: str) -> bool:
    with get_db() as db:
        row = db.execute("SELECT access_key FROM device WHERE device_id=?", (device_id,)).fetchone()
    return bool(row and _verify_access_key(access_key, str(row["access_key"])))


def touch_device(*, device_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        if metadata is None:
            db.execute("UPDATE device SET status='online', last_seen_at=?, updated_at=? WHERE device_id=?", (now, now, device_id))
        else:
            db.execute("UPDATE device SET status='online', last_seen_at=?, metadata_json=?, updated_at=? WHERE device_id=?", (now, json.dumps(metadata, ensure_ascii=True), now, device_id))
    return get_device(device_id=device_id)


def mark_stale_devices_offline(*, stale_seconds: int) -> int:
    with get_db() as db:
        cur = db.execute(
            "UPDATE device SET status='offline' WHERE last_seen_at IS NULL OR CAST(strftime('%s', last_seen_at) AS INTEGER) < CAST(strftime('%s', 'now') AS INTEGER) - ?",
            (int(stale_seconds),),
        )
        return int(cur.rowcount or 0)


def upsert_gb28181_device(*, device_id: str, address: str, sip_port: int, expires_seconds: int) -> None:
    now = _utc_now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)).isoformat(timespec="seconds")
    with get_db() as db:
        db.execute(
            """INSERT INTO gb28181_device (device_id, address, sip_port, status, expires_at, last_seen_at, created_at, updated_at)
               VALUES (?, ?, ?, 'online', ?, ?, ?, ?)
               ON CONFLICT(device_id) DO UPDATE SET address=excluded.address, sip_port=excluded.sip_port,
               status='online', expires_at=excluded.expires_at, last_seen_at=excluded.last_seen_at, updated_at=excluded.updated_at""",
            (device_id, address, sip_port, expires_at, now, now, now),
        )


def touch_gb28181_device(*, device_id: str, address: str, sip_port: int, keepalive: bool) -> None:
    now = _utc_now_iso()
    with get_db() as db:
        db.execute(
            """UPDATE gb28181_device SET address=?, sip_port=?, status='online', last_seen_at=?,
               expires_at=CASE WHEN expires_at < ? THEN ? ELSE expires_at END,
               keepalive_count=keepalive_count + ?, updated_at=? WHERE device_id=?""",
            (address, sip_port, now, now, now, int(keepalive), now, device_id),
        )


def replace_gb28181_channels(*, device_id: str, channels: list[dict[str, str]]) -> None:
    now = _utc_now_iso()
    with get_db() as db:
        db.execute("DELETE FROM gb28181_channel WHERE device_id=?", (device_id,))
        db.executemany(
            "INSERT INTO gb28181_channel (device_id, channel_id, name, status, updated_at) VALUES (?, ?, ?, ?, ?)",
            [(device_id, item["channel_id"], item.get("name", ""), item.get("status", "ON"), now) for item in channels],
        )


def list_gb28181_devices() -> list[dict[str, Any]]:
    now = _utc_now_iso()
    with get_db() as db:
        db.execute("UPDATE gb28181_device SET status='offline' WHERE expires_at < ?", (now,))
        devices = [dict(row) for row in db.execute("SELECT * FROM gb28181_device ORDER BY last_seen_at DESC").fetchall()]
        channels = db.execute("SELECT * FROM gb28181_channel ORDER BY device_id, channel_id").fetchall()
    channels_by_device: dict[str, list[dict[str, Any]]] = {}
    for channel in channels:
        channels_by_device.setdefault(str(channel["device_id"]), []).append(dict(channel))
    for device in devices:
        device["channels"] = channels_by_device.get(str(device["device_id"]), [])
    return devices


def upsert_channel(*, device_id: str, channel_no: int, name: str, vhost: str, app: str | None, stream: str | None, keywords: str = "") -> dict[str, Any]:
    now = _utc_now_iso()
    with get_db() as db:
        db.execute(
            """INSERT INTO device_channel (device_id, channel_no, name, vhost, app, stream, keywords, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(device_id, channel_no) DO UPDATE SET name=excluded.name, vhost=excluded.vhost,
               app=excluded.app, stream=excluded.stream, keywords=excluded.keywords, updated_at=excluded.updated_at""",
            (device_id, channel_no, name, vhost, app, stream, keywords, now, now),
        )
        row = db.execute("SELECT * FROM device_channel WHERE device_id=? AND channel_no=?", (device_id, channel_no)).fetchone()
    return dict(row) if row else {}


def list_channels(*, device_id: str | None = None) -> list[dict[str, Any]]:
    with get_db() as db:
        if device_id:
            rows = db.execute("SELECT c.*, d.name AS device_name FROM device_channel c JOIN device d ON d.device_id=c.device_id WHERE c.device_id=? ORDER BY c.channel_no", (device_id,)).fetchall()
        else:
            rows = db.execute("SELECT c.*, d.name AS device_name FROM device_channel c JOIN device d ON d.device_id=c.device_id ORDER BY d.name, c.channel_no").fetchall()
    return [dict(row) for row in rows]


def list_record_schedules() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT s.*, c.device_id, c.channel_no, c.name AS channel_name, d.name AS device_name, c.vhost, c.app, c.stream FROM record_schedule s JOIN device_channel c ON c.id=s.channel_id JOIN device d ON d.device_id=c.device_id ORDER BY s.id DESC").fetchall()
    return [dict(row) for row in rows]


def upsert_record_schedule(*, schedule_id: int | None, channel_id: int, weekdays: str, start_time: str, end_time: str, retention_days: int, enabled: bool) -> dict[str, Any]:
    now = _utc_now_iso()
    with get_db() as db:
        if schedule_id:
            db.execute("UPDATE record_schedule SET channel_id=?, weekdays=?, start_time=?, end_time=?, retention_days=?, enabled=?, updated_at=? WHERE id=?", (channel_id, weekdays, start_time, end_time, retention_days, int(enabled), now, schedule_id))
        else:
            cur = db.execute("INSERT INTO record_schedule (channel_id, weekdays, start_time, end_time, retention_days, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (channel_id, weekdays, start_time, end_time, retention_days, int(enabled), now, now))
            schedule_id = int(cur.lastrowid)
        row = db.execute("SELECT * FROM record_schedule WHERE id=?", (schedule_id,)).fetchone()
    return dict(row) if row else {}


def delete_record_schedule(*, schedule_id: int) -> int:
    with get_db() as db:
        cur = db.execute("DELETE FROM record_schedule WHERE id=?", (schedule_id,))
        return int(cur.rowcount or 0)


def list_archive_folders(*, device_id: str | None = None) -> list[dict[str, Any]]:
    with get_db() as db:
        if device_id:
            rows = db.execute("SELECT * FROM device_archive_folder WHERE device_id=? ORDER BY name COLLATE NOCASE, id", (device_id,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM device_archive_folder ORDER BY device_id, name COLLATE NOCASE, id").fetchall()
    return [dict(row) for row in rows]


def create_archive_folder(*, device_id: str, name: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            cur = db.execute("INSERT INTO device_archive_folder (device_id, name, created_at, updated_at) VALUES (?, ?, ?, ?)", (device_id, name, now, now))
        except sqlite3.IntegrityError:
            return None
        row = db.execute("SELECT * FROM device_archive_folder WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def get_archive_folder(*, folder_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM device_archive_folder WHERE id=?", (folder_id,)).fetchone()
    return dict(row) if row else None


def _archive_file_query() -> str:
    return """SELECT f.*, d.name AS device_name, folder.name AS folder_name, c.case_no, c.name AS case_name,
              s.session_no, s.session_type, s.status AS session_status
              FROM device_archive_file f JOIN device d ON d.device_id=f.device_id
              LEFT JOIN device_archive_folder folder ON folder.id=f.folder_id
              LEFT JOIN case_info c ON c.id=f.case_id
              LEFT JOIN case_session s ON s.id=f.session_id"""


def _case_is_mutable(db: sqlite3.Connection, case_id: int) -> bool:
    row = db.execute("SELECT status FROM case_info WHERE id=?", (case_id,)).fetchone()
    return bool(row and row["status"] not in {"closed", "archived"})


def create_archive_file(*, device_id: str, case_id: int | None, session_id: int | None = None, folder_id: int | None, archive_type: str, status: str, title: str, original_name: str, stored_name: str, file_size: int, content_type: str | None, sha256: str = "", uploaded_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        if case_id is not None and not _case_is_mutable(db, case_id):
            return None
        cur = db.execute(
            """INSERT INTO device_archive_file (device_id, case_id, session_id, folder_id, archive_type, status, title, original_name, stored_name, file_size, content_type, sha256, uploaded_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (device_id, case_id, session_id, folder_id, archive_type, status, title, original_name, stored_name, int(file_size), content_type, sha256, uploaded_by, now, now),
        )
        if case_id is not None:
            _add_case_audit(db=db, case_id=case_id, session_id=session_id, action="evidence.uploaded", actor=uploaded_by, detail={"archive_id": int(cur.lastrowid), "archive_type": archive_type, "original_name": original_name, "sha256": sha256, "file_size": int(file_size)})
        row = db.execute(f"{_archive_file_query()} WHERE f.id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def list_archive_files(*, device_id: str | None = None) -> list[dict[str, Any]]:
    with get_db() as db:
        sql = _archive_file_query()
        rows = db.execute(f"{sql} {'WHERE f.device_id=?' if device_id else ''} ORDER BY f.updated_at DESC, f.id DESC", (device_id,) if device_id else ()).fetchall()
    return [dict(row) for row in rows]


def get_archive_file(*, archive_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute(f"{_archive_file_query()} WHERE f.id=?", (archive_id,)).fetchone()
    return dict(row) if row else None


def update_archive_file(*, archive_id: int, status: str | None = None, title: str | None = None, folder_id: int | None = None, update_folder: bool = False) -> dict[str, Any] | None:
    changes: list[str] = []
    values: list[Any] = []
    if status is not None:
        changes.append("status=?")
        values.append(status)
    if title is not None:
        changes.append("title=?")
        values.append(title)
    if update_folder:
        changes.append("folder_id=?")
        values.append(folder_id)
    if not changes:
        return get_archive_file(archive_id=archive_id)
    changes.append("updated_at=?")
    values.extend([_utc_now_iso(), archive_id])
    with get_db() as db:
        archive = db.execute("SELECT case_id FROM device_archive_file WHERE id=?", (archive_id,)).fetchone()
        if not archive or (archive["case_id"] is not None and not _case_is_mutable(db, int(archive["case_id"]))):
            return None
        db.execute(f"UPDATE device_archive_file SET {', '.join(changes)} WHERE id=?", values)
    return get_archive_file(archive_id=archive_id)


def delete_archive_file(*, archive_id: int) -> int:
    with get_db() as db:
        archive = db.execute("SELECT case_id FROM device_archive_file WHERE id=?", (archive_id,)).fetchone()
        if not archive or (archive["case_id"] is not None and not _case_is_mutable(db, int(archive["case_id"]))):
            return 0
        cur = db.execute("DELETE FROM device_archive_file WHERE id=?", (archive_id,))
    return int(cur.rowcount or 0)


def _case_query() -> str:
    return """SELECT c.*, COUNT(a.id) AS assigned_device_count,
              GROUP_CONCAT(d.name, '、') AS assigned_device_names
              FROM case_info c
              LEFT JOIN case_device_assignment a ON a.case_id=c.id
              LEFT JOIN device d ON d.device_id=a.device_id"""


def create_case(*, case_no: str, name: str, case_type: str, handling_unit: str, case_reason: str = "", lead_investigator: str = "", created_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        try:
            cur = db.execute(
                     """INSERT INTO case_info (case_no, name, case_type, handling_unit, case_reason, lead_investigator, status, created_by, created_at, updated_at)
                         VALUES (?, ?, ?, ?, ?, ?, 'created', ?, ?, ?)""",
                     (case_no, name, case_type, handling_unit, case_reason, lead_investigator, created_by, now, now),
            )
        except sqlite3.IntegrityError:
            return None
        _add_case_audit(db=db, case_id=int(cur.lastrowid), action="case.created", actor=created_by, detail={"case_no": case_no, "case_type": case_type, "lead_investigator": lead_investigator})
    return get_case(case_id=int(cur.lastrowid))


def get_case(*, case_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute(f"{_case_query()} WHERE c.id=? GROUP BY c.id", (case_id,)).fetchone()
    return dict(row) if row else None


def list_cases(*, keyword: str = "", status: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if keyword:
        token = f"%{keyword}%"
        clauses.append("(c.case_no LIKE ? OR c.name LIKE ? OR c.handling_unit LIKE ?)")
        values.extend([token, token, token])
    if status:
        clauses.append("c.status=?")
        values.append(status)
    sql = _case_query()
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with get_db() as db:
        rows = db.execute(f"{sql} GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC", values).fetchall()
    return [dict(row) for row in rows]


def assign_case_to_device(*, case_id: int, device_id: str, assigned_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        previous = db.execute("SELECT id, status, acknowledged_at FROM case_device_assignment WHERE case_id=? AND device_id=?", (case_id, device_id)).fetchone()
        db.execute(
            """INSERT INTO case_device_assignment (case_id, device_id, status, assigned_by, assigned_at, updated_at)
               VALUES (?, ?, 'pending', ?, ?, ?)
               ON CONFLICT(case_id, device_id) DO UPDATE SET status='pending', assigned_by=excluded.assigned_by,
               assigned_at=excluded.assigned_at, acknowledged_at=NULL, updated_at=excluded.updated_at""",
            (case_id, device_id, assigned_by, now, now),
        )
        db.execute(
            "UPDATE case_info SET status=CASE WHEN status='created' THEN 'assigned' ELSE status END, updated_at=? WHERE id=?",
            (now, case_id),
        )
        _add_case_audit(db=db, case_id=case_id, action="assignment.dispatched", actor=assigned_by, detail={"device_id": device_id, "redispatched": previous is not None, "previous_status": previous["status"] if previous else None, "previous_acknowledged_at": previous["acknowledged_at"] if previous else None})
        row = db.execute(
            """SELECT a.*, d.name AS device_name, c.case_no, c.name AS case_name, c.case_type, c.handling_unit, c.status AS case_status
               FROM case_device_assignment a JOIN device d ON d.device_id=a.device_id
               JOIN case_info c ON c.id=a.case_id WHERE a.case_id=? AND a.device_id=?""",
            (case_id, device_id),
        ).fetchone()
    return dict(row) if row else None


def list_case_assignments(*, case_id: int | None = None, device_id: str | None = None) -> list[dict[str, Any]]:
    sql = """SELECT a.*, d.name AS device_name, c.case_no, c.name AS case_name, c.case_type, c.handling_unit, c.status AS case_status
             FROM case_device_assignment a JOIN device d ON d.device_id=a.device_id
             JOIN case_info c ON c.id=a.case_id"""
    where: list[str] = []
    values: list[Any] = []
    if case_id is not None:
        where.append("a.case_id=?")
        values.append(case_id)
    if device_id is not None:
        where.append("a.device_id=?")
        values.append(device_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with get_db() as db:
        rows = db.execute(f"{sql} ORDER BY a.updated_at DESC, a.id DESC", values).fetchall()
    return [dict(row) for row in rows]


def get_case_assignment(*, assignment_id: int) -> dict[str, Any] | None:
    rows = list_case_assignments()
    return next((row for row in rows if int(row["id"]) == assignment_id), None)


def update_case_assignment_status(*, assignment_id: int, status: str, actor: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        assignment = db.execute("SELECT case_id, status FROM case_device_assignment WHERE id=?", (assignment_id,)).fetchone()
        if not assignment:
            return None
        transitions = {"pending": {"received"}, "received": {"handling", "completed"}, "handling": {"completed"}, "completed": set()}
        if status not in transitions.get(str(assignment["status"]), set()):
            return None
        db.execute(
            "UPDATE case_device_assignment SET status=?, acknowledged_at=COALESCE(acknowledged_at, ?), updated_at=? WHERE id=?",
            (status, now, now, assignment_id),
        )
        if status == "handling":
            db.execute("UPDATE case_info SET status='handling', updated_at=? WHERE id=? AND status IN ('created', 'assigned')", (now, assignment["case_id"]))
        _add_case_audit(db=db, case_id=int(assignment["case_id"]), action="assignment.status", actor=actor, detail={"from_status": assignment["status"], "to_status": status, "assignment_id": assignment_id})
    return get_case_assignment(assignment_id=assignment_id)


def _add_case_audit(*, db: sqlite3.Connection, case_id: int, action: str, actor: str, session_id: int | None = None, detail: dict[str, Any] | None = None) -> None:
    created_at = _utc_now_iso()
    detail_json = json.dumps(detail or {}, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    previous = db.execute("SELECT event_hash FROM case_audit_log WHERE case_id=? AND event_hash<>'' ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
    previous_hash = str(previous["event_hash"]) if previous else ""
    payload = json.dumps({"case_id": case_id, "session_id": session_id, "action": action, "actor": actor, "detail_json": detail_json, "previous_hash": previous_hash, "created_at": created_at}, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    event_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    db.execute(
        "INSERT INTO case_audit_log (case_id, session_id, action, actor, detail_json, previous_hash, event_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (case_id, session_id, action, actor, detail_json, previous_hash, event_hash, created_at),
    )


def _session_query() -> str:
    return """SELECT s.*, c.case_no, c.name AS case_name, d.name AS device_name,
              COUNT(DISTINCT t.id) AS transcript_count, COUNT(DISTINCT m.id) AS media_count
              FROM case_session s JOIN case_info c ON c.id=s.case_id
              JOIN device d ON d.device_id=s.device_id
              LEFT JOIN case_transcript t ON t.session_id=s.id
              LEFT JOIN case_media_asset m ON m.session_id=s.id"""


def get_case_session(*, session_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute(f"{_session_query()} WHERE s.id=? GROUP BY s.id", (session_id,)).fetchone()
    return dict(row) if row else None


def list_case_sessions(*, case_id: int | None = None, device_id: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if case_id is not None:
        clauses.append("s.case_id=?")
        values.append(case_id)
    if device_id is not None:
        clauses.append("s.device_id=?")
        values.append(device_id)
    sql = _session_query()
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with get_db() as db:
        rows = db.execute(f"{sql} GROUP BY s.id ORDER BY COALESCE(s.started_at, s.created_at) DESC, s.id DESC", values).fetchall()
    return [dict(row) for row in rows]


def create_case_session(*, case_id: int, device_id: str, session_no: str, session_type: str, recording_mode: str, planned_start_at: str | None, planned_end_at: str | None, location: str, host_name: str, participant_summary: str, created_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        assignment = db.execute("SELECT status FROM case_device_assignment WHERE case_id=? AND device_id=?", (case_id, device_id)).fetchone()
        if not assignment or assignment["status"] not in {"received", "handling"}:
            return None
        try:
            cur = db.execute(
                     """INSERT INTO case_session (case_id, device_id, session_no, session_type, recording_mode, planned_start_at, planned_end_at, location, host_name, participant_summary, created_by, created_at, updated_at)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (case_id, device_id, session_no, session_type, recording_mode, planned_start_at, planned_end_at, location, host_name, participant_summary, created_by, now, now),
            )
        except sqlite3.IntegrityError:
            return None
        _add_case_audit(db=db, case_id=case_id, session_id=int(cur.lastrowid), action="session.created", actor=created_by, detail={"device_id": device_id, "session_no": session_no, "session_type": session_type, "recording_mode": recording_mode, "planned_start_at": planned_start_at, "planned_end_at": planned_end_at})
    return get_case_session(session_id=int(cur.lastrowid))


def update_case_session_status(*, session_id: int, status: str, actor: str, occurred_at: str | None = None) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        session = db.execute("SELECT case_id, status FROM case_session WHERE id=?", (session_id,)).fetchone()
        if not session:
            return None
        transitions = {"planned": {"active", "cancelled"}, "active": {"finalizing", "ended"}, "finalizing": {"ended"}, "ended": set(), "cancelled": set()}
        if status not in transitions.get(str(session["status"]), set()):
            return None
        fields = ["status=?", "updated_at=?"]
        values: list[Any] = [status, now]
        if status == "active" and session["status"] == "planned":
            fields.append("started_at=?")
            values.append(occurred_at or now)
        if status == "ended":
            fields.append("ended_at=?")
            values.append(occurred_at or now)
        values.append(session_id)
        db.execute(f"UPDATE case_session SET {', '.join(fields)} WHERE id=?", values)
        _add_case_audit(db=db, case_id=int(session["case_id"]), session_id=session_id, action="session.status", actor=actor, detail={"status": status})
    return get_case_session(session_id=session_id)


def _remote_hearing_task_query() -> str:
    return """SELECT t.*, c.case_no, c.name AS case_name,
              SUM(CASE WHEN p.status='running' THEN 1 ELSE 0 END) AS running_participants,
              SUM(CASE WHEN p.status='failed' THEN 1 ELSE 0 END) AS failed_participants
              FROM remote_hearing_task t JOIN case_info c ON c.id=t.case_id
              LEFT JOIN remote_hearing_participant p ON p.task_id=t.id"""


def get_remote_hearing_task(*, task_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute(f"{_remote_hearing_task_query()} WHERE t.id=? GROUP BY t.id", (task_id,)).fetchone()
        participants = db.execute("SELECT p.*, d.name AS device_name FROM remote_hearing_participant p JOIN device d ON d.device_id=p.device_id WHERE p.task_id=? ORDER BY p.role", (task_id,)).fetchall()
    if not row:
        return None
    result = dict(row)
    result["participants"] = []
    for participant in participants:
        item = dict(participant)
        try:
            item["detail"] = json.loads(item.pop("detail_json"))
        except (json.JSONDecodeError, TypeError):
            item["detail"] = {}
        result["participants"].append(item)
    return result


def list_remote_hearing_tasks(*, case_id: int | None = None, device_id: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if case_id is not None:
        clauses.append("t.case_id=?")
        values.append(case_id)
    if device_id is not None:
        clauses.append("EXISTS (SELECT 1 FROM remote_hearing_participant device_participant WHERE device_participant.task_id=t.id AND device_participant.device_id=?)")
        values.append(device_id)
    sql = _remote_hearing_task_query()
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with get_db() as db:
        rows = db.execute(f"{sql} GROUP BY t.id ORDER BY COALESCE(t.scheduled_start_at, t.created_at) DESC, t.id DESC", values).fetchall()
    return [dict(row) for row in rows]


def create_remote_hearing_task(*, case_id: int, task_no: str, title: str, questioning_device_id: str, subject_device_id: str, scheduled_start_at: str | None, scheduled_end_at: str | None, stream_prefix: str, created_by: str) -> dict[str, Any] | None:
    if questioning_device_id == subject_device_id:
        return None
    now = _utc_now_iso()
    with get_db() as db:
        valid_devices = db.execute("SELECT device_id FROM device WHERE enabled=1 AND device_id IN (?, ?)", (questioning_device_id, subject_device_id)).fetchall()
        if len(valid_devices) != 2 or not db.execute("SELECT 1 FROM case_info WHERE id=?", (case_id,)).fetchone():
            return None
        try:
            cur = db.execute("INSERT INTO remote_hearing_task (case_id, task_no, title, scheduled_start_at, scheduled_end_at, stream_prefix, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (case_id, task_no, title, scheduled_start_at, scheduled_end_at, stream_prefix, created_by, now, now))
            task_id = int(cur.lastrowid)
            db.executemany("INSERT INTO remote_hearing_participant (task_id, device_id, role, updated_at) VALUES (?, ?, ?, ?)", [(task_id, questioning_device_id, "questioning", now), (task_id, subject_device_id, "subject", now)])
        except sqlite3.IntegrityError:
            return None
        _add_case_audit(db=db, case_id=case_id, session_id=None, action="remote_hearing.created", actor=created_by, detail={"task_id": task_id, "task_no": task_no, "questioning_device_id": questioning_device_id, "subject_device_id": subject_device_id})
    return get_remote_hearing_task(task_id=task_id)


def update_remote_hearing_participant(*, task_id: int, device_id: str, status: str, detail: dict[str, Any]) -> dict[str, Any] | None:
    if status not in {"ready", "running", "ended", "failed"}:
        return None
    now = _utc_now_iso()
    with get_db() as db:
        task = db.execute("SELECT case_id, status FROM remote_hearing_task WHERE id=?", (task_id,)).fetchone()
        participant = db.execute("SELECT status FROM remote_hearing_participant WHERE task_id=? AND device_id=?", (task_id, device_id)).fetchone()
        if not task or not participant or str(task["status"]) in {"ended", "cancelled"}:
            return None
        fields = ["status=?", "detail_json=?", "updated_at=?"]
        values: list[Any] = [status, json.dumps(detail, ensure_ascii=True, separators=(",", ":")), now]
        if status == "running":
            fields.append("started_at=COALESCE(started_at, ?)")
            values.append(now)
        if status in {"ended", "failed"}:
            fields.append("ended_at=?")
            values.append(now)
        values.extend([task_id, device_id])
        db.execute(f"UPDATE remote_hearing_participant SET {', '.join(fields)} WHERE task_id=? AND device_id=?", values)
        statuses = [str(row["status"]) for row in db.execute("SELECT status FROM remote_hearing_participant WHERE task_id=?", (task_id,)).fetchall()]
        task_status = "failed" if "failed" in statuses else "active" if statuses and all(value == "running" for value in statuses) else "ended" if statuses and all(value == "ended" for value in statuses) else str(task["status"])
        task_fields = ["status=?", "updated_at=?"]
        task_values: list[Any] = [task_status, now]
        if task_status == "active":
            task_fields.append("started_at=COALESCE(started_at, ?)")
            task_values.append(now)
        if task_status in {"ended", "failed"}:
            task_fields.append("ended_at=COALESCE(ended_at, ?)")
            task_values.append(now)
        task_values.append(task_id)
        db.execute(f"UPDATE remote_hearing_task SET {', '.join(task_fields)} WHERE id=?", task_values)
        _add_case_audit(db=db, case_id=int(task["case_id"]), session_id=None, action="remote_hearing.participant", actor=f"device:{device_id}", detail={"task_id": task_id, "status": status, "detail": detail})
    return get_remote_hearing_task(task_id=task_id)


def set_remote_hearing_task_state(*, task_id: int, state: str, actor: str) -> dict[str, Any] | None:
    if state not in {"starting", "stopping", "cancelled"}:
        return None
    now = _utc_now_iso()
    with get_db() as db:
        task = db.execute("SELECT case_id, status FROM remote_hearing_task WHERE id=?", (task_id,)).fetchone()
        if not task:
            return None
        current = str(task["status"])
        allowed = {"starting": {"planned"}, "stopping": {"starting", "active"}, "cancelled": {"planned", "starting"}}
        if current not in allowed[state]:
            return None
        if state == "starting":
            conflict = db.execute(
                """
                SELECT 1
                FROM remote_hearing_participant p
                JOIN remote_hearing_task t ON t.id=p.task_id
                WHERE p.device_id IN (SELECT device_id FROM remote_hearing_participant WHERE task_id=?)
                  AND t.id<>?
                  AND t.status IN ('starting', 'active', 'stopping')
                LIMIT 1
                """,
                (task_id, task_id),
            ).fetchone()
            if conflict:
                return None
        fields = ["status=?", "updated_at=?"]
        values: list[Any] = [state, now]
        if state == "cancelled":
            fields.append("ended_at=?")
            values.append(now)
        values.append(task_id)
        db.execute(f"UPDATE remote_hearing_task SET {', '.join(fields)} WHERE id=?", values)
        _add_case_audit(db=db, case_id=int(task["case_id"]), session_id=None, action=f"remote_hearing.{state}", actor=actor, detail={"task_id": task_id})
    return get_remote_hearing_task(task_id=task_id)


def _command_query() -> str:
    return """SELECT cmd.*, s.case_id, s.session_no, s.recording_mode, s.status AS session_status, d.name AS device_name
              FROM case_device_command cmd JOIN case_session s ON s.id=cmd.session_id
              JOIN device d ON d.device_id=cmd.device_id"""


def create_case_device_command(*, session_id: int, action: str, scheduled_at: str, idempotency_key: str, created_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        session = db.execute("SELECT case_id, device_id FROM case_session WHERE id=?", (session_id,)).fetchone()
        if not session:
            return None
        try:
            cur = db.execute("""INSERT INTO case_device_command (session_id, device_id, action, scheduled_at, idempotency_key, created_by, created_at, updated_at)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (session_id, session["device_id"], action, scheduled_at, idempotency_key, created_by, now, now))
        except sqlite3.IntegrityError:
            db.execute("""UPDATE case_device_command SET status='queued', scheduled_at=?, error_message='', started_at=NULL, completed_at=NULL, updated_at=?
                          WHERE idempotency_key=? AND status IN ('queued', 'failed')""", (scheduled_at, now, idempotency_key))
            row = db.execute(f"{_command_query()} WHERE cmd.idempotency_key=?", (idempotency_key,)).fetchone()
            return dict(row) if row else None
        _add_case_audit(db=db, case_id=int(session["case_id"]), session_id=session_id, action="command.queued", actor=created_by, detail={"command_id": int(cur.lastrowid), "command": action, "scheduled_at": scheduled_at})
        row = db.execute(f"{_command_query()} WHERE cmd.id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def list_case_device_commands(*, case_id: int | None = None, session_id: int | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if case_id is not None:
        clauses.append("s.case_id=?")
        values.append(case_id)
    if session_id is not None:
        clauses.append("cmd.session_id=?")
        values.append(session_id)
    sql = _command_query()
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with get_db() as db:
        rows = db.execute(f"{sql} ORDER BY cmd.id DESC", values).fetchall()
    return [dict(row) for row in rows]


def claim_due_case_device_commands(*, limit: int = 10) -> list[dict[str, Any]]:
    now = _utc_now_iso()
    claimed: list[dict[str, Any]] = []
    with get_db() as db:
        rows = db.execute("SELECT id FROM case_device_command WHERE status='queued' AND scheduled_at<=? ORDER BY scheduled_at, id LIMIT ?", (now, limit)).fetchall()
        for row in rows:
            updated = db.execute("UPDATE case_device_command SET status='running', attempt_count=attempt_count+1, started_at=?, updated_at=? WHERE id=? AND status='queued'", (now, now, row["id"])).rowcount
            if updated:
                command = db.execute(f"{_command_query()} WHERE cmd.id=?", (row["id"],)).fetchone()
                if command:
                    claimed.append(dict(command))
    return claimed


def finish_case_device_command(*, command_id: int, status: str, request_data: dict[str, Any], response_data: dict[str, Any], error_message: str = "") -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        command = db.execute("SELECT cmd.session_id, s.case_id FROM case_device_command cmd JOIN case_session s ON s.id=cmd.session_id WHERE cmd.id=?", (command_id,)).fetchone()
        if not command:
            return None
        db.execute("UPDATE case_device_command SET status=?, request_json=?, response_json=?, error_message=?, completed_at=?, updated_at=? WHERE id=?", (status, json.dumps(request_data, ensure_ascii=True), json.dumps(response_data, ensure_ascii=True), error_message[:1000], now, now, command_id))
        _add_case_audit(db=db, case_id=int(command["case_id"]), session_id=int(command["session_id"]), action="command.succeeded" if status == "succeeded" else "command.failed", actor="system", detail={"command_id": command_id, "error": error_message[:500]})
    return next((item for item in list_case_device_commands(session_id=int(command["session_id"])) if int(item["id"]) == command_id), None)


def get_case_disc_evidence(*, session_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM case_disc_evidence WHERE session_id=?", (session_id,)).fetchone()
    return dict(row) if row else None


def upsert_case_disc_evidence(*, session_id: int, status: str, drive_name: str = "", primary_hash: str = "", verified_hash: str = "", check_percent: int = 0, detail: dict[str, Any] | None = None, verified: bool = False) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        db.execute("""INSERT INTO case_disc_evidence (session_id, status, drive_name, primary_hash, verified_hash, check_percent, detail_json, verified_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET status=excluded.status, drive_name=excluded.drive_name, primary_hash=excluded.primary_hash,
                    verified_hash=excluded.verified_hash, check_percent=excluded.check_percent, detail_json=excluded.detail_json,
                    verified_at=excluded.verified_at, updated_at=excluded.updated_at""", (session_id, status, drive_name, primary_hash, verified_hash, int(check_percent), json.dumps(detail or {}, ensure_ascii=True), now if verified else None, now, now))
        row = db.execute("SELECT * FROM case_disc_evidence WHERE session_id=?", (session_id,)).fetchone()
    return dict(row) if row else None


def complete_case_assignment_if_ready(*, session_id: int, actor: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        session = db.execute("SELECT case_id, device_id FROM case_session WHERE id=?", (session_id,)).fetchone()
        if not session:
            return None
        open_count = int(db.execute("SELECT COUNT(*) FROM case_session WHERE case_id=? AND device_id=? AND status NOT IN ('ended', 'cancelled')", (session["case_id"], session["device_id"])).fetchone()[0])
        assignment = db.execute("SELECT id, status FROM case_device_assignment WHERE case_id=? AND device_id=?", (session["case_id"], session["device_id"])).fetchone()
        if open_count or not assignment or assignment["status"] == "completed":
            return None
        db.execute("UPDATE case_device_assignment SET status='completed', acknowledged_at=COALESCE(acknowledged_at, ?), updated_at=? WHERE id=?", (now, now, assignment["id"]))
        _add_case_audit(db=db, case_id=int(session["case_id"]), action="assignment.completed", actor=actor, detail={"assignment_id": int(assignment["id"]), "device_id": session["device_id"]})
    return get_case_assignment(assignment_id=int(assignment["id"]))


def _transcript_query() -> str:
    return """SELECT t.*, s.case_id, s.session_no, s.device_id, c.case_no, c.name AS case_name,
              v.archive_id AS current_archive_id, f.original_name AS current_file_name, f.sha256 AS current_file_hash
              FROM case_transcript t JOIN case_session s ON s.id=t.session_id
              JOIN case_info c ON c.id=s.case_id
              LEFT JOIN case_transcript_version v ON v.transcript_id=t.id AND v.version_no=t.current_version
              LEFT JOIN device_archive_file f ON f.id=v.archive_id"""


def get_case_transcript(*, transcript_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute(f"{_transcript_query()} WHERE t.id=?", (transcript_id,)).fetchone()
    return dict(row) if row else None


def list_case_transcripts(*, case_id: int | None = None, session_id: int | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if case_id is not None:
        clauses.append("s.case_id=?")
        values.append(case_id)
    if session_id is not None:
        clauses.append("t.session_id=?")
        values.append(session_id)
    sql = _transcript_query()
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with get_db() as db:
        rows = db.execute(f"{sql} ORDER BY t.updated_at DESC, t.id DESC", values).fetchall()
    return [dict(row) for row in rows]


def create_case_transcript(*, session_id: int, title: str, transcript_type: str, template_key: str, editor_type: str = "tiptap", created_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        session = db.execute("SELECT s.case_id FROM case_session s JOIN case_info c ON c.id=s.case_id WHERE s.id=? AND c.status NOT IN ('closed', 'archived')", (session_id,)).fetchone()
        if not session:
            return None
        cur = db.execute(
            """INSERT INTO case_transcript (session_id, title, transcript_type, template_key, editor_type, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, title, transcript_type, template_key, editor_type, created_by, now, now),
        )
        _add_case_audit(db=db, case_id=int(session["case_id"]), session_id=session_id, action="transcript.created", actor=created_by, detail={"transcript_id": int(cur.lastrowid), "transcript_type": transcript_type, "template_key": template_key, "editor_type": editor_type})
    return get_case_transcript(transcript_id=int(cur.lastrowid))


def save_case_transcript_draft(*, transcript_id: int, content_json: str, actor: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        transcript = db.execute("SELECT t.status FROM case_transcript t JOIN case_session s ON s.id=t.session_id JOIN case_info c ON c.id=s.case_id WHERE t.id=? AND c.status NOT IN ('closed', 'archived')", (transcript_id,)).fetchone()
        if not transcript or transcript["status"] == "finalized":
            return None
        db.execute("UPDATE case_transcript SET draft_content_json=?, last_saved_by=?, last_saved_at=?, updated_at=? WHERE id=?", (content_json, actor, now, now, transcript_id))
    return get_case_transcript(transcript_id=transcript_id)


def get_case_transcript_template(*, template_key: str) -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM case_transcript_template WHERE template_key=?", (template_key,)).fetchone()
    return dict(row) if row else None


def list_case_transcript_templates() -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM case_transcript_template ORDER BY name COLLATE NOCASE, id").fetchall()
    return [dict(row) for row in rows]


def upsert_case_transcript_template(*, template_key: str, name: str, transcript_type: str, content_json: str, actor: str) -> dict[str, Any]:
    now = _utc_now_iso()
    with get_db() as db:
        existing = db.execute("SELECT id FROM case_transcript_template WHERE template_key=?", (template_key,)).fetchone()
        if existing:
            db.execute(
                "UPDATE case_transcript_template SET name=?, transcript_type=?, content_json=?, updated_at=? WHERE template_key=?",
                (name, transcript_type, content_json, now, template_key),
            )
        else:
            db.execute(
                """INSERT INTO case_transcript_template (template_key, name, transcript_type, content_json, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (template_key, name, transcript_type, content_json, actor, now, now),
            )
    return get_case_transcript_template(template_key=template_key) or {}


def add_case_transcript_version(*, transcript_id: int, archive_id: int, content_hash: str, note: str, created_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        transcript = db.execute("SELECT t.status, t.current_version, t.session_id, s.case_id, s.device_id FROM case_transcript t JOIN case_session s ON s.id=t.session_id JOIN case_info c ON c.id=s.case_id WHERE t.id=? AND c.status NOT IN ('closed', 'archived')", (transcript_id,)).fetchone()
        archive = db.execute("SELECT id, device_id, session_id, archive_type, sha256 FROM device_archive_file WHERE id=?", (archive_id,)).fetchone()
        if not transcript or not archive or transcript["status"] == "finalized" or archive["archive_type"] != "transcript" or archive["sha256"] != content_hash or archive["device_id"] != transcript["device_id"] or archive["session_id"] != transcript["session_id"]:
            return None
        version_no = int(transcript["current_version"]) + 1
        db.execute(
            """INSERT INTO case_transcript_version (transcript_id, version_no, archive_id, content_hash, note, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (transcript_id, version_no, archive_id, content_hash, note, created_by, now),
        )
        db.execute("UPDATE case_transcript SET current_version=?, updated_at=? WHERE id=?", (version_no, now, transcript_id))
        _add_case_audit(db=db, case_id=int(transcript["case_id"]), session_id=int(transcript["session_id"]), action="transcript.version_added", actor=created_by, detail={"transcript_id": transcript_id, "version_no": version_no, "archive_id": archive_id, "content_hash": content_hash})
    return get_case_transcript(transcript_id=transcript_id)


def finalize_case_transcript(*, transcript_id: int, actor: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        transcript = db.execute("SELECT t.status, t.current_version, t.session_id, s.case_id FROM case_transcript t JOIN case_session s ON s.id=t.session_id JOIN case_info c ON c.id=s.case_id WHERE t.id=? AND c.status NOT IN ('closed', 'archived')", (transcript_id,)).fetchone()
        if not transcript or transcript["status"] == "finalized" or int(transcript["current_version"]) < 1:
            return None
        db.execute("UPDATE case_transcript SET status='finalized', finalized_by=?, finalized_at=?, updated_at=? WHERE id=?", (actor, now, now, transcript_id))
        _add_case_audit(db=db, case_id=int(transcript["case_id"]), session_id=int(transcript["session_id"]), action="transcript.finalized", actor=actor, detail={"transcript_id": transcript_id, "version_no": int(transcript["current_version"])})
    return get_case_transcript(transcript_id=transcript_id)


def create_case_media_asset(*, session_id: int, archive_id: int | None, media_type: str, source_stream: str, started_at: str | None, ended_at: str | None, sha256: str, created_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        session = db.execute("SELECT s.case_id, s.device_id FROM case_session s JOIN case_info c ON c.id=s.case_id WHERE s.id=? AND c.status NOT IN ('closed', 'archived')", (session_id,)).fetchone()
        archive = db.execute("SELECT device_id, session_id, archive_type, sha256 FROM device_archive_file WHERE id=?", (archive_id,)).fetchone() if archive_id is not None else None
        if not session or archive_id is None or not archive or archive["device_id"] != session["device_id"] or archive["session_id"] != session_id or archive["archive_type"] != media_type or archive["sha256"] != sha256:
            return None
        cur = db.execute(
            """INSERT INTO case_media_asset (case_id, session_id, archive_id, media_type, source_stream, started_at, ended_at, sha256, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session["case_id"], session_id, archive_id, media_type, source_stream, started_at, ended_at, sha256, created_by, now),
        )
        _add_case_audit(db=db, case_id=int(session["case_id"]), session_id=session_id, action="media.registered", actor=created_by, detail={"media_id": int(cur.lastrowid), "media_type": media_type, "archive_id": archive_id, "sha256": sha256})
        row = db.execute("SELECT * FROM case_media_asset WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def list_case_media_assets(*, case_id: int | None = None, session_id: int | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if case_id is not None:
        clauses.append("m.case_id=?")
        values.append(case_id)
    if session_id is not None:
        clauses.append("m.session_id=?")
        values.append(session_id)
    sql = """SELECT m.*, s.session_no, s.device_id, f.original_name, f.file_size
             FROM case_media_asset m JOIN case_session s ON s.id=m.session_id
             LEFT JOIN device_archive_file f ON f.id=m.archive_id"""
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with get_db() as db:
        rows = db.execute(f"{sql} ORDER BY COALESCE(m.started_at, m.created_at) DESC, m.id DESC", values).fetchall()
    return [dict(row) for row in rows]


def create_case_recording_binding(*, session_id: int, app: str, stream: str, recording_path: str, started_at: str, ended_at: str, sha256: str, integrity_status: str, created_by: str) -> dict[str, Any] | None:
    now = _utc_now_iso()
    with get_db() as db:
        session = db.execute("SELECT s.case_id, s.device_id FROM case_session s JOIN case_info c ON c.id=s.case_id WHERE s.id=? AND c.status NOT IN ('closed', 'archived')", (session_id,)).fetchone()
        if not session:
            return None
        try:
            cur = db.execute(
                """INSERT INTO case_recording_binding (case_id, session_id, device_id, app, stream, recording_path, started_at, ended_at, sha256, integrity_status, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session["case_id"], session_id, session["device_id"], app, stream, recording_path, started_at, ended_at, sha256, integrity_status, created_by, now),
            )
        except sqlite3.IntegrityError:
            return None
        _add_case_audit(db=db, case_id=int(session["case_id"]), session_id=session_id, action="recording.bound", actor=created_by, detail={"recording_id": int(cur.lastrowid), "recording_path": recording_path, "app": app, "stream": stream, "sha256": sha256, "integrity_status": integrity_status})
        row = db.execute("SELECT * FROM case_recording_binding WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def list_case_recording_bindings(*, keyword: str = "", case_id: int | None = None, app: str | None = None, stream: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if keyword:
        token = f"%{keyword}%"
        clauses.append("(c.case_no LIKE ? OR c.name LIKE ? OR c.handling_unit LIKE ?)")
        values.extend([token, token, token])
    if case_id is not None:
        clauses.append("r.case_id=?")
        values.append(case_id)
    if app:
        clauses.append("r.app=?")
        values.append(app)
    if stream:
        clauses.append("r.stream=?")
        values.append(stream)
    sql = """SELECT r.*, c.case_no, c.name AS case_name, s.session_no, s.session_type
             FROM case_recording_binding r JOIN case_info c ON c.id=r.case_id
             JOIN case_session s ON s.id=r.session_id"""
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with get_db() as db:
        rows = db.execute(f"{sql} ORDER BY r.started_at DESC, r.id DESC", values).fetchall()
    return [dict(row) for row in rows]


def list_case_audit_logs(*, case_id: int) -> list[dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT a.*, s.session_no FROM case_audit_log a LEFT JOIN case_session s ON s.id=a.session_id WHERE a.case_id=? ORDER BY a.id DESC", (case_id,)).fetchall()
    return [dict(row) for row in rows]


def verify_case_audit_chain(*, case_id: int) -> bool:
    with get_db() as db:
        rows = db.execute("SELECT case_id, session_id, action, actor, detail_json, previous_hash, event_hash, created_at FROM case_audit_log WHERE case_id=? ORDER BY id", (case_id,)).fetchall()
    previous_hash = ""
    for row in rows:
        if not row["event_hash"]:
            return False
        if row["previous_hash"] != previous_hash:
            return False
        payload = json.dumps({"case_id": row["case_id"], "session_id": row["session_id"], "action": row["action"], "actor": row["actor"], "detail_json": row["detail_json"], "previous_hash": row["previous_hash"], "created_at": row["created_at"]}, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["event_hash"]:
            return False
        previous_hash = str(row["event_hash"])
    return True


def get_case_completion_report(*, case_id: int) -> dict[str, Any] | None:
    with get_db() as db:
        case = db.execute("SELECT status FROM case_info WHERE id=?", (case_id,)).fetchone()
        if not case:
            return None
        assignment_count = int(db.execute("SELECT COUNT(*) FROM case_device_assignment WHERE case_id=?", (case_id,)).fetchone()[0])
        incomplete_assignments = [dict(row) for row in db.execute("SELECT device_id, status FROM case_device_assignment WHERE case_id=? AND status!='completed'", (case_id,)).fetchall()]
        open_sessions = [dict(row) for row in db.execute("SELECT id, session_no, status FROM case_session WHERE case_id=? AND status NOT IN ('ended', 'cancelled')", (case_id,)).fetchall()]
        draft_transcripts = [dict(row) for row in db.execute("""SELECT t.id, t.title, s.session_no FROM case_transcript t JOIN case_session s ON s.id=t.session_id
                                                               WHERE s.case_id=? AND t.status!='finalized'""", (case_id,)).fetchall()]
        unbound_media = [dict(row) for row in db.execute("SELECT id, media_type FROM case_media_asset WHERE case_id=? AND archive_id IS NULL", (case_id,)).fetchall()]
        missing_video_evidence = [dict(row) for row in db.execute("""SELECT s.id, s.session_no FROM case_session s
                                                                      WHERE s.case_id=? AND s.status='ended' AND NOT EXISTS (
                                                                          SELECT 1 FROM case_media_asset m WHERE m.session_id=s.id AND m.media_type='video' AND m.archive_id IS NOT NULL
                                                                      )""", (case_id,)).fetchall()]
        unverified_discs = [dict(row) for row in db.execute("""SELECT s.id, s.session_no FROM case_session s LEFT JOIN case_disc_evidence e ON e.session_id=s.id
                                                              WHERE s.case_id=? AND s.recording_mode='sync_burn' AND s.status='ended' AND COALESCE(e.status, '')!='verified'""", (case_id,)).fetchall()]
    checks = {
        "has_device_assignment": assignment_count > 0,
        "all_devices_completed": not incomplete_assignments,
        "all_sessions_closed": not open_sessions,
        "all_transcripts_finalized": not draft_transcripts,
        "all_media_bound": not unbound_media,
        "all_sessions_have_video_evidence": not missing_video_evidence,
        "all_sync_burn_discs_verified": not unverified_discs,
        "audit_chain_valid": verify_case_audit_chain(case_id=case_id),
    }
    return {"ready": all(checks.values()), "checks": checks, "incomplete_assignments": incomplete_assignments, "open_sessions": open_sessions, "draft_transcripts": draft_transcripts, "unbound_media": unbound_media, "missing_video_evidence": missing_video_evidence, "unverified_discs": unverified_discs, "status": case["status"]}


def close_case(*, case_id: int, actor: str) -> dict[str, Any] | None:
    report = get_case_completion_report(case_id=case_id)
    if not report or not report["ready"] or report["status"] in {"closed", "archived"}:
        return None
    now = _utc_now_iso()
    with get_db() as db:
        db.execute("UPDATE case_info SET status='closed', updated_at=? WHERE id=?", (now, case_id))
        _add_case_audit(db=db, case_id=case_id, action="case.closed", actor=actor, detail={"completion_checks": report["checks"]})
    return get_case(case_id=case_id)


def archive_is_immutable(*, archive_id: int) -> bool:
    with get_db() as db:
        row = db.execute("""SELECT 1 FROM case_transcript_version WHERE archive_id=?
                          UNION ALL SELECT 1 FROM case_media_asset WHERE archive_id=? LIMIT 1""", (archive_id, archive_id)).fetchone()
    return row is not None


def log_case_archive_event(*, archive_id: int, action: str, actor: str) -> None:
    with get_db() as db:
        archive = db.execute("SELECT case_id, session_id, archive_type, original_name, sha256 FROM device_archive_file WHERE id=?", (archive_id,)).fetchone()
        if not archive or archive["case_id"] is None:
            return
        _add_case_audit(db=db, case_id=int(archive["case_id"]), session_id=int(archive["session_id"]) if archive["session_id"] is not None else None, action=action, actor=actor, detail={"archive_id": archive_id, "archive_type": archive["archive_type"], "original_name": archive["original_name"], "sha256": archive["sha256"]})


def save_video_wall(*, owner_username: str, name: str, layout_size: int, cells: list[dict[str, Any]], polling_seconds: int, enabled: bool) -> dict[str, Any]:
    now = _utc_now_iso()
    with get_db() as db:
        db.execute(
            """INSERT INTO video_wall_config (owner_username, name, layout_size, cells_json, polling_seconds, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(owner_username, name) DO UPDATE SET layout_size=excluded.layout_size, cells_json=excluded.cells_json,
               polling_seconds=excluded.polling_seconds, enabled=excluded.enabled, updated_at=excluded.updated_at""",
            (owner_username, name, layout_size, json.dumps(cells, ensure_ascii=True), polling_seconds, int(enabled), now, now),
        )
        row = db.execute("SELECT * FROM video_wall_config WHERE owner_username=? AND name=?", (owner_username, name)).fetchone()
    return _serialize_wall(row)


def get_video_wall(*, owner_username: str, name: str = "default") -> dict[str, Any] | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM video_wall_config WHERE owner_username=? AND name=?", (owner_username, name)).fetchone()
    return _serialize_wall(row)


def _serialize_wall(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if not row:
        return None
    result = dict(row)
    result["cells"] = json.loads(result.pop("cells_json"))
    return result
