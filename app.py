from __future__ import annotations

import atexit
import json
import logging
import os
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Callable
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_from_directory,
)


try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media"
ANALYTICS_DIR = BASE_DIR / "analytics"
DATA_DIR = BASE_DIR / "data"
VISITS_LOG_FILE = ANALYTICS_DIR / "visits.jsonl"
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "nigahahhaghaghahahghagha")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
APP_TIMEZONE_NAME = os.getenv("APP_TIMEZONE", os.getenv("TZ", "America/Asuncion"))
APP_VERSION = os.getenv("APP_VERSION", "4.0.1")

# Frases del efecto typewriter en el banner de inicio (se eligen al azar).
HOME_BANNER_TYPEWRITER_PHRASES = [
    "Proyectos, experimentos y builds al azar.",
    "Si llegaste hasta acá, bienvenido al catálogo.",
    "Backend, automatización y diseño sin fórmulas fijas.",
    "Dev independiente construyendo cosas raras.",
    "Sin garantías de calidad garantizada.",
    "Mezclo código, curiosidad y lo que salga.",
]

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
DEVICE_LABELS_ES = {
    "desktop": "Escritorio",
    "mobile": "Movil",
    "tablet": "Tablet",
    "desconocido": "Desconocido",
}
PROJECT_CATEGORY_MUSICAL = "musical"
PROJECT_CATEGORY_INTERACTIVE = "interactive"
REPO_PAGES_ROOT = Path(
    os.getenv("REPO_PAGES_ROOT", str(Path.home() / "repopages"))
).expanduser().resolve()
PAGES_DIR_BY_CATEGORY: dict[str, Path] = {
    PROJECT_CATEGORY_MUSICAL: Path(
        os.getenv(
            "PAGES_MUSICAL_DIR",
            str(REPO_PAGES_ROOT / "paginas_musicales"),
        )
    ).expanduser().resolve(),
    PROJECT_CATEGORY_INTERACTIVE: Path(
        os.getenv(
            "PAGES_INTERACTIVE_DIR",
            str(REPO_PAGES_ROOT / "paginas_interactivas"),
        )
    ).expanduser().resolve(),
}
PROJECT_CATEGORY_DIRECTORY_NAMES = {
    PROJECT_CATEGORY_MUSICAL: "paginas_musicales",
    PROJECT_CATEGORY_INTERACTIVE: "paginas_interactivas",
}
PROJECT_CATEGORY_DIRECTORY_ALIASES = {
    "paginas-musicales": PROJECT_CATEGORY_MUSICAL,
    "paginas_musicales": PROJECT_CATEGORY_MUSICAL,
    "musicales": PROJECT_CATEGORY_MUSICAL,
    "musical": PROJECT_CATEGORY_MUSICAL,
    "musica": PROJECT_CATEGORY_MUSICAL,
    "music": PROJECT_CATEGORY_MUSICAL,
    "paginas-interactivas": PROJECT_CATEGORY_INTERACTIVE,
    "paginas_interactivas": PROJECT_CATEGORY_INTERACTIVE,
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
app.config["TEMPLATES_AUTO_RELOAD"] = os.getenv("TEMPLATES_AUTO_RELOAD", "1") == "1"
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = app.config["TEMPLATES_AUTO_RELOAD"]
app.logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


@app.context_processor
def inject_app_metadata() -> dict[str, str]:
    return {"app_version": APP_VERSION}


VISITS_LOCK = Lock()
VISITS_TOTAL = 0
VISITS_BY_DEVICE: Counter[str] = Counter()
VISITS_BY_PAGE: Counter[str] = Counter()
VISIT_EVENTS: list[dict[str, str]] = []
FAVICON_COLOR_CACHE: dict[str, str | None] = {}


def ensure_storage() -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VISITS_LOG_FILE.touch(exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_device_category(value: str | None) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in DEVICE_LABELS_ES:
        return cleaned
    return "desconocido"


def infer_device_category(user_agent: str | None) -> str:
    haystack = str(user_agent or "").strip().lower()
    if not haystack:
        return "desconocido"
    if any(token in haystack for token in ("ipad", "tablet", "kindle", "playbook", "silk/")):
        return "tablet"
    if any(
        token in haystack
        for token in ("mobile", "iphone", "ipod", "android", "blackberry", "phone")
    ):
        return "mobile"
    return "desktop"


def format_visit_device_label(device: str) -> str:
    normalized_device = normalize_device_category(device)
    return DEVICE_LABELS_ES.get(normalized_device, normalized_device.title())


def build_visit_event(
    *,
    page: str,
    observed_at: datetime | None = None,
    device: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    timestamp = observed_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    local_timestamp = timestamp.astimezone(APP_TIMEZONE)
    resolved_device = normalize_device_category(
        device or infer_device_category(user_agent)
    )
    return {
        "at": timestamp.isoformat(),
        "date": local_timestamp.date().isoformat(),
        "time": local_timestamp.strftime("%H:%M:%S"),
        "device": resolved_device,
        "page": canonicalize_page_path(page),
    }


def canonicalize_page_path(page: str | None) -> str:
    cleaned = str(page or "").strip() or "/"
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"

    if cleaned.startswith("/pages/"):
        slug = cleaned[len("/pages/") :].strip("/")
        return f"/pages/{slug}/" if slug else "/pages/"

    cleaned = cleaned.rstrip("/") or "/"
    return cleaned


def get_page_label(page: str) -> str:
    normalized = canonicalize_page_path(page)
    if normalized == "/":
        return "Inicio"
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


def build_visit_device_timeline(
    visit_events: list[dict[str, object]],
    *,
    bucket_limit: int = 10,
    series_limit: int = 4,
) -> dict:
    return build_visit_timeline(
        visit_events,
        label_resolver=lambda event: format_visit_device_label(str(event.get("device") or "")),
        bucket_limit=bucket_limit,
        series_limit=series_limit,
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


def load_visit_stats() -> None:
    global VISITS_TOTAL

    if not VISITS_LOG_FILE.is_file():
        return

    with VISITS_LOCK:
        VISITS_TOTAL = 0
        VISITS_BY_DEVICE.clear()
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

                page = canonicalize_page_path(str(event.get("page") or "/"))
                normalized_event = build_visit_event(
                    page=page,
                    observed_at=parse_visit_timestamp(str(event.get("at") or "")),
                    device=str(event.get("device") or ""),
                    user_agent=str(event.get("user_agent") or ""),
                )

                VISITS_TOTAL += 1
                VISITS_BY_DEVICE[normalized_event["device"]] += 1
                VISITS_BY_PAGE[page] += 1
                VISIT_EVENTS.append(normalized_event)


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
            "date": str(event.get("date") or ""),
            "time": str(event.get("time") or ""),
            "page": canonicalize_page_path(str(event.get("page") or "/")),
            "device": normalize_device_category(str(event.get("device") or "")),
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
    by_device_counter: Counter[str] = Counter()
    by_page_counter: Counter[str] = Counter()

    for event in filtered_project_events:
        by_device_counter[str(event["device"])] += 1
        by_page_counter[str(event["page"])] += 1

    top_pages = [
        {"path": page, "label": get_page_label(page), "count": total}
        for page, total in by_page_counter.most_common(12)
    ]

    return {
        "total": total_visits,
        "by_device": {
            format_visit_device_label(device): total
            for device, total in by_device_counter.most_common()
        },
        "top_pages": top_pages,
        "device_timeline": build_visit_device_timeline(filtered_project_events, bucket_limit=10),
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


def record_visit(page: str) -> None:
    global VISITS_TOTAL

    page = canonicalize_page_path(page)
    event = build_visit_event(
        page=page,
        user_agent=request.headers.get("User-Agent", ""),
    )

    try:
        with VISITS_LOCK:
            with VISITS_LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(f"{json.dumps(event, ensure_ascii=True)}\n")

            VISITS_TOTAL += 1
            VISITS_BY_DEVICE[event["device"]] += 1
            VISITS_BY_PAGE[page] += 1
            VISIT_EVENTS.append(event.copy())

            total_visits = VISITS_TOTAL
            device_total = VISITS_BY_DEVICE[event["device"]]
    except OSError:
        app.logger.exception("Could not write visit analytics to %s", VISITS_LOG_FILE)
        return

    app.logger.info(
        "[visit] total=%s device=%s device_total=%s page=%s date=%s time=%s",
        total_visits,
        event["device"],
        device_total,
        page,
        event["date"],
        event["time"],
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


def get_page_roots() -> tuple[Path, ...]:
    return tuple(PAGES_DIR_BY_CATEGORY.values())


def resolve_page_root(page_dir: Path) -> Path | None:
    resolved_page_dir = page_dir.resolve()
    for pages_root in get_page_roots():
        resolved_root = pages_root.resolve()
        try:
            resolved_page_dir.relative_to(resolved_root)
        except ValueError:
            continue
        return resolved_root
    return None


def build_page_storage_path(page_dir: Path) -> str:
    pages_root = resolve_page_root(page_dir)
    if pages_root is None:
        return page_dir.as_posix()
    return page_dir.relative_to(pages_root).as_posix()


def iter_project_directories() -> list[tuple[str, Path, os.stat_result]]:
    project_directories: list[tuple[str, Path, os.stat_result]] = []

    for category, pages_root in PAGES_DIR_BY_CATEGORY.items():
        if not pages_root.is_dir():
            continue

        for page_dir in pages_root.iterdir():
            if not page_dir.is_dir():
                continue

            index_file = page_dir / "index.html"
            if index_file.is_file():
                project_directories.append((category, page_dir, index_file.stat()))

    return project_directories


def find_page_directory_by_slug(slug: str) -> Path | None:
    normalized_slug = str(slug or "").strip()
    if not normalized_slug:
        return None

    for pages_root in get_page_roots():
        if not pages_root.is_dir():
            continue

        candidate = pages_root / normalized_slug
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate

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


def build_projects_overview(pages: list[dict]) -> dict[str, object]:
    project_views = sum(int(page.get("visit_count") or 0) for page in pages)
    featured_pages = sorted(
        pages,
        key=lambda page: (
            int(page.get("visit_count") or 0),
            str(page.get("updated_at") or ""),
        ),
        reverse=True,
    )
    return {
        "project_count": len(pages),
        "project_views": project_views,
        "featured_pages": featured_pages[:3],
    }


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

    relative_asset_path = favicon_file.relative_to(page_dir).as_posix()
    return f"/pages/{page_dir.name}/{relative_asset_path}"


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
                "storage_path": build_page_storage_path(page_dir),
                "version": changelog.get("version"),
                "has_changelog": bool(changelog.get("available")),
                "changelog_url": build_project_changelog_url(slug),
                "favicon_url": discover_favicon_url(page_dir),
                "favicon_color": discover_favicon_color(page_dir),
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "visit_count": get_page_visit_count(build_project_page_path(slug)),
            }
        )

    return pages


@app.get("/")
def home():
    record_visit("/")
    pages = discover_pages()
    overview = build_projects_overview(pages)
    return render_template(
        "index.html",
        app_timezone_name=APP_TIMEZONE_NAME,
        pages=pages,
        project_views=overview["project_views"],
        featured_pages=overview["featured_pages"],
        banner_typewriter_phrases=HOME_BANNER_TYPEWRITER_PHRASES,
    )


@app.get("/projects")
def projects_page():
    record_visit("/projects")
    return render_template(
        "projects.html",
        app_timezone_name=APP_TIMEZONE_NAME,
    )


@app.get("/projects/<path:page_slug>/changelog")
def project_changelog_page(page_slug: str):
    page_dir = find_page_directory_by_slug(page_slug)
    if page_dir is None:
        abort(404)

    record_visit(build_project_page_path(page_dir.name))
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
        app_timezone_name=APP_TIMEZONE_NAME,
        page=page_data,
        changelog=changelog,
    )


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


@app.get("/health")
def health_check():
    return jsonify({
        "status": "ok",
        "version": APP_VERSION,
        "instance_id": SERVER_INSTANCE_ID,
        "started_at": SERVER_STARTED_AT,
        "timestamp": utc_now_iso(),
    }), 200


@app.get("/pages/<path:asset_path>")
def serve_page_assets(asset_path: str):
    clean_parts = [part for part in Path(asset_path).parts if part not in {"", "."}]
    if any(part == ".." for part in clean_parts):
        abort(404)

    if not clean_parts:
        abort(404)

    slug = clean_parts[0]
    page_dir = find_page_directory_by_slug(slug)
    if page_dir is not None:
        pages_root = resolve_page_root(page_dir)
        if pages_root is not None:
            if len(clean_parts) == 1:
                index_file = page_dir / "index.html"
                if index_file.is_file():
                    record_visit(f"/pages/{slug}/")
                    return send_from_directory(
                        pages_root,
                        str(index_file.relative_to(pages_root)),
                    )
                abort(404)

            requested_path = page_dir.joinpath(*clean_parts[1:])
            if requested_path.is_dir():
                index_file = requested_path / "index.html"
                if index_file.is_file():
                    record_visit(f"/pages/{'/'.join(clean_parts)}/")
                    return send_from_directory(
                        pages_root,
                        str(index_file.relative_to(pages_root)),
                    )
                abort(404)

            if requested_path.is_file():
                if requested_path.name == "index.html":
                    parent_parts = clean_parts[:-1]
                    page_path = "/pages/"
                    if parent_parts:
                        page_path += f"{'/'.join(parent_parts)}/"
                    record_visit(page_path)
                return send_from_directory(
                    pages_root,
                    str(requested_path.relative_to(pages_root)),
                )

            if "." not in requested_path.name:
                index_file = requested_path / "index.html"
                if index_file.is_file():
                    record_visit(f"/pages/{'/'.join(clean_parts)}/")
                    return send_from_directory(
                        pages_root,
                        str(index_file.relative_to(pages_root)),
                    )

    for pages_root in get_page_roots():
        if not pages_root.is_dir():
            continue

        requested_path = pages_root.joinpath(*clean_parts)
        if requested_path.is_dir():
            index_file = requested_path / "index.html"
            if index_file.is_file():
                record_visit(f"/pages/{'/'.join(clean_parts)}/")
                return send_from_directory(
                    pages_root,
                    str(index_file.relative_to(pages_root)),
                )
            continue

        if requested_path.is_file():
            if requested_path.name == "index.html":
                parent_parts = clean_parts[:-1]
                page_path = "/pages/"
                if parent_parts:
                    page_path += f"{'/'.join(parent_parts)}/"
                record_visit(page_path)
            return send_from_directory(
                pages_root,
                str(requested_path.relative_to(pages_root)),
            )

        if "." not in requested_path.name:
            index_file = requested_path / "index.html"
            if index_file.is_file():
                record_visit(f"/pages/{'/'.join(clean_parts)}/")
                return send_from_directory(
                    pages_root,
                    str(index_file.relative_to(pages_root)),
                )

    abort(404)


ensure_storage()
load_visit_stats()


def run_server() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))

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
    run_server()