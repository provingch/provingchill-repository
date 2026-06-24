#!/usr/bin/env python3
"""
Monitor script for the main backend application.
Beautiful terminal interface with real-time monitoring.
"""

import mimetypes
import json
import logging
import subprocess
import sys
import time
from http import HTTPStatus
from http.client import HTTPConnection, HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from urllib.parse import unquote, urlparse

try:
    import socketio
except ImportError:
    socketio = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.columns import Columns
    from rich.align import Align
    from rich.layout import Layout
except ImportError:
    Console = None

# Configuration
BACKEND_URL = "http://localhost:8080"  # Adjust if needed
HEALTH_ENDPOINT = f"{BACKEND_URL}/health"
CHECK_INTERVAL = 0.5  # seconds
LOG_FILE = Path(__file__).resolve().parent / "analytics" / "monitor_events.jsonl"
VISITS_FILE = Path(__file__).resolve().parent / "analytics" / "visits.jsonl"
PROCESS_CMD_PATTERN = "app.py"  # Pattern to match the backend process
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MEDIA_DIR = BASE_DIR / "media"
MONITOR_LOOP_SLEEP = CHECK_INTERVAL
MAINTENANCE_AUTO_REFRESH_SECONDS = 18

# Socket.IO configuration for emitting events
SOCKET_IO_URL = "http://localhost:8080"
MONITOR_ROOM = "monitor:owners"

BACKEND_URI = urlparse(BACKEND_URL)
BACKEND_HOST = BACKEND_URI.hostname or "127.0.0.1"
BACKEND_PORT = BACKEND_URI.port or (443 if BACKEND_URI.scheme == "https" else 80)

logging.basicConfig(
    level=logging.WARNING,  # Reduce log noise for clean terminal
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def log_event(event_type: str, details: dict[str, Any]) -> None:
    """Log a monitoring event to the JSONL file."""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "details": details,
    }
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            json.dump(event, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        logger.error(f"Failed to log event: {e}")


def load_visits() -> list[dict[str, Any]]:
    """Load visit data from the visits JSONL file."""
    visits = []
    if not VISITS_FILE.exists():
        return visits
    
    try:
        with VISITS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        visit = json.loads(line)
                        visits.append(visit)
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        logger.error(f"Failed to load visits: {e}")
    
    return visits


def get_visits_summary() -> dict[str, Any]:
    """Calculate visit statistics."""
    visits = load_visits()
    
    if not visits:
        return {
            "total": 0,
            "by_source": {},
            "by_page": {},
            "recent": [],
        }
    
    # Count by source
    by_source: dict[str, int] = {}
    for visit in visits:
        source = visit.get("source", "direct")
        by_source[source] = by_source.get(source, 0) + 1
    
    # Count by page
    by_page: dict[str, int] = {}
    for visit in visits:
        page = visit.get("page", "/")
        by_page[page] = by_page.get(page, 0) + 1
    
    # Get recent visits (last 20)
    recent = visits[-20:] if len(visits) > 20 else visits
    
    return {
        "total": len(visits),
        "by_source": by_source,
        "by_page": by_page,
        "recent": recent,
    }


def check_http_health() -> bool:
    """Check backend health via HTTP."""
    connection_class = HTTPSConnection if BACKEND_URI.scheme == "https" else HTTPConnection
    connection = None

    try:
        connection = connection_class(BACKEND_HOST, BACKEND_PORT, timeout=5)
        request_path = BACKEND_URI.path.rstrip("/") or ""
        connection.request("GET", f"{request_path}/health" if request_path else "/health")
        response = connection.getresponse()
        return response.status == HTTPStatus.OK
    except OSError:
        return False
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


def scan_process() -> bool:
    """Scan for the backend process."""
    if psutil is None:
        try:
            result = subprocess.run(
                ["ps", "-eo", "args="],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return False

        for raw_line in result.stdout.splitlines():
            if PROCESS_CMD_PATTERN in raw_line and "monitor.py" not in raw_line:
                return True
        return False

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any(PROCESS_CMD_PATTERN in arg for arg in cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except Exception:
        return False


def create_status_panel(title: str, status: bool, details: str) -> Panel:
    """Create a status panel with color coding."""
    if status:
        color = "green"
        icon = "✓"
        status_text = "OK"
    else:
        color = "red"
        icon = "✗"
        status_text = "ERROR"
    
    content = f"[{color}]{icon} {status_text}[/{color}]\n{details}"
    return Panel(content, title=f"[bold]{title}[/bold]", border_style=color)


def create_events_table(events: list[dict[str, Any]]) -> Table:
    """Create a table of recent events."""
    table = Table(title="Eventos Recientes", show_header=True, header_style="bold magenta")
    table.add_column("Hora", style="cyan", no_wrap=True)
    table.add_column("Tipo", style="yellow", no_wrap=True)
    table.add_column("Detalles", style="white")
    
    for event in events[-10:]:  # Show last 10 events
        timestamp = datetime.fromisoformat(event.get("timestamp", "")).strftime("%H:%M:%S")
        event_type = event.get("type", "unknown")
        details = json.dumps(event.get("details", {}), ensure_ascii=False)
        
        # Color code event types
        if "reachable" in event_type or "found" in event_type:
            type_style = "green"
        elif "unreachable" in event_type or "missing" in event_type:
            type_style = "red"
        elif "connected" in event_type:
            type_style = "blue"
        elif "disconnected" in event_type:
            type_style = "dim"
        else:
            type_style = "yellow"
        
        table.add_row(timestamp, f"[{type_style}]{event_type}[/{type_style}]", details)
    
    return table


def create_visits_table(visits_summary: dict[str, Any]) -> Table:
    """Create a table of visit statistics."""
    table = Table(title="Estadisticas de Visitas", show_header=True, header_style="bold cyan")
    table.add_column("Metrica", style="yellow", no_wrap=True)
    table.add_column("Valor", style="white")
    
    total = visits_summary.get("total", 0)
    table.add_row("Total de visitas", str(total))
    
    by_source = visits_summary.get("by_source", {})
    if by_source:
        for source, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True)[:5]:
            table.add_row(f"  Por origen: {source}", str(count))
    
    by_page = visits_summary.get("by_page", {})
    if by_page:
        for page, count in sorted(by_page.items(), key=lambda x: x[1], reverse=True)[:5]:
            table.add_row(f"  Por pagina: {page}", str(count))
    
    return table


def create_layout(http_ok: bool, process_ok: bool, events: list[dict[str, Any]], visits_summary: dict[str, Any] | None = None) -> Layout:
    """Create the main layout."""
    layout = Layout()
    
    # Header
    header = Panel(
        Align.center("[bold blue]🔍 Monitor de Backend[/bold blue]\n[italic]Sistema de monitoreo en tiempo real[/italic]"),
        border_style="blue"
    )
    
    # Status panels
    http_panel = create_status_panel(
        "HTTP Heartbeat",
        http_ok,
        f"Endpoint: {HEALTH_ENDPOINT}\nÚltima verificación: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    process_panel = create_status_panel(
        "Proceso Backend",
        process_ok,
        f"Patrón: {PROCESS_CMD_PATTERN}\nÚltima verificación: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    status_row = Columns([http_panel, process_panel], equal=True, expand=True)
    
    # Events table
    events_table = create_events_table(events)
    
    # Visits table (only if data available)
    visits_table = None
    if visits_summary and visits_summary.get("total", 0) > 0:
        visits_table = create_visits_table(visits_summary)
    
    # Footer
    footer = Panel(
        f"[dim]Actualización cada {CHECK_INTERVAL}s | Eventos totales: {len(events)}[/dim]",
        border_style="dim"
    )
    
    # Combine layout
    if visits_table:
        layout.split(
            Layout(header, size=5),
            Layout(status_row, size=12),
            Layout(visits_table, size=12),
            Layout(events_table, size=15),
            Layout(footer, size=3)
        )
    else:
        layout.split(
            Layout(header, size=5),
            Layout(status_row, size=12),
            Layout(events_table, size=20),
            Layout(footer, size=3)
        )
    
    return layout


def load_shared_styles() -> str:
    """Load the site's shared stylesheet so the placeholder matches the portal."""
    styles_path = STATIC_DIR / "styles.css"
    try:
        return styles_path.read_text(encoding="utf-8")
    except OSError:
        logger.exception("Failed to read shared styles from %s", styles_path)
        return ""


def build_maintenance_html(*, generated_at: datetime | None = None) -> str:
    """Build the emergency maintenance page with the same visual language as the site."""
    generated_at = generated_at or datetime.now(timezone.utc)
    styles = load_shared_styles()
    generated_label = generated_at.astimezone().strftime("%d/%m/%Y %H:%M:%S")
    refresh_seconds = str(MAINTENANCE_AUTO_REFRESH_SECONDS)

    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="refresh" content="{refresh_seconds}" />
    <title>Volvemos pronto | ProvingChill</title>
    <link rel="icon" type="image/png" href="/media/favicon.png" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Syne:wght@600;700;800&display=swap"
      rel="stylesheet"
    />
    <style>
      {styles}

      .maintenance-shell {{
        padding: 1.4rem 0 2.8rem;
      }}

      .maintenance-wrap {{
        display: grid;
        gap: 1rem;
      }}

      .maintenance-panel,
      .maintenance-side {{
        padding: 1.3rem;
      }}

      .maintenance-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.15fr) minmax(18rem, 0.85fr);
        gap: 1rem;
      }}

      .maintenance-kicker {{
        margin: 0 0 0.65rem;
        color: #d8deea;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
      }}

      .maintenance-panel h1,
      .maintenance-side h2 {{
        margin: 0;
      }}

      .maintenance-panel p,
      .maintenance-side p {{
        color: var(--muted);
        line-height: 1.6;
      }}

      .maintenance-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.65rem;
        margin-top: 1rem;
      }}

      .maintenance-pill {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.44rem 0.72rem;
        border-radius: 999px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(255, 255, 255, 0.04);
        color: #eef3fb;
        font-size: 0.84rem;
        font-weight: 700;
      }}

      .maintenance-dot {{
        width: 0.5rem;
        height: 0.5rem;
        border-radius: 999px;
        background: var(--gold);
        box-shadow: 0 0 0 0 rgba(246, 211, 101, 0.45);
        animation: maintenance-pulse 1.8s ease-out infinite;
      }}

      @keyframes maintenance-pulse {{
        0% {{ box-shadow: 0 0 0 0 rgba(246, 211, 101, 0.45); }}
        70% {{ box-shadow: 0 0 0 8px rgba(246, 211, 101, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(246, 211, 101, 0); }}
      }}

      .maintenance-actions {{
        margin-top: 1rem;
        display: flex;
        gap: 0.65rem;
        flex-wrap: wrap;
      }}

      .maintenance-button {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 2.7rem;
        padding: 0.62rem 1rem;
        border-radius: 0.9rem;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(255, 255, 255, 0.04);
        color: var(--text);
        font: inherit;
        font-weight: 700;
        text-decoration: none;
        cursor: pointer;
        transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
      }}

      .maintenance-button:hover {{
        transform: translateY(-1px);
        border-color: rgba(255, 255, 255, 0.22);
        background: rgba(255, 255, 255, 0.08);
      }}

      .maintenance-button.primary {{
        border-color: rgba(123, 223, 242, 0.26);
        background: rgba(123, 223, 242, 0.12);
      }}

      .maintenance-list {{
        margin: 0.95rem 0 0;
        padding-left: 1.15rem;
        color: var(--muted);
        line-height: 1.65;
      }}

      .maintenance-note {{
        margin-top: 1rem;
        font-size: 0.88rem;
      }}

      @media (max-width: 900px) {{
        .maintenance-grid {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="bg-noise" aria-hidden="true"></div>
    <div class="bg-shape bg-shape-a" aria-hidden="true"></div>
    <div class="bg-shape bg-shape-b" aria-hidden="true"></div>

    <main class="wrapper maintenance-shell">
      <div class="maintenance-wrap">
        <section class="panel maintenance-panel">
          <p class="maintenance-kicker">Mantenimiento automatico</p>
          <h1>Estamos trabajando en la pagina</h1>
          <p>
            El servidor principal está temporalmente fuera de línea o reiniciándose.
            `monitor.py` levantó esta pantalla para avisar que el sitio volverá apenas el backend
            quede estable otra vez.
          </p>
          <div class="maintenance-meta">
            <span class="maintenance-pill"><span class="maintenance-dot"></span> Modo mantenimiento activo</span>
            <span class="maintenance-pill">Ultima actualizacion: {generated_label}</span>
            <span class="maintenance-pill">Reintento automatico cada {refresh_seconds}s</span>
          </div>
          <div class="maintenance-actions">
            <button class="maintenance-button primary" type="button" onclick="window.location.reload()">
              Reintentar ahora
            </button>
            <a class="maintenance-button" href="/monitor">Abrir monitor cuando vuelva</a>
          </div>
        </section>

        <div class="maintenance-grid">
          <section class="panel maintenance-side">
            <p class="maintenance-kicker">Que esta pasando</p>
            <h2>Volvemos despues de este mantenimiento</h2>
            <ul class="maintenance-list">
              <li>Se detectó una caída o reinicio del backend principal.</li>
              <li>El monitor quedó sirviendo esta pantalla temporal mientras se recupera.</li>
              <li>Cuando el server vuelva, esta página se refresca sola para devolverte al sitio.</li>
            </ul>
          </section>

          <section class="panel maintenance-side">
            <p class="maintenance-kicker">Estado</p>
            <h2>Monitor activo</h2>
            <p>
              Si sigues viendo este aviso, el backend todavía no terminó de volver.
              Puedes refrescar manualmente o esperar el reintento automático.
            </p>
            <p class="maintenance-note">
              ProvingChill quedará disponible de nuevo apenas el proceso principal responda.
            </p>
          </section>
        </div>
      </div>
    </main>
  </body>
</html>
"""


def is_json_request_path(path: str) -> bool:
    return path == "/health" or path.startswith("/api/")


def guess_content_type(path: Path) -> str:
    guessed_type, _ = mimetypes.guess_type(str(path))
    return guessed_type or "application/octet-stream"


class MaintenanceRequestHandler(BaseHTTPRequestHandler):
    """Serve a maintenance placeholder using the site's visual language."""

    server_version = "ProvingChillMaintenance/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        logger.info("maintenance-http %s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        request_path = unquote(parsed.path or "/")

        if request_path.startswith("/static/"):
            self._serve_local_file(STATIC_DIR, request_path[len("/static/") :])
            return

        if request_path.startswith("/media/"):
            self._serve_local_file(MEDIA_DIR, request_path[len("/media/") :])
            return

        if is_json_request_path(request_path):
            payload = {
                "status": "maintenance",
                "message": "El backend principal esta en mantenimiento y volvera pronto.",
                "retry_after_seconds": MAINTENANCE_AUTO_REFRESH_SECONDS,
            }
            self._respond_json(payload, status=HTTPStatus.SERVICE_UNAVAILABLE)
            return

        html = build_maintenance_html()
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Retry-After", str(MAINTENANCE_AUTO_REFRESH_SECONDS))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        request_path = unquote(parsed.path or "/")
        if is_json_request_path(request_path):
            self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return

        self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def _serve_local_file(self, root_dir: Path, relative_path: str) -> None:
        clean_parts = [part for part in Path(relative_path).parts if part not in {"", "."}]
        if any(part == ".." for part in clean_parts):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        target_path = root_dir.joinpath(*clean_parts)
        if not target_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            payload = target_path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", guess_content_type(target_path))
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(payload)

    def _respond_json(self, payload: dict[str, Any], *, status: HTTPStatus) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Retry-After", str(MAINTENANCE_AUTO_REFRESH_SECONDS))
        self.end_headers()
        self.wfile.write(body)


class MaintenancePlaceholderServer:
    """Best-effort emergency server that serves a maintenance placeholder on the backend port."""

    def __init__(self, host: str = BACKEND_HOST, port: int = BACKEND_PORT):
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._lock = Lock()
        self.started_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._lock:
            if self.is_running:
                return True

            try:
                server = ThreadingHTTPServer((self.host, self.port), MaintenanceRequestHandler)
            except OSError as exc:
                logger.warning("Could not start maintenance placeholder on %s:%s: %s", self.host, self.port, exc)
                return False

            server.daemon_threads = True
            self._server = server
            self.host = str(server.server_address[0])
            self.port = int(server.server_address[1])
            self.started_at = datetime.now(timezone.utc)
            self._thread = Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.5},
                name="maintenance-placeholder-server",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
            self.started_at = None

        if server is not None:
            try:
                server.shutdown()
            except Exception:
                logger.exception("Failed to shutdown maintenance placeholder server cleanly")
            try:
                server.server_close()
            except Exception:
                logger.exception("Failed to close maintenance placeholder server socket")

        if thread is not None:
            thread.join(timeout=2)


def main() -> None:
    """Main monitoring loop with beautiful terminal interface."""
    if Console is None:
        print("❌ Rich library not available. Install with: pip install rich")
        sys.exit(1)
    
    console = Console()
    console.print("[bold green]🚀 Iniciando Monitor de Backend...[/bold green]")
    
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)
    
    # Initialize Socket.IO client
    sio = None
    if socketio is not None:
        try:
            sio = socketio.Client(
                engineio_logger=False,
                logger=False,
                reconnection=True,
                reconnection_delay=1,
                reconnection_attempts=10,
            )
            
            @sio.event
            def connect():
                console.print("[green]✓ Conectado a Socket.IO[/green]")
            
            @sio.event
            def disconnect():
                console.print("[red]✗ Desconectado de Socket.IO[/red]")
            
            sio.connect(SOCKET_IO_URL, wait_timeout=5)
        except Exception as e:
            console.print(f"[red]⚠ No se pudo conectar a Socket.IO: {e}[/red]")
            sio = None
    else:
        console.print("[yellow]⚠ Socket.IO no disponible, eventos no se emitirán[/yellow]")
    
    # Load existing events
    events = []
    if LOG_FILE.exists():
        try:
            with LOG_FILE.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            event = json.loads(line)
                            events.append(event)
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            console.print(f"[red]Error cargando eventos existentes: {e}[/red]")
    
    last_health_ok = None
    last_process_ok = None
    maintenance_server = MaintenancePlaceholderServer()
    maintenance_start_failed = False
    
    try:
        with Live(console=console, refresh_per_second=1, screen=True) as live:
            while True:
                health_ok = check_http_health()
                process_ok = scan_process()

                if maintenance_server.is_running and (health_ok or process_ok):
                    maintenance_server.stop()
                    event_data = {
                        "reason": "backend_recovered" if health_ok else "backend_process_detected",
                        "host": maintenance_server.host,
                        "port": maintenance_server.port,
                    }
                    log_event("maintenance_placeholder_disabled", event_data)
                    events.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "type": "maintenance_placeholder_disabled",
                        "details": event_data,
                    })
                    maintenance_start_failed = False

                should_start_placeholder = (not health_ok) and (not process_ok)
                if should_start_placeholder and not maintenance_server.is_running:
                    if maintenance_server.start():
                        event_data = {
                            "host": maintenance_server.host,
                            "port": maintenance_server.port,
                            "refresh_seconds": MAINTENANCE_AUTO_REFRESH_SECONDS,
                        }
                        log_event("maintenance_placeholder_enabled", event_data)
                        events.append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "type": "maintenance_placeholder_enabled",
                            "details": event_data,
                        })
                        maintenance_start_failed = False
                    elif not maintenance_start_failed:
                        event_data = {
                            "host": maintenance_server.host,
                            "port": maintenance_server.port,
                            "reason": "port_unavailable_or_bind_failed",
                        }
                        log_event("maintenance_placeholder_failed", event_data)
                        events.append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "type": "maintenance_placeholder_failed",
                            "details": event_data,
                        })
                        maintenance_start_failed = True
                
                # Log events on state changes
                if last_health_ok is not None:
                    if not health_ok and last_health_ok:
                        event_data = {"method": "http"}
                        log_event("backend_unreachable", event_data)
                        events.append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "type": "backend_unreachable",
                            "details": event_data,
                        })
                        if sio and sio.connected:
                            try:
                                sio.emit("monitor_event", {
                                    "type": "backend_unreachable",
                                    "details": event_data,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }, to=MONITOR_ROOM)
                            except Exception:
                                pass
                    
                    elif health_ok and not last_health_ok:
                        event_data = {"method": "http"}
                        log_event("backend_reachable", event_data)
                        events.append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "type": "backend_reachable",
                            "details": event_data,
                        })
                        if sio and sio.connected:
                            try:
                                sio.emit("monitor_event", {
                                    "type": "backend_reachable",
                                    "details": event_data,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }, to=MONITOR_ROOM)
                            except Exception:
                                pass
                
                if last_process_ok is not None:
                    if not process_ok and last_process_ok:
                        event_data = {"pattern": PROCESS_CMD_PATTERN}
                        log_event("backend_process_missing", event_data)
                        events.append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "type": "backend_process_missing",
                            "details": event_data,
                        })
                        if sio and sio.connected:
                            try:
                                sio.emit("monitor_event", {
                                    "type": "backend_process_missing",
                                    "details": event_data,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }, to=MONITOR_ROOM)
                            except Exception:
                                pass
                    
                    elif process_ok and not last_process_ok:
                        event_data = {"pattern": PROCESS_CMD_PATTERN}
                        log_event("backend_process_found", event_data)
                        events.append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "type": "backend_process_found",
                            "details": event_data,
                        })
                        if sio and sio.connected:
                            try:
                                sio.emit("monitor_event", {
                                    "type": "backend_process_found",
                                    "details": event_data,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }, to=MONITOR_ROOM)
                            except Exception:
                                pass
                
                # Keep only recent events in memory
                if len(events) > 180:
                    events = events[-180:]
                
                last_health_ok = health_ok
                last_process_ok = process_ok
                
                # Load visits summary
                visits_summary = get_visits_summary()
                
                # Update display
                layout = create_layout(health_ok, process_ok, events, visits_summary)
                live.update(layout)
                
                time.sleep(MONITOR_LOOP_SLEEP)
    
    except KeyboardInterrupt:
        maintenance_server.stop()
        console.print("\n[bold yellow]👋 Monitor detenido por el usuario[/bold yellow]")
    except Exception as e:
        maintenance_server.stop()
        console.print(f"\n[bold red]💥 Monitor falló: {e}[/bold red]")
        logger.exception("Monitor crashed")
        sys.exit(1)


if __name__ == "__main__":
    main()
