from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
import fnmatch
import mimetypes
import os
import platform
import shutil

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_shared_root()
    yield


app = FastAPI(title="Consola Backend", version="3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SHARED_ROOT = (BASE_DIR.parent / "shared").resolve()
SHARED_ROOT = Path(os.getenv("CONSOLA_SHARED_ROOT", DEFAULT_SHARED_ROOT)).expanduser().resolve()
MAX_READ_BYTES = int(os.getenv("CONSOLA_MAX_READ_BYTES", str(512 * 1024)))

MUTATING_COMMANDS = {
    "touch",
    "rm",
    "rmdir",
    "mkdir",
    "cp",
    "mv",
    "nano",
    "vim",
    "vi",
    "ed",
    "sed",
    "tee",
    "chmod",
    "chown",
    "ln",
    "dd",
}


class CommandRequest(BaseModel):
    command: str
    args: list[str] = []
    cwd: str = "/"
    raw: str = ""


def ensure_shared_root() -> None:
    SHARED_ROOT.mkdir(parents=True, exist_ok=True)


def get_commands() -> dict[str, dict[str, list[str] | str]]:
    return {
        "help": {"description": "Mostrar comandos", "args": []},
        "ls": {"description": "Listar archivos", "args": ["-la", "ruta"]},
        "pwd": {"description": "Directorio actual", "args": []},
        "cd": {"description": "Cambiar directorio", "args": ["ruta"]},
        "cat": {"description": "Leer archivo de texto", "args": ["archivo"]},
        "head": {"description": "Primeras lineas de un archivo", "args": ["-n", "archivo"]},
        "tail": {"description": "Ultimas lineas de un archivo", "args": ["-n", "archivo"]},
        "grep": {"description": "Buscar texto en archivos", "args": ["patron", "archivo"]},
        "find": {"description": "Buscar por nombre", "args": ["ruta", "patron"]},
        "tree": {"description": "Ver arbol de directorios", "args": ["ruta"]},
        "stat": {"description": "Ver metadatos", "args": ["ruta"]},
        "file": {"description": "Detectar tipo de archivo", "args": ["archivo"]},
        "df": {"description": "Uso del disco real", "args": []},
        "clear": {"description": "Limpiar consola", "args": []},
        "whoami": {"description": "Usuario de lectura", "args": []},
        "date": {"description": "Fecha y hora", "args": []},
        "neofetch": {"description": "Info del sistema", "args": []},
        "cmatrix": {"description": "Efecto Matrix", "args": []},
    }


def normalize_virtual_path(path: str, cwd: str = "/") -> str:
    path = path or "."
    if path == "~":
        path = "/"

    base = PurePosixPath("/") if path.startswith("/") else PurePosixPath(cwd or "/")
    candidate = PurePosixPath(path) if path.startswith("/") else base / path
    parts: list[str] = []

    for part in candidate.parts:
        if part in {"", "/"}:
            continue
        if part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)

    return "/" + "/".join(parts) if parts else "/"


def real_path(virtual_path: str, cwd: str = "/") -> tuple[str, Path]:
    normalized = normalize_virtual_path(virtual_path, cwd)
    relative = normalized.lstrip("/")
    resolved = (SHARED_ROOT / relative).resolve()

    try:
        common_path = os.path.commonpath([str(SHARED_ROOT), str(resolved)])
    except ValueError:
        raise PermissionError("ruta fuera de la carpeta compartida")

    if common_path != str(SHARED_ROOT):
        raise PermissionError("ruta fuera de la carpeta compartida")

    return normalized, resolved


def display_path(path: Path) -> str:
    rel = path.resolve().relative_to(SHARED_ROOT)
    return "/" + rel.as_posix() if rel.as_posix() != "." else "/"


def format_size(size: int) -> str:
    units = ["B", "K", "M", "G", "T"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{size}B"


def is_probably_binary(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            chunk = file.read(2048)
    except OSError:
        return False
    return b"\0" in chunk


def read_text_file(path: Path) -> tuple[str, bool]:
    data = path.read_bytes()
    truncated = len(data) > MAX_READ_BYTES
    data = data[:MAX_READ_BYTES]
    text = data.decode("utf-8", errors="replace")
    return text, truncated


def parse_count_args(args: list[str], default: int = 10) -> tuple[int, list[str]]:
    if len(args) >= 2 and args[0] == "-n":
        try:
            return max(1, min(500, int(args[1]))), args[2:]
        except ValueError:
            return default, args[2:]
    return default, args


def command_read_only_message(command: str) -> str:
    return (
        f"{command}: permiso denegado: esta consola es de solo lectura\n"
        "Los archivos se modifican desde SSH en la carpeta intermediaria del servidor."
    )


def list_directory(path: Path, show_all: bool, long_format: bool) -> str:
    entries = sorted(
        [entry for entry in path.iterdir() if show_all or not entry.name.startswith(".")],
        key=lambda item: (not item.is_dir(), item.name.lower()),
    )
    lines = []
    for entry in entries:
        suffix = "/" if entry.is_dir() else ""
        if long_format:
            stat = entry.stat()
            kind = "d" if entry.is_dir() else "-"
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            lines.append(f"{kind}r--r--r-- {format_size(stat.st_size):>8} {modified} {entry.name}{suffix}")
        else:
            lines.append(f"{entry.name}{suffix}")
    return "\n".join(lines)


def find_entries(start: Path, pattern: str) -> str:
    matches = []
    for entry in start.rglob("*"):
        if len(matches) >= 300:
            matches.append("[resultado truncado]")
            break
        if fnmatch.fnmatch(entry.name.lower(), pattern.lower()) or pattern.lower() in entry.name.lower():
            matches.append(display_path(entry) + ("/" if entry.is_dir() else ""))
    return "\n".join(matches)


def tree_output(start: Path, max_depth: int = 3) -> str:
    lines = [display_path(start)]

    def walk(path: Path, prefix: str, depth: int) -> None:
        if depth >= max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        for index, entry in enumerate(entries[:80]):
            connector = "`-- " if index == len(entries[:80]) - 1 else "|-- "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = "    " if connector == "`-- " else "|   "
                walk(entry, prefix + extension, depth + 1)
        if len(entries) > 80:
            lines.append(f"{prefix}`-- [truncado]")

    if start.is_dir():
        walk(start, "", 0)
    return "\n".join(lines)


@app.get("/commands")
async def list_commands():
    return {"commands": get_commands(), "root": str(SHARED_ROOT)}


@app.get("/status")
async def status():
    ensure_shared_root()
    return {
        "ok": True,
        "mode": "read-only",
        "root": str(SHARED_ROOT),
        "max_read_bytes": MAX_READ_BYTES,
    }


@app.post("/execute")
async def execute_command(request: CommandRequest):
    ensure_shared_root()
    command = request.command.lower().strip()
    args = [str(arg) for arg in request.args]
    cwd = normalize_virtual_path(request.cwd or "/")
    new_cwd = cwd

    try:
        if not command:
            return {"output": "", "cwd": new_cwd}

        if command in MUTATING_COMMANDS:
            return {"output": command_read_only_message(command), "cwd": new_cwd}

        if request.raw and any(token in request.raw for token in [">", ">>"]):
            return {"output": command_read_only_message(command), "cwd": new_cwd}

        if command == "help":
            output = [
                "Consola conectada a carpeta real (modo solo lectura).",
                f"Raiz visible: /  ->  {SHARED_ROOT}",
                "",
                "Comandos disponibles:",
            ]
            for cmd, info in get_commands().items():
                args_str = " ".join([f"[{arg}]" for arg in info["args"]])
                output.append(f"  {cmd:<10} {args_str:<18} {info['description']}")
            output.append("")
            output.append("Bloqueado: touch, mkdir, rm, mv, cp, nano, chmod y redirecciones.")
            return {"output": "\n".join(output), "cwd": new_cwd}

        if command == "pwd":
            return {"output": cwd, "cwd": new_cwd}

        if command == "cd":
            target = args[0] if args else "/"
            virtual, path = real_path(target, cwd)
            if not path.exists():
                return {"output": f"cd: {virtual}: No such file or directory", "cwd": new_cwd}
            if not path.is_dir():
                return {"output": f"cd: {virtual}: Not a directory", "cwd": new_cwd}
            return {"output": "", "cwd": virtual}

        if command == "ls":
            show_all = any(arg in {"-a", "-la", "-al"} for arg in args)
            long_format = any(arg in {"-l", "-la", "-al"} for arg in args)
            path_args = [arg for arg in args if not arg.startswith("-")]
            target = path_args[0] if path_args else "."
            virtual, path = real_path(target, cwd)
            if not path.exists():
                return {"output": f"ls: cannot access '{virtual}': No such file or directory", "cwd": new_cwd}
            if path.is_file():
                return {"output": path.name, "cwd": new_cwd}
            return {"output": list_directory(path, show_all, long_format), "cwd": new_cwd}

        if command == "cat":
            if not args:
                return {"output": "cat: missing file operand", "cwd": new_cwd}
            virtual, path = real_path(args[0], cwd)
            if not path.exists() or not path.is_file():
                return {"output": f"cat: {virtual}: No such file", "cwd": new_cwd}
            if is_probably_binary(path):
                return {"output": f"cat: {virtual}: binary file", "cwd": new_cwd}
            text, truncated = read_text_file(path)
            if truncated:
                text += f"\n[truncado a {format_size(MAX_READ_BYTES)}]"
            return {"output": text, "cwd": new_cwd}

        if command in {"head", "tail"}:
            count, remaining = parse_count_args(args)
            if not remaining:
                return {"output": f"{command}: missing file operand", "cwd": new_cwd}
            virtual, path = real_path(remaining[0], cwd)
            if not path.exists() or not path.is_file():
                return {"output": f"{command}: {virtual}: No such file", "cwd": new_cwd}
            if is_probably_binary(path):
                return {"output": f"{command}: {virtual}: binary file", "cwd": new_cwd}
            text, _ = read_text_file(path)
            lines = text.splitlines()
            selected = lines[:count] if command == "head" else lines[-count:]
            return {"output": "\n".join(selected), "cwd": new_cwd}

        if command == "grep":
            if len(args) < 2:
                return {"output": "grep: usage: grep <patron> <archivo>", "cwd": new_cwd}
            pattern = args[0].lower()
            virtual, path = real_path(args[1], cwd)
            if not path.exists() or not path.is_file():
                return {"output": f"grep: {virtual}: No such file", "cwd": new_cwd}
            if is_probably_binary(path):
                return {"output": f"grep: {virtual}: binary file", "cwd": new_cwd}
            text, _ = read_text_file(path)
            matches = [
                f"{index}: {line}"
                for index, line in enumerate(text.splitlines(), 1)
                if pattern in line.lower()
            ]
            return {"output": "\n".join(matches), "cwd": new_cwd}

        if command == "find":
            if not args:
                start_arg = "."
                pattern = "*"
            elif len(args) == 1:
                start_arg = "."
                pattern = args[0]
            else:
                start_arg = args[0]
                pattern = args[1]
            virtual, path = real_path(start_arg, cwd)
            if not path.exists() or not path.is_dir():
                return {"output": f"find: {virtual}: No such directory", "cwd": new_cwd}
            return {"output": find_entries(path, pattern), "cwd": new_cwd}

        if command == "tree":
            target = args[0] if args else "."
            virtual, path = real_path(target, cwd)
            if not path.exists():
                return {"output": f"tree: {virtual}: No such file or directory", "cwd": new_cwd}
            return {"output": tree_output(path), "cwd": new_cwd}

        if command == "stat":
            if not args:
                return {"output": "stat: missing operand", "cwd": new_cwd}
            virtual, path = real_path(args[0], cwd)
            if not path.exists():
                return {"output": f"stat: cannot stat '{virtual}': No such file or directory", "cwd": new_cwd}
            stat = path.stat()
            output = [
                f"File: {virtual}",
                f"Size: {stat.st_size} bytes",
                f"Type: {'directory' if path.is_dir() else 'file'}",
                f"Modified: {datetime.fromtimestamp(stat.st_mtime).isoformat(sep=' ', timespec='seconds')}",
                "Access: read-only",
            ]
            return {"output": "\n".join(output), "cwd": new_cwd}

        if command == "file":
            if not args:
                return {"output": "file: missing operand", "cwd": new_cwd}
            virtual, path = real_path(args[0], cwd)
            if not path.exists():
                return {"output": f"file: cannot open '{virtual}'", "cwd": new_cwd}
            if path.is_dir():
                kind = "directory"
            else:
                kind = mimetypes.guess_type(path.name)[0] or ("binary data" if is_probably_binary(path) else "text/plain")
            return {"output": f"{virtual}: {kind}", "cwd": new_cwd}

        if command == "df":
            usage = shutil.disk_usage(SHARED_ROOT)
            used_percent = (usage.used / usage.total) * 100 if usage.total else 0
            output = "Filesystem        Size     Used    Avail Use% Mounted on\n"
            output += (
                f"consola-shared {format_size(usage.total):>8} "
                f"{format_size(usage.used):>8} {format_size(usage.free):>8} "
                f"{used_percent:>4.1f}% /"
            )
            return {"output": output, "cwd": new_cwd}

        if command == "clear":
            return {"clear": True, "cwd": new_cwd}

        if command == "whoami":
            return {"output": "consola-reader", "cwd": new_cwd}

        if command == "date":
            return {"output": datetime.now().astimezone().strftime("%a %b %d %H:%M:%S %Z %Y"), "cwd": new_cwd}

        if command == "cmatrix":
            return {"output": "[Matrix effect - Ctrl+C para salir]", "cwd": new_cwd, "cmatrix": True}

        if command == "neofetch":
            output = f"""
      ______          consola-reader@console
     / ____/___       OS: {platform.system()} read-only console
    / /   / __ \\      Root: {SHARED_ROOT}
   / /___/ /_/ /      Shell: zsh-like web terminal
   \\____/\\____/       Mode: read-only
                      Python: {platform.python_version()}
            """
            return {"output": output.strip(), "cwd": new_cwd}

        return {"output": f"Command not found: {command}", "cwd": new_cwd}

    except PermissionError as error:
        return {"output": f"permission denied: {error}", "cwd": new_cwd}
    except OSError as error:
        return {"output": f"io error: {error}", "cwd": new_cwd}
    except Exception as error:
        return {"output": f"Error: {error}", "cwd": new_cwd}


@app.get("/")
async def root():
    return {
        "message": "Consola Backend",
        "version": "3.0",
        "mode": "read-only",
        "root": str(SHARED_ROOT),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("CONSOLA_BACKEND_PORT", "8000")))
