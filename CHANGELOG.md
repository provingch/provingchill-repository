# Changelog

Todos los cambios relevantes de este repositorio se documentan acá.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa versionado aproximado por releases.

## [4.0.1] - 2026-06-26

### Changed

- Analytics más privado: cada visita guarda solo fecha, hora, tipo de dispositivo y página visitada.
- Ya no se persisten referrer, user-agent completo, UTM ni dominios de origen.
- `/api/visits` devuelve totales por dispositivo en lugar de orígenes o referrers.
- Versión del portal visible en la barra de navegación (`v4.0.1`).
- `analytics/*.jsonl` ignorado en git para no subir logs de visitas al repositorio.

### Fixed

- Primer patch post-4.0: se eliminó la exposición de datos de navegación que quedaban en el log de visitas.

## [4.0.0] - 2026-06-26

### Changed

- Los proyectos publicados se leen desde carpetas externas en `~/repopages/` en lugar de `uploaded_pages/` dentro del repo.
- Categorías separadas en:
  - `~/repopages/paginas_musicales`
  - `~/repopages/paginas_interactivas`
- Rutas configurables con `REPO_PAGES_ROOT`, `PAGES_MUSICAL_DIR` y `PAGES_INTERACTIVE_DIR`.
- README actualizado para reflejar el estado actual del portal.

### Removed

- Contenido de proyectos del repositorio (`uploaded_pages/`), movido fuera del repo.
- Funcionalidades retiradas del backend principal: cuentas, chat, likes, monitor y Socket.IO.

### Added

- `CHANGELOG.md` del repositorio.
- `venv/`, `env/` y `.Trash-1000/` al `.gitignore`.

## [3.0.0] - 2025

### Added

- Portal Flask con detección automática de proyectos estáticos.
- Analytics de visitas con origen (`utm_source`, referrer, user-agent).
- Changelog público por proyecto.
- Publicación por carpetas y categorías (`paginas-musicales`, `paginas-interactivas`).
- Licencia CC BY-NC 4.0.

## [2.x] - Anterior

Versiones previas con evolución del portal y subida de archivos. No hay notas detalladas conservadas en git.
