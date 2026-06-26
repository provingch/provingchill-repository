# Portal de presentación con Flask

Landing personal en modo solo lectura: detecta proyectos estáticos en el servidor y los publica con analytics básicos de visitas.

## Ejecutar

1. Crear entorno virtual (opcional):
   - `python -m venv venv`
   - `source venv/bin/activate`
2. Instalar dependencias:
   - `pip install -r requirements.txt`
3. Iniciar servidor:
   - ```bash
     FLASK_SECRET_KEY="cambia-esto" \
     TEMPLATES_AUTO_RELOAD=1 \
     python app.py
     ```
4. Abrir:
   - `http://localhost:8080`

Por defecto usa `waitress` si está instalada. Variables útiles:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Host de escucha |
| `PORT` | `8080` | Puerto |
| `FLASK_SECRET_KEY` | valor de desarrollo | Clave de sesión Flask |
| `TEMPLATES_AUTO_RELOAD` | `1` | Recarga plantillas sin reiniciar |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
| `APP_TIMEZONE` | `America/Asuncion` | Zona horaria para analytics |
| `REPO_PAGES_ROOT` | `~/repopages` | Raíz de proyectos externos |
| `PAGES_MUSICAL_DIR` | `~/repopages/paginas_musicales` | Proyectos musicales |
| `PAGES_INTERACTIVE_DIR` | `~/repopages/paginas_interactivas` | Proyectos interactivos |

## Publicar proyectos

- No hay subida desde la web.
- Los proyectos viven **fuera del repositorio**, en carpetas externas del servidor.
- Cada proyecto debe estar en su propia carpeta con un `index.html`.
- Separación por categoría:
  - `~/repopages/paginas_musicales/mi-proyecto/index.html`
  - `~/repopages/paginas_interactivas/mi-juego/index.html`
- Assets libres dentro de cada carpeta:
  - `css/`, `js/`, `media/`, etc.
- Changelog opcional por proyecto:
  - `changelog.json` o `CHANGELOG.md`
  - `version.txt`

El backend no crea esas carpetas: las preparás vos en el servidor y reiniciás la app si hace falta.

## Qué hace

- Home de presentación en `/`.
- Catálogo de proyectos en `/projects`.
- Publicación estática por carpeta en `/pages/<slug>/`.
- Changelog público por proyecto en `/projects/<slug>/changelog`.
- Registro de visitas en `analytics/visits.jsonl` con datos mínimos: fecha, hora, tipo de dispositivo y página visitada.
- No se guardan referrer, IP, user-agent completo ni parámetros UTM.
- Detección de favicon y color dominante por proyecto (requiere `Pillow`).

## API y rutas

- `GET /` — home
- `GET /projects` — listado de proyectos
- `GET /pages/<slug>/` — proyecto estático
- `GET /pages/<slug>/<asset>` — assets del proyecto
- `GET /projects/<slug>/changelog` — changelog del proyecto
- `GET /media/<archivo>` — media del portal
- `GET /api/pages` — proyectos detectados (slug, categoría, versión, favicon, visitas)
- `GET /api/visits` — resumen agregado de visitas (totales, dispositivos, proyectos)
- `GET /health` — healthcheck

## Analytics

Cada visita guarda solo:

```json
{
  "date": "2026-06-26",
  "time": "20:43:17",
  "device": "desktop",
  "page": "/pages/mi-proyecto/"
}
```

`device` puede ser `desktop`, `mobile`, `tablet` o `desconocido`. El campo `page` se usa solo para contar vistas por proyecto; no identifica a la persona.

## Estructura del repo

- `app.py` — backend Flask
- `templates/` — HTML del portal
- `static/` — CSS y JS del frontend
- `media/` — favicon y assets del sitio
- `analytics/` — logs de visitas
- `~/repopages/` — proyectos publicados (fuera del repo)

## Changelog del proyecto

Ver [CHANGELOG.md](./CHANGELOG.md).

## Licencia

[CC BY-NC 4.0](./LICENSE)
