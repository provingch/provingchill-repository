from __future__ import annotations

import atexit
import json
import logging
import os
import re
import sqlite3
import sys
import unicodedata
import requests
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from getpass import getpass
from ipaddress import ip_address
from pathlib import Path
from threading import Lock
from typing import Callable
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import (
    Flask,
    abort,
    flash,
    has_request_context,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import socketio as socketio_lib
except ModuleNotFoundError:
    socketio_lib = None

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

BASE_DIR = Path(__file__).resolve().parent
PAGES_DIR = BASE_DIR / "uploaded_pages"
MEDIA_DIR = BASE_DIR / "media"
AVATARS_DIR = MEDIA_DIR / "avatars"
ANALYTICS_DIR = BASE_DIR / "analytics"
DATA_DIR = BASE_DIR / "data"
VISITS_LOG_FILE = ANALYTICS_DIR / "visits.jsonl"
MONITOR_LOG_FILE = ANALYTICS_DIR / "monitor_events.jsonl"
AUTH_DB_FILE = DATA_DIR / "auth.db"
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "nigahahhaghaghahahghagha")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ROLE_OWNER = "owner"
ROLE_USER = "user"
OWNER_USERNAMES = {"provingggg"}
RESERVED_USERNAMES = {"arisitam"}
CHAT_ROOM_NAME = "chat:authenticated"
CHAT_HISTORY_LIMIT = 80
CHAT_MESSAGE_MAX_LENGTH = 420
RATING_MIN = 1
RATING_MAX = 5
RATINGS_PAGE_PATH = "/valoraciones"
LEGACY_RATINGS_PAGE_PATH = "/chat"
PROJECT_LIKE_LIMIT = 1
MAX_AVATAR_BYTES = 4 * 1024 * 1024
ALLOWED_AVATAR_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
APP_TIMEZONE_NAME = os.getenv("APP_TIMEZONE", os.getenv("TZ", "America/Asuncion"))
LEGACY_SERVER_TIME_OFFSET = timedelta(hours=5, minutes=3)
TIME_OFFSET_MIGRATION_KEY = "server_time_offset_5h_3m_v1"
TIME_OFFSET_REMOVAL_MIGRATION_KEY = "server_time_offset_5h_3m_removed_v1"
PUBLIC_IP_HEADERS = (
    "CF-Connecting-IP",
    "True-Client-IP",
    "X-Forwarded-For",
    "X-Real-IP",
)
CONSOLA_BACKEND_URL = os.getenv("CONSOLA_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
SOURCE_ALIASES = {
    "ig": "instagram",
    "insta": "instagram",
    "instagram": "instagram",
    "fb": "facebook",
    "facebook": "facebook",
    "messenger": "messenger",
    "telegram": "telegram",
    "tg": "telegram",
    "threads": "threads",
    "wa": "whatsapp",
    "wsp": "whatsapp",
    "whatsapp": "whatsapp",
    "discordapp": "discord",
    "dc": "discord",
    "discord": "discord",
    "twitter": "x",
    "x": "x",
    "reddit": "reddit",
    "linkedin": "linkedin",
    "tiktok": "tiktok",
    "youtube": "youtube",
    "slack": "slack",
}
SOURCE_DISPLAY_LABELS = {
    "direct": "Directo",
    "link": "Link",
    "instagram": "Instagram",
    "discord": "Discord",
    "whatsapp": "WhatsApp",
    "facebook": "Facebook",
    "messenger": "Messenger",
    "telegram": "Telegram",
    "threads": "Threads",
    "x": "X",
    "reddit": "Reddit",
    "linkedin": "LinkedIn",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "slack": "Slack",
}
EXPLICIT_SOURCE_QUERY_KEYS = (
    "utm_source",
    "source",
    "via",
    "platform",
    "ref_source",
)
SOURCE_DOMAIN_MATCHERS = (
    ("instagram", ("instagram.com",)),
    ("discord", ("discord.com", "discord.gg", "discordapp.com")),
    ("whatsapp", ("whatsapp.com", "wa.me")),
    ("messenger", ("messenger.com", "m.me")),
    ("facebook", ("facebook.com", "fb.com")),
    ("telegram", ("telegram.me", "t.me", "telegram.org")),
    ("threads", ("threads.net",)),
    ("x", ("x.com", "twitter.com", "t.co")),
    ("reddit", ("reddit.com", "redd.it")),
    ("linkedin", ("linkedin.com", "lnkd.in")),
    ("tiktok", ("tiktok.com",)),
    ("youtube", ("youtube.com", "youtu.be")),
    ("slack", ("slack.com", "slack-redir.net")),
)
SOURCE_TEXT_SIGNATURES = (
    ("instagram", ("instagram", "com.instagram.android")),
    ("discord", ("discord", "discordbot", "com.discord")),
    ("whatsapp", ("whatsapp", "com.whatsapp")),
    ("messenger", ("messenger", "com.facebook.orca")),
    ("facebook", ("facebook", "fban", "fbav", "com.facebook.katana")),
    ("telegram", ("telegram", "telegrambot", "org.telegram.messenger")),
    ("threads", ("threads",)),
    ("x", ("twitter", "com.twitter.android")),
    ("reddit", ("reddit", "com.reddit.frontpage")),
    ("linkedin", ("linkedin",)),
    ("tiktok", ("tiktok", "musical_ly", "ugc.trill")),
    ("youtube", ("youtube", "com.google.android.youtube")),
    ("slack", ("slack",)),
)
MONTH_LABELS_ES = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)
PROJECT_CATEGORY_MUSICAL = "musical"
PROJECT_CATEGORY_INTERACTIVE = "interactive"
PROJECT_CATEGORY_DIRECTORY_NAMES = {
    PROJECT_CATEGORY_MUSICAL: "paginas-musicales",
    PROJECT_CATEGORY_INTERACTIVE: "paginas-interactivas",
}
PROJECT_CATEGORY_DIRECTORY_ALIASES = {
    "paginas-musicales": PROJECT_CATEGORY_MUSICAL,
    "musicales": PROJECT_CATEGORY_MUSICAL,
    "musical": PROJECT_CATEGORY_MUSICAL,
    "musica": PROJECT_CATEGORY_MUSICAL,
    "music": PROJECT_CATEGORY_MUSICAL,
    "paginas-interactivas": PROJECT_CATEGORY_INTERACTIVE,
    "interactivas": PROJECT_CATEGORY_INTERACTIVE,
    "interactiva": PROJECT_CATEGORY_INTERACTIVE,
    "interactivos": PROJECT_CATEGORY_INTERACTIVE,
    "interactive": PROJECT_CATEGORY_INTERACTIVE,
}
PROJECT_CHANGELOG_JSON_FILENAMES = ("changelog.json", "CHANGELOG.json")
PROJECT_CHANGELOG_TEXT_FILENAMES = ("CHANGELOG.md", "changelog.md", "CHANGELOG.txt", "changelog.txt")
PROJECT_VERSION_FILENAMES = ("version.txt", "VERSION", "VERSION.txt")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

try:
    APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)
except ZoneInfoNotFoundError:
    APP_TIMEZONE = timezone.utc

def read_bool_env(name: str, *, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


SESSION_COOKIE_SECURE = read_bool_env("SESSION_COOKIE_SECURE", default=False)
SESSION_USER_ID_KEY = "auth_user_id"
USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,38}[a-z0-9])?$")
FAVICON_PRIORITY = (
    "favicon.png",
    "favicon.webp",
    "favicon.jpg",
    "favicon.jpeg",
    "favicon.ico",
    "favicon.svg",
)
SERVER_INSTANCE_ID = uuid4().hex[:12]
SERVER_STARTED_AT = datetime.now(timezone.utc).isoformat()

app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY
app.config["SESSION_COOKIE_SECURE"] = SESSION_COOKIE_SECURE
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["TEMPLATES_AUTO_RELOAD"] = os.getenv("TEMPLATES_AUTO_RELOAD", "1") == "1"
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = app.config["TEMPLATES_AUTO_RELOAD"]
app.logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

if socketio_lib is not None:
    socket_server = socketio_lib.Server(
        async_mode="threading",
        cors_allowed_origins=os.getenv("SOCKET_IO_CORS", "*"),
        allow_upgrades=False,
    )
    app.wsgi_app = socketio_lib.WSGIApp(
        socket_server,
        app.wsgi_app,
        socketio_path="socket.io",
    )
else:
    socket_server = None

VISITS_LOCK = Lock()
VISITS_TOTAL = 0
VISITS_BY_SOURCE: Counter[str] = Counter()
VISITS_BY_REFERRER: Counter[str] = Counter()
VISITS_BY_PAGE: Counter[str] = Counter()
VISIT_EVENTS: list[dict[str, str]] = []
FAVICON_COLOR_CACHE: dict[str, str | None] = {}
SOCKET_CLIENTS: dict[str, dict[str, object]] = {}


def ensure_storage() -> None:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    for directory_name in PROJECT_CATEGORY_DIRECTORY_NAMES.values():
        (PAGES_DIR / directory_name).mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VISITS_LOG_FILE.touch(exist_ok=True)
    MONITOR_LOG_FILE.touch(exist_ok=True)
    ensure_auth_storage()


def add_column_if_missing(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    existing_columns = {
        str(column[1]).strip().lower()
        for column in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name.lower() in existing_columns:
        return

    try:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def shift_iso_string(iso_datetime: str | None, delta: timedelta) -> str | None:
    if not iso_datetime:
        return iso_datetime

    try:
        parsed = datetime.fromisoformat(iso_datetime)
    except ValueError:
        return iso_datetime

    if parsed.tzinfo is None:
        return iso_datetime

    return (parsed + delta).isoformat()


def apply_time_offset_migration(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    migration_row = connection.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (TIME_OFFSET_MIGRATION_KEY,),
    ).fetchone()
    if migration_row is not None:
        return

    user_rows = connection.execute(
        "SELECT id, created_at, updated_at, last_login_at FROM users"
    ).fetchall()
    for row in user_rows:
        row_id = int(row[0])
        connection.execute(
            """
            UPDATE users
            SET created_at = ?, updated_at = ?, last_login_at = ?
            WHERE id = ?
            """,
            (
                shift_iso_string(row[1], LEGACY_SERVER_TIME_OFFSET),
                shift_iso_string(row[2], LEGACY_SERVER_TIME_OFFSET),
                shift_iso_string(row[3], LEGACY_SERVER_TIME_OFFSET),
                row_id,
            ),
        )

    chat_rows = connection.execute(
        "SELECT id, created_at FROM chat_messages"
    ).fetchall()
    for row in chat_rows:
        row_id = int(row[0])
        connection.execute(
            "UPDATE chat_messages SET created_at = ? WHERE id = ?",
            (shift_iso_string(row[1], LEGACY_SERVER_TIME_OFFSET), row_id),
        )

    connection.execute(
        """
        INSERT INTO app_metadata (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (TIME_OFFSET_MIGRATION_KEY, utc_now_iso()),
    )


def remove_time_offset_migration(connection: sqlite3.Connection) -> None:
    migration_row = connection.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (TIME_OFFSET_REMOVAL_MIGRATION_KEY,),
    ).fetchone()
    if migration_row is not None:
        return

    previous_migration = connection.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (TIME_OFFSET_MIGRATION_KEY,),
    ).fetchone()
    if previous_migration is None:
        connection.execute(
            """
            INSERT INTO app_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (TIME_OFFSET_REMOVAL_MIGRATION_KEY, utc_now_iso()),
        )
        return

    for row in connection.execute(
        "SELECT id, created_at, updated_at, last_login_at FROM users"
    ).fetchall():
        row_id = int(row[0])
        connection.execute(
            """
            UPDATE users
            SET created_at = ?, updated_at = ?, last_login_at = ?
            WHERE id = ?
            """,
            (
                shift_iso_string(row[1], -LEGACY_SERVER_TIME_OFFSET),
                shift_iso_string(row[2], -LEGACY_SERVER_TIME_OFFSET),
                shift_iso_string(row[3], -LEGACY_SERVER_TIME_OFFSET),
                row_id,
            ),
        )

    for row in connection.execute(
        "SELECT id, created_at FROM chat_messages"
    ).fetchall():
        row_id = int(row[0])
        connection.execute(
            "UPDATE chat_messages SET created_at = ? WHERE id = ?",
            (shift_iso_string(row[1], -LEGACY_SERVER_TIME_OFFSET), row_id),
        )

    connection.execute(
        """
        INSERT INTO app_metadata (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (TIME_OFFSET_REMOVAL_MIGRATION_KEY, utc_now_iso()),
    )


def ensure_auth_storage() -> None:
    with sqlite3.connect(AUTH_DB_FILE) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )
        add_column_if_missing(
            connection,
            "users",
            "role",
            f"role TEXT NOT NULL DEFAULT '{ROLE_USER}'",
        )
        add_column_if_missing(connection, "users", "avatar_filename", "avatar_filename TEXT")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                avatar_filename TEXT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        add_column_if_missing(
            connection,
            "chat_messages",
            "avatar_filename",
            "avatar_filename TEXT",
        )
        add_column_if_missing(
            connection,
            "chat_messages",
            "rating",
            f"rating INTEGER NOT NULL DEFAULT {RATING_MAX}",
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_likes (
                project_slug TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_slug, user_id)
            )
            """
        )
        apply_time_offset_migration(connection)
        remove_time_offset_migration(connection)

        for username in RESERVED_USERNAMES:
            connection.execute("DELETE FROM users WHERE username = ?", (username,))

        owner_count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = ?",
            (ROLE_OWNER,),
        ).fetchone()[0]
        if owner_count == 0:
            for owner_username in OWNER_USERNAMES:
                owner_row = connection.execute(
                    "SELECT id FROM users WHERE username = ?",
                    (owner_username,),
                ).fetchone()
                if owner_row is not None:
                    connection.execute(
                        "UPDATE users SET role = ? WHERE id = ?",
                        (ROLE_OWNER, owner_row["id"] if isinstance(owner_row, sqlite3.Row) else owner_row[0]),
                    )
                    break

        connection.execute(
            "UPDATE users SET role = ? WHERE role IS NULL OR TRIM(role) = ''",
            (ROLE_USER,),
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def app_now_iso() -> str:
    return datetime.now(APP_TIMEZONE).isoformat()


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(AUTH_DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def normalize_username(raw_username: str) -> str:
    username = (raw_username or "").strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "El usuario debe tener entre 3 y 40 caracteres y usar solo letras, numeros, "
            "punto, guion o guion bajo."
        )
    return username


def validate_password(raw_password: str) -> str:
    if len(raw_password) < 8:
        raise ValueError("La contrasena debe tener al menos 8 caracteres.")
    if len(raw_password) > 200:
        raise ValueError("La contrasena es demasiado larga.")
    return raw_password


def build_avatar_url(avatar_filename: str | None) -> str | None:
    if not avatar_filename:
        return None
    avatar_path = f"avatars/{avatar_filename}"
    if has_request_context():
        return url_for("serve_media", filename=avatar_path)

    application_root = str(app.config.get("APPLICATION_ROOT") or "").rstrip("/")
    if application_root:
        return f"{application_root}/media/{avatar_path}"
    return f"/media/{avatar_path}"


def fetch_user_by_username(username: str) -> sqlite3.Row | None:
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                avatar_filename,
                is_active,
                created_at,
                updated_at,
                last_login_at
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()


def fetch_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                avatar_filename,
                is_active,
                created_at,
                updated_at,
                last_login_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()


def serialize_user(row: sqlite3.Row) -> dict:
    avatar_filename = row["avatar_filename"]
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "role": str(row["role"] or ROLE_USER),
        "avatar_filename": str(avatar_filename) if avatar_filename else None,
        "avatar_url": build_avatar_url(str(avatar_filename)) if avatar_filename else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_login_at": row["last_login_at"],
    }


def clear_auth_session() -> None:
    session.pop(SESSION_USER_ID_KEY, None)


def get_current_user() -> dict | None:
    raw_user_id = session.get(SESSION_USER_ID_KEY)
    if raw_user_id is None:
        return None

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        clear_auth_session()
        return None

    row = fetch_user_by_id(user_id)
    if row is None or not bool(row["is_active"]):
        clear_auth_session()
        return None

    return serialize_user(row)


def touch_last_login(user_id: int) -> None:
    with get_db_connection() as connection:
        connection.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (app_now_iso(), user_id),
        )


def normalize_public_ip(raw_value: str | None) -> str | None:
    if not raw_value:
        return None

    candidate = raw_value.strip().strip('"').strip("'")
    if not candidate:
        return None

    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.split(":", 1)[0]

    try:
        parsed = ip_address(candidate)
    except ValueError:
        return None

    if not parsed.is_global:
        return None
    return parsed.compressed


def extract_client_ip() -> str:
    for header_name in PUBLIC_IP_HEADERS:
        header_value = request.headers.get(header_name, "")
        if not header_value:
            continue

        for raw_candidate in header_value.split(","):
            public_ip = normalize_public_ip(raw_candidate)
            if public_ip:
                return public_ip

    remote_public_ip = normalize_public_ip(request.remote_addr)
    if remote_public_ip:
        return remote_public_ip

    return "public-unavailable"


def is_owner_user(user: dict | None) -> bool:
    if not user:
        return False
    return str(user.get("role") or ROLE_USER).lower() == ROLE_OWNER


def owner_exists(
    connection: sqlite3.Connection,
    *,
    exclude_user_id: int | None = None,
) -> bool:
    query = "SELECT 1 FROM users WHERE role = ?"
    params: list[object] = [ROLE_OWNER]
    if exclude_user_id is not None:
        query += " AND id != ?"
        params.append(int(exclude_user_id))
    query += " LIMIT 1"
    row = connection.execute(query, tuple(params)).fetchone()
    return row is not None


def resolve_role_for_new_account(connection: sqlite3.Connection, username: str) -> str:
    if username in OWNER_USERNAMES and not owner_exists(connection):
        return ROLE_OWNER
    return ROLE_USER


def validate_available_username(
    connection: sqlite3.Connection,
    raw_username: str,
    *,
    current_user_id: int | None = None,
    current_role: str = ROLE_USER,
) -> str:
    normalized_username = normalize_username(raw_username)
    if normalized_username in RESERVED_USERNAMES:
        raise ValueError("Ese usuario no esta disponible.")
    if (
        normalized_username in OWNER_USERNAMES
        and current_role != ROLE_OWNER
        and owner_exists(connection, exclude_user_id=current_user_id)
    ):
        raise ValueError("Ese usuario esta reservado.")

    existing_user = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        (normalized_username,),
    ).fetchone()
    if existing_user is not None:
        existing_id = int(existing_user["id"]) if isinstance(existing_user, sqlite3.Row) else int(existing_user[0])
        if current_user_id is None or existing_id != int(current_user_id):
            raise ValueError("Ese usuario ya existe.")

    return normalized_username


def delete_avatar_file(avatar_filename: str | None) -> None:
    if not avatar_filename:
        return
    avatar_path = AVATARS_DIR / avatar_filename
    try:
        avatar_path.unlink(missing_ok=True)
    except OSError:
        app.logger.exception("Could not delete avatar file %s", avatar_path)


def save_avatar_upload(user_id: int, uploaded_file) -> str:
    original_filename = str(getattr(uploaded_file, "filename", "") or "").strip()
    if not original_filename:
        raise ValueError("Selecciona una imagen para tu perfil.")

    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_AVATAR_SUFFIXES:
        allowed_labels = ", ".join(sorted(ALLOWED_AVATAR_SUFFIXES))
        raise ValueError(f"Formato no permitido. Usa: {allowed_labels}.")

    mimetype = str(getattr(uploaded_file, "mimetype", "") or "").lower()
    if mimetype and not mimetype.startswith("image/"):
        raise ValueError("El archivo debe ser una imagen valida.")

    raw_bytes = uploaded_file.read(MAX_AVATAR_BYTES + 1)
    if not raw_bytes:
        raise ValueError("La imagen esta vacia.")
    if len(raw_bytes) > MAX_AVATAR_BYTES:
        raise ValueError("La foto supera el limite de 4 MB.")

    avatar_filename = f"user-{user_id}-{uuid4().hex}{suffix}"
    avatar_path = AVATARS_DIR / avatar_filename
    avatar_path.write_bytes(raw_bytes)
    return avatar_filename


def create_user(username: str, password: str) -> sqlite3.Row:
    clean_password = validate_password(password)
    password_hash = generate_password_hash(clean_password)
    timestamp = utc_now_iso()

    with get_db_connection() as connection:
        normalized_username = validate_available_username(connection, username)
        role = resolve_role_for_new_account(connection, normalized_username)

        cursor = connection.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                role,
                avatar_filename,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, NULL, 1, ?, ?)
            """,
            (normalized_username, password_hash, role, timestamp, timestamp),
        )
        user_row = connection.execute(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                avatar_filename,
                is_active,
                created_at,
                updated_at,
                last_login_at
            FROM users
            WHERE id = ?
            """,
            (int(cursor.lastrowid),),
        ).fetchone()

    if user_row is None:
        raise RuntimeError("No pude recuperar el usuario recien creado.")
    return user_row


def set_user_password(username: str, password: str) -> str:
    normalized_username = normalize_username(username)
    clean_password = validate_password(password)
    password_hash = generate_password_hash(clean_password)
    timestamp = utc_now_iso()

    with get_db_connection() as connection:
        existing_user = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if existing_user is None:
            raise ValueError("Ese usuario no existe.")

        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, is_active = 1, updated_at = ?
            WHERE id = ?
            """,
            (
                password_hash,
                timestamp,
                existing_user["id"],
            ),
        )

    return normalized_username


def update_user_profile(
    user_id: int,
    *,
    username: str,
    password: str = "",
    password_confirmation: str = "",
    uploaded_avatar=None,
    remove_avatar: bool = False,
) -> sqlite3.Row:
    timestamp = utc_now_iso()

    with get_db_connection() as connection:
        current_row = connection.execute(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                avatar_filename,
                is_active,
                created_at,
                updated_at,
                last_login_at
            FROM users
            WHERE id = ?
            """,
            (int(user_id),),
        ).fetchone()

        if current_row is None:
            raise ValueError("La sesion ya no es valida.")

        current_role = str(current_row["role"] or ROLE_USER)
        normalized_username = validate_available_username(
            connection,
            username,
            current_user_id=int(user_id),
            current_role=current_role,
        )

        updates: dict[str, object] = {
            "username": normalized_username,
            "updated_at": timestamp,
        }

        if password or password_confirmation:
            if password != password_confirmation:
                raise ValueError("Las contrasenas nuevas no coinciden.")
            updates["password_hash"] = generate_password_hash(validate_password(password))

        current_avatar_filename = (
            str(current_row["avatar_filename"]) if current_row["avatar_filename"] else None
        )
        next_avatar_filename = current_avatar_filename
        uploaded_avatar_filename: str | None = None
        has_new_avatar = bool(
            uploaded_avatar is not None and str(getattr(uploaded_avatar, "filename", "") or "").strip()
        )

        if has_new_avatar:
            uploaded_avatar_filename = save_avatar_upload(int(user_id), uploaded_avatar)
            next_avatar_filename = uploaded_avatar_filename
        elif remove_avatar:
            next_avatar_filename = None

        updates["avatar_filename"] = next_avatar_filename

        set_clause = ", ".join(f"{column} = ?" for column in updates)
        values = list(updates.values()) + [int(user_id)]

        try:
            connection.execute(
                f"UPDATE users SET {set_clause} WHERE id = ?",
                values,
            )
            connection.execute(
                """
                UPDATE chat_messages
                SET username = ?, role = ?, avatar_filename = ?
                WHERE user_id = ?
                """,
                (
                    normalized_username,
                    current_role,
                    next_avatar_filename,
                    int(user_id),
                ),
            )
        except Exception:
            if uploaded_avatar_filename is not None:
                delete_avatar_file(uploaded_avatar_filename)
            raise

        refreshed_row = connection.execute(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                avatar_filename,
                is_active,
                created_at,
                updated_at,
                last_login_at
            FROM users
            WHERE id = ?
            """,
            (int(user_id),),
        ).fetchone()

    if refreshed_row is None:
        raise RuntimeError("No pude recuperar el perfil actualizado.")

    if current_avatar_filename != next_avatar_filename:
        delete_avatar_file(current_avatar_filename)

    return refreshed_row


def list_users() -> list[sqlite3.Row]:
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, username, role, is_active, created_at, updated_at, last_login_at
            FROM users
            ORDER BY username ASC
            """
        ).fetchall()
    return list(rows)


def delete_user(username: str) -> bool:
    normalized_username = normalize_username(username)
    with get_db_connection() as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if user_row is None:
            return False

        user_id = int(user_row["id"]) if isinstance(user_row, sqlite3.Row) else int(user_row[0])
        connection.execute("DELETE FROM project_likes WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
        cursor = connection.execute(
            "DELETE FROM users WHERE username = ?",
            (normalized_username,),
        )
    return cursor.rowcount > 0


def prompt_password(*, confirm: bool = True) -> str:
    password = getpass("Contrasena: ")
    if confirm:
        confirmation = getpass("Repite la contrasena: ")
        if password != confirmation:
            raise ValueError("Las contrasenas no coinciden.")
    return validate_password(password)


def normalize_chat_message(raw_message: str) -> str:
    message = re.sub(r"\s+", " ", (raw_message or "").strip())
    if not message:
        raise ValueError("Escribe un comentario antes de enviarlo.")
    if len(message) > CHAT_MESSAGE_MAX_LENGTH:
        raise ValueError(
            f"El comentario no puede superar los {CHAT_MESSAGE_MAX_LENGTH} caracteres."
        )
    return message


def normalize_rating(raw_rating: object) -> int:
    try:
        rating = int(raw_rating)
    except (TypeError, ValueError):
        raise ValueError("Selecciona una valoracion de 1 a 5 estrellas.") from None

    if rating < RATING_MIN or rating > RATING_MAX:
        raise ValueError("Selecciona una valoracion de 1 a 5 estrellas.")
    return rating


def serialize_chat_message(row: sqlite3.Row) -> dict:
    avatar_filename = row["avatar_filename"]
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "username": str(row["username"]),
        "role": str(row["role"] or ROLE_USER),
        "avatar_url": build_avatar_url(str(avatar_filename)) if avatar_filename else None,
        "message": str(row["message"]),
        "rating": normalize_rating(row["rating"] if row["rating"] is not None else RATING_MAX),
        "created_at": row["created_at"],
    }


def load_chat_messages(*, limit: int = CHAT_HISTORY_LIMIT) -> list[dict]:
    safe_limit = max(1, min(int(limit), CHAT_HISTORY_LIMIT))
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, username, role, avatar_filename, message, rating, created_at
            FROM chat_messages
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [serialize_chat_message(row) for row in rows]


def get_rating_summary() -> dict:
    with get_db_connection() as connection:
        aggregate_row = connection.execute(
            """
            SELECT COUNT(*) AS total_ratings, AVG(rating) AS average_rating
            FROM chat_messages
            """
        ).fetchone()
        distribution_rows = connection.execute(
            """
            SELECT rating, COUNT(*) AS total
            FROM chat_messages
            GROUP BY rating
            ORDER BY rating DESC
            """
        ).fetchall()

    total_ratings = int(aggregate_row["total_ratings"] or 0) if aggregate_row else 0
    average_rating = float(aggregate_row["average_rating"] or 0) if aggregate_row else 0.0
    by_star = {rating: 0 for rating in range(RATING_MAX, RATING_MIN - 1, -1)}

    for row in distribution_rows:
        by_star[int(row["rating"])] = int(row["total"])

    return {
        "total_ratings": total_ratings,
        "average_rating": round(average_rating, 1) if total_ratings else 0,
        "by_star": [
            {"rating": rating, "count": by_star[rating]}
            for rating in range(RATING_MAX, RATING_MIN - 1, -1)
        ],
    }


def create_chat_message(user: dict, raw_message: str, raw_rating: object) -> dict:
    message = normalize_chat_message(raw_message)
    rating = normalize_rating(raw_rating)
    timestamp = utc_now_iso()

    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO chat_messages (
                user_id,
                username,
                role,
                avatar_filename,
                message,
                rating,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user["id"]),
                str(user["username"]),
                str(user.get("role") or ROLE_USER),
                user.get("avatar_filename"),
                message,
                rating,
                timestamp,
            ),
        )
        row = connection.execute(
            """
            SELECT id, user_id, username, role, avatar_filename, message, rating, created_at
            FROM chat_messages
            WHERE id = ?
            """,
            (int(cursor.lastrowid),),
        ).fetchone()

    if row is None:
        raise RuntimeError("No pude recuperar la valoracion recien creada.")
    return serialize_chat_message(row)


def print_usage() -> None:
    print("Uso:")
    print("  python app.py")
    print("  python app.py create-user <usuario>")
    print("  python app.py set-password <usuario>")
    print("  python app.py list-users")
    print("  python app.py delete-user <usuario>")


def run_cli(argv: list[str]) -> int:
    if len(argv) < 2:
        print_usage()
        return 1

    command = argv[1].strip().lower()

    try:
        if command == "create-user":
            if len(argv) < 3:
                print("Falta el usuario.")
                print_usage()
                return 1

            created_user = create_user(argv[2], prompt_password())
            print(
                f"Usuario '{created_user['username']}' creado con rol "
                f"'{created_user['role']}' en {AUTH_DB_FILE}."
            )
            return 0

        if command == "set-password":
            if len(argv) < 3:
                print("Falta el usuario.")
                print_usage()
                return 1

            normalized_username = set_user_password(argv[2], prompt_password())
            print(f"Contrasena actualizada para '{normalized_username}'.")
            return 0

        if command == "list-users":
            rows = list_users()
            if not rows:
                print("No hay usuarios cargados todavia.")
                return 0

            for row in rows:
                last_login_at = row["last_login_at"] or "-"
                print(
                    f"{row['username']} | rol={row['role']} | activo={int(row['is_active'])} | "
                    f"creado={row['created_at']} | ultimo_login={last_login_at}"
                )
            return 0

        if command == "delete-user":
            if len(argv) < 3:
                print("Falta el usuario.")
                print_usage()
                return 1

            if delete_user(argv[2]):
                print(f"Usuario '{normalize_username(argv[2])}' eliminado.")
                return 0

            print("Ese usuario no existe.")
            return 1
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Comando desconocido: {command}")
    print_usage()
    return 1


def normalize_source(value: str | None) -> str:
    if value is None:
        return "direct"

    cleaned = re.sub(r"[^a-z0-9_-]+", "", value.strip().lower())
    if not cleaned:
        return "direct"
    return SOURCE_ALIASES.get(cleaned, cleaned)


def extract_explicit_source() -> str:
    for query_key in EXPLICIT_SOURCE_QUERY_KEYS:
        raw_value = str(request.args.get(query_key, "") or "").strip()
        if raw_value:
            return normalize_source(raw_value)
    return ""


def extract_referrer_domain(referrer: str) -> str:
    if not referrer:
        return ""

    try:
        parsed = urlparse(referrer)
    except ValueError:
        return ""

    if not parsed.hostname:
        return ""
    return parsed.hostname.lower()


def normalize_domain_label(value: str | None) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned.startswith("www."):
        return cleaned[4:]
    return cleaned


def is_internal_referrer(current_host: str, referrer_domain: str) -> bool:
    normalized_host = normalize_domain_label(current_host)
    normalized_referrer = normalize_domain_label(referrer_domain)
    if not normalized_host or not normalized_referrer:
        return False
    return (
        normalized_referrer == normalized_host
        or normalized_referrer.endswith(f".{normalized_host}")
    )


def infer_source_from_domain(referrer_domain: str) -> str | None:
    normalized_domain = normalize_domain_label(referrer_domain)
    if not normalized_domain:
        return None

    for source, domains in SOURCE_DOMAIN_MATCHERS:
        if any(
            normalized_domain == domain or normalized_domain.endswith(f".{domain}")
            for domain in domains
        ):
            return source

    return None


def infer_source_from_text(*values: str) -> str | None:
    haystack = " ".join(str(value or "").strip().lower() for value in values if value).strip()
    if not haystack:
        return None

    for source, signatures in SOURCE_TEXT_SIGNATURES:
        if any(signature in haystack for signature in signatures):
            return source

    return None


def normalize_fetch_site(value: str | None) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in {"cross-site", "same-origin", "same-site", "none"}:
        return cleaned
    return ""


def infer_source(
    *,
    current_host: str,
    explicit_source: str,
    referrer_domain: str,
    user_agent: str,
    requested_with: str,
    sec_fetch_site: str,
) -> str:
    # Internal navigation must win even inside in-app browsers, otherwise one
    # external open turns into multiple fake external visits while the user moves
    # around the same site.
    if is_internal_referrer(current_host, referrer_domain):
        return "internal"

    if explicit_source:
        return normalize_source(explicit_source)

    requested_with_source = infer_source_from_text(requested_with)
    if requested_with_source:
        return requested_with_source

    referrer_source = infer_source_from_domain(referrer_domain)
    if referrer_source:
        return referrer_source

    user_agent_source = infer_source_from_text(user_agent)
    if user_agent_source:
        return user_agent_source

    if normalize_fetch_site(sec_fetch_site) == "cross-site":
        return "link"

    if not referrer_domain:
        return "direct"

    return "link"


def canonicalize_page_path(page: str | None) -> str:
    cleaned = str(page or "").strip() or "/"
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"

    if cleaned.startswith("/pages/"):
        slug = cleaned[len("/pages/") :].strip("/")
        return f"/pages/{slug}/" if slug else "/pages/"

    cleaned = cleaned.rstrip("/") or "/"
    if cleaned == LEGACY_RATINGS_PAGE_PATH:
        return RATINGS_PAGE_PATH
    return cleaned


def get_page_label(page: str) -> str:
    normalized = canonicalize_page_path(page)
    if normalized == "/":
        return "Inicio"
    if normalized == RATINGS_PAGE_PATH:
        return "Valoraciones"
    if normalized == "/projects":
        return "Proyectos"
    if normalized.startswith("/pages/"):
        return humanize_slug(normalized[len("/pages/") :].strip("/"))
    return normalized.strip("/") or "Inicio"


def is_project_page_path(page: str | None) -> bool:
    normalized = canonicalize_page_path(page)
    return normalized.startswith("/pages/") and normalized != "/pages/"


def get_page_visit_count(page: str) -> int:
    with VISITS_LOCK:
        return int(VISITS_BY_PAGE[canonicalize_page_path(page)])


def parse_visit_timestamp(iso_datetime: str | None) -> datetime | None:
    if not iso_datetime:
        return None

    try:
        parsed = datetime.fromisoformat(iso_datetime)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_visit_day_label(local_datetime: datetime) -> str:
    month_label = MONTH_LABELS_ES[local_datetime.month - 1]
    return f"{local_datetime.day:02d} {month_label}"


def format_visit_date_label(local_date: date) -> str:
    month_label = MONTH_LABELS_ES[local_date.month - 1]
    return f"{local_date.day:02d} {month_label}"


def format_visit_origin_label(source: str, referrer_domain: str) -> str:
    normalized_source = normalize_source(source)
    if normalized_source not in {"direct", "link"}:
        return SOURCE_DISPLAY_LABELS.get(
            normalized_source,
            normalized_source.replace("_", " ").strip().title() or "Directo",
        )

    cleaned_domain = str(referrer_domain or "").strip().lower()
    if cleaned_domain:
        inferred_domain_source = infer_source_from_domain(cleaned_domain)
        if inferred_domain_source and inferred_domain_source not in {"direct", "link"}:
            return SOURCE_DISPLAY_LABELS.get(
                inferred_domain_source,
                inferred_domain_source.replace("_", " ").strip().title(),
            )
        return normalize_domain_label(cleaned_domain)

    return SOURCE_DISPLAY_LABELS.get(
        normalized_source,
        normalized_source.replace("_", " ").strip().title() or "Directo",
    )


def get_visit_window_dates(*, bucket_limit: int = 10) -> tuple[date, date]:
    safe_bucket_limit = max(2, int(bucket_limit))
    today = datetime.now(APP_TIMEZONE).date()
    start_date = today - timedelta(days=safe_bucket_limit - 1)
    return start_date, today


def build_visit_timeline(
    visit_events: list[dict[str, object]],
    *,
    label_resolver: Callable[[dict[str, object]], str],
    meta_resolver: Callable[[dict[str, object]], dict[str, object]] | None = None,
    bucket_limit: int = 10,
    series_limit: int = 4,
) -> dict:
    safe_bucket_limit = max(2, int(bucket_limit))
    window_start, window_end = get_visit_window_dates(bucket_limit=safe_bucket_limit)
    bucket_labels = {
        (window_start + timedelta(days=offset)).isoformat(): format_visit_date_label(
            window_start + timedelta(days=offset)
        )
        for offset in range(safe_bucket_limit)
    }
    totals_by_label: Counter[str] = Counter()
    counts_by_label_and_bucket: dict[str, Counter[str]] = {}
    metadata_by_label: dict[str, dict[str, object]] = {}

    for event in visit_events:
        parsed_at = parse_visit_timestamp(str(event.get("at") or ""))
        if parsed_at is None:
            continue

        local_date = parsed_at.astimezone(APP_TIMEZONE).date()
        if local_date < window_start or local_date > window_end:
            continue

        bucket_key = local_date.isoformat()
        label = label_resolver(event).strip()
        if not label:
            continue

        totals_by_label[label] += 1
        if label not in counts_by_label_and_bucket:
            counts_by_label_and_bucket[label] = Counter()
        counts_by_label_and_bucket[label][bucket_key] += 1
        if meta_resolver is not None and label not in metadata_by_label:
            metadata_by_label[label] = meta_resolver(event)

    ordered_bucket_keys = [
        (window_start + timedelta(days=offset)).isoformat()
        for offset in range(safe_bucket_limit)
    ]

    ranked_labels = [label for label, _total in totals_by_label.most_common(series_limit)]
    remaining_labels = [label for label in totals_by_label if label not in ranked_labels]
    series: list[dict[str, object]] = []

    for label in ranked_labels:
        bucket_counts = counts_by_label_and_bucket.get(label, Counter())
        values = [int(bucket_counts.get(bucket_key, 0)) for bucket_key in ordered_bucket_keys]
        if any(values):
            series_item: dict[str, object] = {
                "label": label,
                "values": values,
                "total": int(sum(values)),
            }
            if label in metadata_by_label:
                series_item.update(metadata_by_label[label])
            series.append(series_item)

    if remaining_labels:
        other_values = [
            sum(
                int(counts_by_label_and_bucket.get(label, Counter()).get(bucket_key, 0))
                for label in remaining_labels
            )
            for bucket_key in ordered_bucket_keys
        ]
        if any(other_values):
            series.append({"label": "Otros", "values": other_values, "total": int(sum(other_values))})

    return {
        "labels": [bucket_labels[bucket_key] for bucket_key in ordered_bucket_keys],
        "series": series,
    }


def build_visit_origin_timeline(
    visit_events: list[dict[str, object]],
    *,
    bucket_limit: int = 10,
    series_limit: int = 4,
) -> dict:
    return build_visit_timeline(
        visit_events,
        label_resolver=lambda event: format_visit_origin_label(
            str(event.get("source") or "direct"),
            str(event.get("referrer_domain") or ""),
        ),
        bucket_limit=bucket_limit,
        series_limit=series_limit,
    )


def load_visit_stats() -> None:
    global VISITS_TOTAL

    if not VISITS_LOG_FILE.is_file():
        return

    with VISITS_LOCK:
        VISITS_TOTAL = 0
        VISITS_BY_SOURCE.clear()
        VISITS_BY_REFERRER.clear()
        VISITS_BY_PAGE.clear()
        VISIT_EVENTS.clear()

        with VISITS_LOG_FILE.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                source = normalize_source(str(event.get("source") or "direct"))
                page = canonicalize_page_path(str(event.get("page") or "/"))
                referrer_domain = str(event.get("referrer_domain") or "").strip().lower()

                VISITS_TOTAL += 1
                VISITS_BY_SOURCE[source] += 1
                VISITS_BY_PAGE[page] += 1
                if referrer_domain:
                    VISITS_BY_REFERRER[referrer_domain] += 1
                VISIT_EVENTS.append(
                    {
                        "at": str(event.get("at") or ""),
                        "page": page,
                        "source": source,
                        "referrer_domain": referrer_domain,
                    }
                )


def get_visits_snapshot() -> dict:
    with VISITS_LOCK:
        visit_events = [event.copy() for event in VISIT_EVENTS]

    project_catalog = {
        str(page["url"]): {
            "label": str(page["title"]),
            "favicon_url": page.get("favicon_url"),
            "color": page.get("favicon_color"),
        }
        for page in discover_pages()
    }

    project_events = [
        {
            "at": str(event.get("at") or ""),
            "page": canonicalize_page_path(str(event.get("page") or "/")),
            "source": normalize_source(str(event.get("source") or "direct")),
            "referrer_domain": str(event.get("referrer_domain") or "").strip().lower(),
        }
        for event in visit_events
        if is_project_page_path(str(event.get("page") or "/"))
    ]

    window_start, window_end = get_visit_window_dates(bucket_limit=10)
    filtered_project_events: list[dict[str, object]] = []

    for event in project_events:
        parsed_at = parse_visit_timestamp(str(event.get("at") or ""))
        if parsed_at is None:
            continue

        local_date = parsed_at.astimezone(APP_TIMEZONE).date()
        if local_date < window_start or local_date > window_end:
            continue
        filtered_project_events.append(event)

    total_visits = len(filtered_project_events)
    by_source_counter: Counter[str] = Counter()
    by_page_counter: Counter[str] = Counter()
    by_referrer_counter: Counter[str] = Counter()

    for event in filtered_project_events:
        by_source_counter[str(event["source"])] += 1
        by_page_counter[str(event["page"])] += 1
        referrer_domain = str(event["referrer_domain"])
        if referrer_domain:
            by_referrer_counter[referrer_domain] += 1

    top_pages = [
        {"path": page, "label": get_page_label(page), "count": total}
        for page, total in by_page_counter.most_common(12)
    ]
    top_referrers = [
        {"domain": domain, "count": total}
        for domain, total in by_referrer_counter.most_common(10)
    ]

    return {
        "total": total_visits,
        "by_source": {source: total for source, total in by_source_counter.most_common()},
        "top_pages": top_pages,
        "top_referrers": top_referrers,
        "origin_timeline": build_visit_origin_timeline(filtered_project_events, bucket_limit=10),
        "page_timeline": build_visit_timeline(
            filtered_project_events,
            label_resolver=lambda event: str(
                project_catalog.get(str(event.get("page") or ""), {}).get(
                    "label",
                    get_page_label(str(event.get("page") or "")),
                )
            ),
            meta_resolver=lambda event: {
                "color": project_catalog.get(str(event.get("page") or ""), {}).get("color"),
                "favicon_url": project_catalog.get(str(event.get("page") or ""), {}).get("favicon_url"),
            },
            bucket_limit=10,
            series_limit=6,
        ),
        "top_project": top_pages[0] if top_pages else None,
    }


def emit_visits_snapshot(event_data: dict | None = None, *, sid: str | None = None) -> None:
    if socket_server is None:
        return

    payload: dict = {"stats": get_visits_snapshot()}
    if event_data:
        payload["event"] = event_data

    try:
        socket_server.emit("visits:update", payload, to=sid)
    except Exception:
        app.logger.exception("Could not emit visits:update through socket.io")


def get_socket_user(environ: dict) -> dict | None:
    try:
        with app.request_context(environ):
            return get_current_user()
    except Exception:
        app.logger.exception("Could not resolve socket session user.")
        return None


def emit_chat_snapshot(*, sid: str | None = None, environ: dict | None = None) -> None:
    if socket_server is None:
        return

    try:
        user = None
        if environ is not None:
            with app.request_context(environ):
                user = get_current_user()
                messages = load_chat_messages()
        else:
            messages = load_chat_messages()
        payload: dict[str, object] = {
            "messages": messages,
            "summary": get_rating_summary(),
        }
        socket_server.emit("chat:update", payload, to=sid)
    except Exception:
        app.logger.exception("Could not emit chat:update snapshot through socket.io")


def emit_chat_message(message: dict) -> None:
    if socket_server is None:
        return

    try:
        socket_server.emit(
            "chat:update",
            {"message": message, "summary": get_rating_summary()},
            to=CHAT_ROOM_NAME,
        )
    except Exception:
        app.logger.exception("Could not emit chat:update message through socket.io")


if socket_server is not None:

    @socket_server.event
    def connect(sid, environ, auth=None):  # type: ignore[no-untyped-def]
        app.logger.info("[socket] connected sid=%s", sid)
        emit_visits_snapshot(sid=sid)
        
        user = get_socket_user(environ)
        if user is not None:
            socket_server.enter_room(sid, CHAT_ROOM_NAME)
            emit_chat_snapshot(sid=sid, environ=environ)

    @socket_server.event
    def disconnect(sid):  # type: ignore[no-untyped-def]
        app.logger.info("[socket] disconnected sid=%s", sid)


def record_visit(page: str) -> None:
    global VISITS_TOTAL

    page = canonicalize_page_path(page)
    current_user = get_current_user()
    if is_owner_user(current_user):
        app.logger.info(
            "[visit] ignored owner page=%s user=%s",
            page,
            current_user["username"],
        )
        return

    explicit_source = extract_explicit_source()
    referrer = request.headers.get("Referer", "")
    user_agent = request.headers.get("User-Agent", "")
    requested_with = request.headers.get("X-Requested-With", "")
    sec_fetch_site = request.headers.get("Sec-Fetch-Site", "")
    request_host = request.host.split(":", 1)[0].lower() if request.host else ""
    referrer_domain = extract_referrer_domain(referrer)
    source = infer_source(
        current_host=request_host,
        explicit_source=explicit_source,
        referrer_domain=referrer_domain,
        user_agent=user_agent,
        requested_with=requested_with,
        sec_fetch_site=sec_fetch_site,
    )

    event = {
        "at": utc_now_iso(),
        "page": page,
        "source": source,
        "utm_source": explicit_source or None,
        "referrer_domain": referrer_domain or None,
        "user_agent": user_agent[:180],
    }

    try:
        with VISITS_LOCK:
            with VISITS_LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(f"{json.dumps(event, ensure_ascii=True)}\n")

            VISITS_TOTAL += 1
            VISITS_BY_SOURCE[source] += 1
            VISITS_BY_PAGE[page] += 1
            if referrer_domain:
                VISITS_BY_REFERRER[referrer_domain] += 1
            VISIT_EVENTS.append(
                {
                    "at": event["at"],
                    "page": page,
                    "source": source,
                    "referrer_domain": referrer_domain,
                }
            )

            total_visits = VISITS_TOTAL
            source_total = VISITS_BY_SOURCE[source]
    except OSError:
        app.logger.exception("Could not write visit analytics to %s", VISITS_LOG_FILE)
        return

    app.logger.info(
        "[visit] total=%s source=%s source_total=%s page=%s referrer=%s",
        total_visits,
        source,
        source_total,
        page,
        referrer_domain or "-",
    )
    emit_visits_snapshot(
        {
            "at": event["at"],
            "page": page,
            "source": source,
            "referrer_domain": referrer_domain or None,
        }
    )


def humanize_slug(slug: str) -> str:
    words = [part for part in slug.replace("_", "-").split("-") if part]
    if not words:
        return slug
    return " ".join(word.capitalize() for word in words)


def normalize_project_category_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def resolve_project_category_directory(folder_name: str) -> str | None:
    normalized_key = normalize_project_category_key(folder_name)
    if not normalized_key:
        return None
    return PROJECT_CATEGORY_DIRECTORY_ALIASES.get(normalized_key)


def infer_project_category(*, container_name: str | None = None) -> str:
    return resolve_project_category_directory(container_name or "") or PROJECT_CATEGORY_MUSICAL


def iter_project_directories() -> list[tuple[str, Path, os.stat_result]]:
    project_directories: list[tuple[str, Path, os.stat_result]] = []

    for entry in PAGES_DIR.iterdir():
        if not entry.is_dir():
            continue

        index_file = entry / "index.html"
        if index_file.is_file():
            project_directories.append(
                (PROJECT_CATEGORY_MUSICAL, entry, index_file.stat())
            )
            continue

        category = resolve_project_category_directory(entry.name)
        if not category:
            continue

        for nested_page_dir in entry.iterdir():
            if not nested_page_dir.is_dir():
                continue

            nested_index = nested_page_dir / "index.html"
            if not nested_index.is_file():
                continue

            project_directories.append((category, nested_page_dir, nested_index.stat()))

    return project_directories


def find_page_directory_by_slug(slug: str) -> Path | None:
    normalized_slug = str(slug or "").strip()
    if not normalized_slug:
        return None

    direct_page_dir = PAGES_DIR / normalized_slug
    if direct_page_dir.is_dir() and (direct_page_dir / "index.html").is_file():
        return direct_page_dir

    for _, page_dir, _ in iter_project_directories():
        if page_dir.name == normalized_slug:
            return page_dir

    return None


def build_project_page_path(slug: str) -> str:
    return canonicalize_page_path(f"/pages/{str(slug or '').strip()}/")


def build_project_public_url(slug: str) -> str:
    return build_project_page_path(str(slug or "").strip())


def build_project_changelog_url(slug: str) -> str:
    clean_slug = str(slug or "").strip()
    return f"/projects/{clean_slug}/changelog"


def get_project_slug_from_page_path(page: str | None) -> str | None:
    normalized_page = canonicalize_page_path(page)
    if not is_project_page_path(normalized_page):
        return None
    slug = normalized_page[len("/pages/") :].strip("/")
    return slug or None


def discover_project_changelog_file(page_dir: Path) -> Path | None:
    for filename in PROJECT_CHANGELOG_JSON_FILENAMES + PROJECT_CHANGELOG_TEXT_FILENAMES:
        candidate = page_dir / filename
        if candidate.is_file():
            return candidate
    return None


def read_project_version_file(page_dir: Path) -> str | None:
    for filename in PROJECT_VERSION_FILENAMES:
        candidate = page_dir / filename
        if not candidate.is_file():
            continue

        try:
            version_text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue

        if version_text:
            return version_text.splitlines()[0].strip()

    return None


def parse_project_changelog_entries(raw_entries: object) -> list[dict[str, object]]:
    if not isinstance(raw_entries, list):
        return []

    entries: list[dict[str, object]] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue

        version = str(item.get("version") or item.get("title") or "").strip()
        released_on = str(item.get("date") or item.get("released_at") or item.get("released_on") or "").strip()
        notes_source = item.get("notes", item.get("changes", item.get("items")))
        notes: list[str] = []

        if isinstance(notes_source, list):
            notes = [str(note).strip() for note in notes_source if str(note).strip()]
        elif isinstance(notes_source, str):
            notes = [line.strip("-* ").strip() for line in notes_source.splitlines() if line.strip()]

        summary = str(item.get("summary") or "").strip()
        if not version and not notes and not summary:
            continue

        entry: dict[str, object] = {
            "version": version or "Sin version",
            "date": released_on or None,
            "notes": notes,
        }
        if summary:
            entry["summary"] = summary
        entries.append(entry)

    return entries


def parse_project_changelog_text(raw_text: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    current_entry: dict[str, object] | None = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if re.match(r"^#{2,6}\s+", line):
            heading = re.sub(r"^#{2,6}\s+", "", line).strip()
            if heading.casefold() == "changelog":
                continue

            if current_entry is not None:
                entries.append(current_entry)

            current_entry = {
                "version": heading,
                "date": None,
                "notes": [],
            }
            continue

        if current_entry is None:
            continue

        if re.match(r"^[-*]\s+", line):
            note = re.sub(r"^[-*]\s+", "", line).strip()
            if note:
                notes = current_entry.setdefault("notes", [])
                if isinstance(notes, list):
                    notes.append(note)
            continue

        notes = current_entry.setdefault("notes", [])
        if isinstance(notes, list):
            notes.append(line)

    if current_entry is not None:
        entries.append(current_entry)

    return entries


def load_project_changelog(page_dir: Path) -> dict[str, object]:
    changelog_file = discover_project_changelog_file(page_dir)
    version = read_project_version_file(page_dir)

    if changelog_file is None:
        return {
            "available": False,
            "version": version,
            "entries": [],
            "format": None,
            "source_file": None,
        }

    try:
        raw_text = changelog_file.read_text(encoding="utf-8").strip()
    except OSError:
        raw_text = ""

    entries: list[dict[str, object]] = []
    changelog_format: str | None = None

    if changelog_file.suffix.lower() == ".json" and raw_text:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            entries = parse_project_changelog_entries(
                payload.get("entries", payload.get("versions", payload.get("changelog", [])))
            )
        elif isinstance(payload, list):
            entries = parse_project_changelog_entries(payload)

        changelog_format = "json"
    elif raw_text:
        entries = parse_project_changelog_text(raw_text)
        changelog_format = "text"

    if not version and entries:
        first_version = str(entries[0].get("version") or "").strip()
        version = first_version or None

    return {
        "available": bool(changelog_file),
        "version": version,
        "entries": entries,
        "format": changelog_format,
        "source_file": changelog_file.name,
        "raw_text": raw_text if changelog_format == "text" and not entries else "",
    }


def get_project_like_snapshot(*, viewer_user_id: int | None = None) -> tuple[dict[str, int], set[str]]:
    with get_db_connection() as connection:
        like_rows = connection.execute(
            """
            SELECT project_slug, COUNT(*) AS total
            FROM project_likes
            GROUP BY project_slug
            """
        ).fetchall()
        liked_rows = (
            connection.execute(
                "SELECT project_slug FROM project_likes WHERE user_id = ?",
                (int(viewer_user_id),),
            ).fetchall()
            if viewer_user_id is not None
            else []
        )

    counts = {str(row["project_slug"]): int(row["total"]) for row in like_rows}
    liked_slugs = {str(row["project_slug"]) for row in liked_rows}
    return counts, liked_slugs


def set_project_like(project_slug: str, user_id: int, *, liked: bool) -> dict[str, object]:
    normalized_slug = str(project_slug or "").strip()
    if not normalized_slug:
        raise ValueError("Proyecto no valido.")

    timestamp = utc_now_iso()
    with get_db_connection() as connection:
        if liked:
            connection.execute(
                """
                INSERT INTO project_likes (project_slug, user_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(project_slug, user_id) DO NOTHING
                """,
                (normalized_slug, int(user_id), timestamp),
            )
        else:
            connection.execute(
                "DELETE FROM project_likes WHERE project_slug = ? AND user_id = ?",
                (normalized_slug, int(user_id)),
            )

        aggregate_row = connection.execute(
            "SELECT COUNT(*) AS total FROM project_likes WHERE project_slug = ?",
            (normalized_slug,),
        ).fetchone()
        liked_row = connection.execute(
            "SELECT 1 FROM project_likes WHERE project_slug = ? AND user_id = ?",
            (normalized_slug, int(user_id)),
        ).fetchone()

    return {
        "project_slug": normalized_slug,
        "like_count": int(aggregate_row["total"] or 0) if aggregate_row else 0,
        "viewer_has_liked": liked_row is not None,
    }


def build_projects_overview(pages: list[dict]) -> dict[str, object]:
    project_views = sum(int(page.get("visit_count") or 0) for page in pages)
    total_likes = sum(int(page.get("like_count") or 0) for page in pages)
    featured_pages = sorted(
        pages,
        key=lambda page: (
            int(page.get("like_count") or 0),
            int(page.get("visit_count") or 0),
            str(page.get("updated_at") or ""),
        ),
        reverse=True,
    )
    return {
        "project_count": len(pages),
        "project_views": project_views,
        "total_likes": total_likes,
        "featured_pages": featured_pages[:3],
    }


def load_monitor_events(*, limit: int | None = None) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    if not MONITOR_LOG_FILE.is_file():
        return events

    try:
        with MONITOR_LOG_FILE.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue

                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = str(payload.get("timestamp") or "").strip()
                event_type = str(payload.get("type") or "unknown").strip() or "unknown"
                details = payload.get("details")
                if not isinstance(details, dict):
                    details = {"raw": details}

                events.append(
                    {
                        "timestamp": timestamp,
                        "type": event_type,
                        "details": details,
                    }
                )
    except OSError:
        app.logger.exception("Could not read monitor events from %s", MONITOR_LOG_FILE)
        return []

    events.sort(key=lambda event: str(event.get("timestamp") or ""))
    if limit is not None:
        safe_limit = max(1, int(limit))
        return events[-safe_limit:]
    return events


def discover_favicon_file(page_dir: Path) -> Path | None:
    media_dir = page_dir / "media"
    if not media_dir.is_dir():
        return None

    for filename in FAVICON_PRIORITY:
        candidate = media_dir / filename
        if candidate.is_file():
            return candidate

    media_files = [item for item in media_dir.iterdir() if item.is_file()]
    lower_name_map = {item.name.lower(): item for item in media_files}

    for filename in FAVICON_PRIORITY:
        candidate = lower_name_map.get(filename)
        if candidate:
            return candidate

    for item in sorted(media_files, key=lambda path: path.name.lower()):
        lower_name = item.name.lower()
        if "favicon" in lower_name:
            return item

    return None


def discover_favicon_url(page_dir: Path) -> str | None:
    favicon_file = discover_favicon_file(page_dir)
    if favicon_file is None:
        return None

    relative_path = favicon_file.relative_to(PAGES_DIR).as_posix()
    return f"/pages/{relative_path}"


def blend_color_channel(channel: int, *, target: int = 255, amount: float = 0.18) -> int:
    return int(round(channel * (1 - amount) + target * amount))


def discover_favicon_color(page_dir: Path) -> str | None:
    favicon_file = discover_favicon_file(page_dir)
    if favicon_file is None:
        return None

    cache_key = str(favicon_file.resolve())
    if cache_key in FAVICON_COLOR_CACHE:
        return FAVICON_COLOR_CACHE[cache_key]

    if Image is None:
        FAVICON_COLOR_CACHE[cache_key] = None
        return None

    try:
        with Image.open(favicon_file) as image:
            rgba_image = image.convert("RGBA")
            rgba_image.thumbnail((40, 40))
            weighted_pixels = [
                (red, green, blue, alpha)
                for red, green, blue, alpha in rgba_image.getdata()
                if alpha >= 24
            ]
    except Exception:
        FAVICON_COLOR_CACHE[cache_key] = None
        return None

    if not weighted_pixels:
        FAVICON_COLOR_CACHE[cache_key] = None
        return None

    total_weight = 0.0
    total_red = 0.0
    total_green = 0.0
    total_blue = 0.0

    for red, green, blue, alpha in weighted_pixels:
        weight = max(alpha / 255.0, 0.12)
        total_weight += weight
        total_red += red * weight
        total_green += green * weight
        total_blue += blue * weight

    if total_weight <= 0:
        FAVICON_COLOR_CACHE[cache_key] = None
        return None

    average_red = int(round(total_red / total_weight))
    average_green = int(round(total_green / total_weight))
    average_blue = int(round(total_blue / total_weight))

    if average_red + average_green + average_blue < 150:
        average_red = blend_color_channel(average_red)
        average_green = blend_color_channel(average_green)
        average_blue = blend_color_channel(average_blue)

    color = f"#{average_red:02x}{average_green:02x}{average_blue:02x}"
    FAVICON_COLOR_CACHE[cache_key] = color
    return color


def discover_pages() -> list[dict]:
    pages: list[dict] = []
    page_candidates: list[tuple[float, str, Path, os.stat_result]] = []
    current_user = get_current_user() if has_request_context() else None
    viewer_user_id = int(current_user["id"]) if current_user and current_user.get("id") is not None else None
    like_counts, viewer_likes = get_project_like_snapshot(viewer_user_id=viewer_user_id)

    for category, page_dir, stat in iter_project_directories():
        page_candidates.append((stat.st_mtime, category, page_dir, stat))

    for _, category, page_dir, stat in sorted(page_candidates, key=lambda item: item[0], reverse=True):
        slug = page_dir.name
        changelog = load_project_changelog(page_dir)
        pages.append(
            {
                "slug": slug,
                "title": humanize_slug(slug),
                "url": build_project_public_url(slug),
                "category": category,
                "storage_path": page_dir.relative_to(PAGES_DIR).as_posix(),
                "version": changelog.get("version"),
                "has_changelog": bool(changelog.get("available")),
                "changelog_url": build_project_changelog_url(slug),
                "favicon_url": discover_favicon_url(page_dir),
                "favicon_color": discover_favicon_color(page_dir),
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "visit_count": get_page_visit_count(build_project_page_path(slug)),
                "like_count": int(like_counts.get(slug, 0)),
                "viewer_has_liked": slug in viewer_likes,
            }
        )

    return pages


def resolve_post_redirect_target(default_endpoint: str, *, anchor: str | None = None) -> str:
    raw_next_path = str(request.form.get("next_path") or "").strip()
    if raw_next_path:
        parsed = urlparse(raw_next_path)
        if (
            not parsed.scheme
            and not parsed.netloc
            and parsed.path.startswith("/")
            and not parsed.path.startswith("//")
        ):
            return raw_next_path

    if anchor:
        return url_for(default_endpoint, _anchor=anchor)
    return url_for(default_endpoint)


@app.get("/")
def home():
    record_visit("/")
    auth_user = get_current_user()
    pages = discover_pages()
    overview = build_projects_overview(pages)
    return render_template(
        "index.html",
        auth_user=auth_user,
        app_timezone_name=APP_TIMEZONE_NAME,
        pages=pages,
        project_views=overview["project_views"],
        total_likes=overview["total_likes"],
        featured_pages=overview["featured_pages"],
    )


@app.get(RATINGS_PAGE_PATH)
def ratings_page():
    return redirect(url_for("projects_page"))


@app.get(LEGACY_RATINGS_PAGE_PATH)
def chat_page():
    return redirect(url_for("projects_page"))


@app.get("/projects")
def projects_page():
    record_visit("/projects")
    auth_user = get_current_user()
    return render_template(
        "projects.html",
        auth_user=auth_user,
        app_timezone_name=APP_TIMEZONE_NAME,
    )


@app.get("/projects/<path:page_slug>/changelog")
def project_changelog_page(page_slug: str):
    page_dir = find_page_directory_by_slug(page_slug)
    if page_dir is None:
        abort(404)

    record_visit(build_project_page_path(page_dir.name))
    auth_user = get_current_user()
    changelog = load_project_changelog(page_dir)
    page_data = {
        "slug": page_dir.name,
        "title": humanize_slug(page_dir.name),
        "url": build_project_public_url(page_dir.name),
        "version": changelog.get("version"),
        "changelog_url": build_project_changelog_url(page_dir.name),
        "favicon_url": discover_favicon_url(page_dir),
        "visit_count": get_page_visit_count(build_project_page_path(page_dir.name)),
    }
    return render_template(
        "project_changelog.html",
        auth_user=auth_user,
        app_timezone_name=APP_TIMEZONE_NAME,
        page=page_data,
        changelog=changelog,
    )


@app.get("/monitor")
def monitor_page():
    auth_user = get_current_user()
    return render_template(
        "monitor.html",
        auth_user=auth_user,
        app_timezone_name=APP_TIMEZONE_NAME,
        can_execute_monitor_commands=is_owner_user(auth_user),
    )


@app.post("/register")
def register():
    if get_current_user() is not None:
        flash("Ya tienes una sesion activa.", "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    username = request.form.get("register_username", "")
    password = request.form.get("register_password", "")
    password_confirmation = request.form.get("register_password_confirm", "")

    if not username or not password or not password_confirmation:
        flash("Completa usuario, contrasena y confirmacion para registrarte.", "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    if password != password_confirmation:
        flash("Las contrasenas no coinciden.", "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    try:
        user_row = create_user(username, password)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    session.permanent = True
    session[SESSION_USER_ID_KEY] = int(user_row["id"])
    touch_last_login(int(user_row["id"]))
    flash(
        f"Cuenta creada como {user_row['username']} con rol {user_row['role']}.",
        "success",
    )
    return redirect(resolve_post_redirect_target("projects_page"))


@app.post("/account/profile")
def update_account_profile_route():
    user = get_current_user()
    if user is None:
        flash("Inicia sesion para editar tu cuenta.", "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    username = request.form.get("profile_username", "")
    password = request.form.get("profile_password", "")
    password_confirmation = request.form.get("profile_password_confirm", "")
    uploaded_avatar = request.files.get("profile_avatar")
    remove_avatar = request.form.get("profile_avatar_remove") == "1"

    try:
        updated_user_row = update_user_profile(
            int(user["id"]),
            username=username,
            password=password,
            password_confirmation=password_confirmation,
            uploaded_avatar=uploaded_avatar,
            remove_avatar=remove_avatar,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    updated_user = serialize_user(updated_user_row)
    flash(
        f"Cuenta actualizada. Ahora entras como {updated_user['username']}.",
        "success",
    )
    return redirect(resolve_post_redirect_target("home", anchor="login"))


@app.post("/login")
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if not username or not password:
        flash("Completa usuario y contrasena para entrar.", "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    try:
        normalized_username = normalize_username(username)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    user_row = fetch_user_by_username(normalized_username)
    if user_row is None or not bool(user_row["is_active"]):
        clear_auth_session()
        flash("Usuario no encontrado o inactivo. Crea una cuenta nueva para registrarte.", "info")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    if not check_password_hash(user_row["password_hash"], password):
        clear_auth_session()
        flash("Contraseña incorrecta.", "error")
        return redirect(resolve_post_redirect_target("home", anchor="login"))

    session.permanent = True
    session[SESSION_USER_ID_KEY] = int(user_row["id"])
    touch_last_login(int(user_row["id"]))
    flash(
        f"Sesion iniciada como {user_row['username']} con rol {user_row['role']}.",
        "success",
    )
    return redirect(resolve_post_redirect_target("projects_page"))


@app.post("/logout")
def logout():
    clear_auth_session()
    flash("Sesion cerrada.", "success")
    return redirect(resolve_post_redirect_target("home", anchor="login"))


@app.after_request
def disable_html_cache(response):
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/media/<path:filename>")
def serve_media(filename: str):
    return send_from_directory(MEDIA_DIR, filename)


@app.get("/api/pages")
def list_pages():
    return jsonify({"pages": discover_pages()})


@app.get("/api/visits")
def project_visits():
    return jsonify(get_visits_snapshot())


@app.route("/api/consola/<path:endpoint>", methods=["GET", "POST"])
def consola_backend_proxy(endpoint: str):
    if endpoint not in {"commands", "status", "execute"}:
        return jsonify({"error": "Endpoint de consola no permitido."}), 404

    target_url = f"{CONSOLA_BACKEND_URL}/{endpoint}"
    try:
        if request.method == "POST":
            backend_response = requests.post(
                target_url,
                json=request.get_json(silent=True) or {},
                timeout=5,
            )
        else:
            backend_response = requests.get(target_url, timeout=5)
    except requests.RequestException as exc:
        return jsonify({
            "error": "Backend de consola no disponible.",
            "detail": str(exc),
            "backend": CONSOLA_BACKEND_URL,
        }), 502

    try:
        payload = backend_response.json()
    except ValueError:
        payload = {"error": backend_response.text}

    return jsonify(payload), backend_response.status_code


@app.post("/api/pages/<path:page_slug>/like")
def like_project_route(page_slug: str):
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Inicia sesion para dar like."}), 401

    page_dir = find_page_directory_by_slug(page_slug)
    if page_dir is None:
        return jsonify({"error": "Proyecto no encontrado."}), 404

    result = set_project_like(page_dir.name, int(user["id"]), liked=True)
    return jsonify(result), 200


@app.delete("/api/pages/<path:page_slug>/like")
def unlike_project_route(page_slug: str):
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Inicia sesion para quitar tu like."}), 401

    page_dir = find_page_directory_by_slug(page_slug)
    if page_dir is None:
        return jsonify({"error": "Proyecto no encontrado."}), 404

    result = set_project_like(page_dir.name, int(user["id"]), liked=False)
    return jsonify(result), 200


@app.get("/api/auth/session")
def auth_session():
    user = get_current_user()
    return jsonify({"authenticated": user is not None, "user": user})


@app.get("/api/ratings")
@app.get("/api/chat/messages")
def chat_messages():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Inicia sesion para ver las valoraciones."}), 401
    return jsonify({"messages": load_chat_messages(), "summary": get_rating_summary(), "user": user})


@app.post("/api/ratings")
@app.post("/api/chat/messages")
def create_chat_message_route():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Inicia sesion para dejar una valoracion."}), 401

    payload = request.get_json(silent=True)
    raw_message = ""
    raw_rating: object = RATING_MAX
    if isinstance(payload, dict):
        raw_message = str(payload.get("message") or "")
        raw_rating = payload.get("rating", RATING_MAX)

    try:
        message = create_chat_message(user, raw_message, raw_rating)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    emit_chat_message(message)
    return jsonify({"message": message, "summary": get_rating_summary()}), 201


@app.get("/health")
def health_check():
    return jsonify({
        "status": "ok",
        "instance_id": SERVER_INSTANCE_ID,
        "started_at": SERVER_STARTED_AT,
        "timestamp": utc_now_iso(),
    }), 200


@app.get("/api/monitor/events")
def get_monitor_events_route():
    try:
        events = load_monitor_events(limit=120)
    except Exception:
        app.logger.exception("Could not retrieve monitor events")
        return jsonify({"error": "Failed to retrieve monitor events"}), 500

    return jsonify({"events": events, "total": len(events)}), 200


def execute_monitor_command(command: str) -> dict[str, object]:
    """Execute a monitoring command and return results."""
    parts = command.strip().lower().split()
    if not parts:
        return {"error": "Comando vacío"}
    
    cmd = parts[0]
    monitor_events = load_monitor_events()
    
    try:
        if cmd == "/status":
            uptime = datetime.now(timezone.utc) - datetime.fromisoformat(SERVER_STARTED_AT)
            uptime_secs = int(uptime.total_seconds())
            hours, remainder = divmod(uptime_secs, 3600)
            minutes, seconds = divmod(remainder, 60)
            return {
                "command": cmd,
                "result": {
                    "instance_id": SERVER_INSTANCE_ID,
                    "uptime": f"{hours}h {minutes}m {seconds}s",
                    "started_at": SERVER_STARTED_AT,
                    "total_monitor_events": len(monitor_events),
                },
            }
        
        elif cmd == "/stats" or cmd == "/stats" and len(parts) > 1:
            period = parts[1] if len(parts) > 1 else "all"
            
            if period == "daily" or period == "today":
                today = datetime.now(APP_TIMEZONE).date()
                today_events = [
                    event
                    for event in monitor_events
                    if str(event.get("timestamp") or "").startswith(today.isoformat())
                ]
                
                return {
                    "command": f"{cmd} {period}",
                    "result": {
                        "date": today.isoformat(),
                        "total_events": len(today_events),
                        "events_by_type": dict(Counter(event.get("type") for event in today_events)),
                    },
                }
            else:
                event_types = Counter(event.get("type") for event in monitor_events)
                return {
                    "command": cmd,
                    "result": {
                        "total_events": len(monitor_events),
                        "events_by_type": dict(event_types),
                        "file": str(MONITOR_LOG_FILE),
                    },
                }
        
        elif cmd == "/logs":
            subcommand = parts[1] if len(parts) > 1 else "count"
            
            if subcommand == "count":
                try:
                    lines = MONITOR_LOG_FILE.read_text(encoding="utf-8").strip().split("\n") if MONITOR_LOG_FILE.exists() else []
                    return {
                        "command": f"{cmd} {subcommand}",
                        "result": {
                            "total_log_lines": len([l for l in lines if l]),
                            "file": str(MONITOR_LOG_FILE),
                        },
                    }
                except Exception as e:
                    return {"error": f"Error reading log file: {e}"}
            
            elif subcommand == "today":
                try:
                    today = datetime.now(APP_TIMEZONE).date()
                    lines = MONITOR_LOG_FILE.read_text(encoding="utf-8").strip().split("\n") if MONITOR_LOG_FILE.exists() else []
                    today_logs = []
                    for line in lines:
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            event_date = event.get("timestamp", "").split("T")[0]
                            if event_date == today.isoformat():
                                today_logs.append(event)
                        except json.JSONDecodeError:
                            pass
                    
                    return {
                        "command": f"{cmd} {subcommand}",
                        "result": {
                            "date": today.isoformat(),
                            "logs_today": len(today_logs),
                        },
                    }
                except Exception as e:
                    return {"error": f"Error reading logs: {e}"}
            else:
                return {"error": f"Subcomando desconocido: {subcommand}"}
        
        elif cmd == "/events":
            subcommand = parts[1] if len(parts) > 1 else "summary"
            
            if subcommand == "summary":
                event_types = Counter(event.get("type") for event in monitor_events)
                return {
                    "command": f"{cmd} {subcommand}",
                    "result": {
                        "total_events": len(monitor_events),
                        "event_types": dict(event_types),
                        "file": str(MONITOR_LOG_FILE),
                    },
                }
            elif subcommand == "recent":
                limit = int(parts[2]) if len(parts) > 2 else 10
                recent = monitor_events[-max(1, limit) :]
                return {
                    "command": f"{cmd} {subcommand}",
                    "result": {
                        "count": len(recent),
                        "events": [
                            {
                                "timestamp": event.get("timestamp"),
                                "type": event.get("type"),
                                "details": event.get("details"),
                            }
                            for event in recent
                        ],
                    },
                }
            else:
                return {"error": f"Subcomando desconocido: {subcommand}"}
        
        elif cmd == "/help":
            return {
                "command": cmd,
                "result": {
                    "commands": [
                        "/status - Información general del servidor",
                        "/stats [daily|today] - Estadísticas de eventos",
                        "/logs [count|today] - Información de archivos de log",
                        "/events [summary|recent [N]] - Detalles de eventos almacenados",
                        "/help - Mostrar este mensaje",
                    ],
                },
            }
        
        else:
            return {"error": f"Comando no reconocido: {cmd}. Usa /help para ver comandos disponibles."}
    
    except Exception as e:
        app.logger.exception(f"Error executing command: {cmd}")
        return {"error": f"Error ejecutando comando: {e}"}


@app.post("/api/monitor/command")
def execute_monitor_command_route():
    user = get_current_user()
    if user is None or not is_owner_user(user):
        return jsonify({"error": "Solo propietarios pueden ejecutar comandos."}), 403
    
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command", "")).strip()
    
    if not command:
        return jsonify({"error": "Comando vacío"}), 400
    
    result = execute_monitor_command(command)
    return jsonify(result), 200


@app.get("/pages/<path:asset_path>")
def serve_page_assets(asset_path: str):
    clean_parts = [part for part in Path(asset_path).parts if part not in {"", "."}]
    if any(part == ".." for part in clean_parts):
        abort(404)

    requested_path = PAGES_DIR.joinpath(*clean_parts)
    if not requested_path.exists() and clean_parts:
        page_dir = find_page_directory_by_slug(clean_parts[0])
        if page_dir is not None:
            requested_path = page_dir.joinpath(*clean_parts[1:])

    if requested_path.is_dir():
        index_file = requested_path / "index.html"
        if index_file.is_file():
            record_visit(f"/pages/{'/'.join(clean_parts)}/")
            return send_from_directory(PAGES_DIR, str(index_file.relative_to(PAGES_DIR)))
        abort(404)

    if requested_path.is_file():
        if requested_path.name == "index.html":
            parent_parts = clean_parts[:-1]
            page_path = "/pages/"
            if parent_parts:
                page_path += f"{'/'.join(parent_parts)}/"
            record_visit(page_path)
        return send_from_directory(PAGES_DIR, str(requested_path.relative_to(PAGES_DIR)))

    if "." not in requested_path.name:
        index_file = requested_path / "index.html"
        if index_file.is_file():
            record_visit(f"/pages/{'/'.join(clean_parts)}/")
            return send_from_directory(PAGES_DIR, str(index_file.relative_to(PAGES_DIR)))

    abort(404)


ensure_storage()
load_visit_stats()


def run_server() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))

    if socketio_lib is None:
        app.logger.warning("python-socketio is not installed; realtime visits are disabled.")

    try:
        from waitress import serve
    except ModuleNotFoundError:
        app.logger.warning(
            "waitress is not installed; falling back to Flask development server."
        )
        app.run(host=host, port=port, debug=False, use_reloader=False)
        return

    serve(app, host=host, port=port)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(run_cli(sys.argv))
    run_server()
