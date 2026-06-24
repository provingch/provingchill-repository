# Portal de presentación con Flask

Landing personal en modo solo lectura: detecta proyectos que ya cargaste en el servidor y los publica.

## Ejecutar

1. Crear entorno virtual (opcional):
   - `python -m venv .venv`
   - `source .venv/bin/activate`
2. Instalar dependencias:
   - `pip install -r requirements.txt`
3. Iniciar servidor:
   - ```bash
     FLASK_SECRET_KEY="nigahahhaghaghahahghagha" \
     SESSION_COOKIE_SECURE=0 \
     TEMPLATES_AUTO_RELOAD=1 \
     python app.py
     ```
4. Abrir:
   - `http://localhost:8080`

## Cuentas y chat

- El acceso usa una base SQLite local en `data/auth.db`.
- Cualquier persona puede registrarse desde la web.
- La cuenta `provingggg` queda con rol `owner`; las demás se guardan como `user`.
- El mini chat solo se muestra y funciona para sesiones autenticadas.
- La contrasena se guarda con hash, no en texto plano.
- En desarrollo local usa `SESSION_COOKIE_SECURE=0`.
- En produccion con HTTPS usa `SESSION_COOKIE_SECURE=1`.

### Administrar usuarios

- Crear usuario:
  - `python app.py create-user <usuario>`
- Ver usuarios cargados:
  - `python app.py list-users`
- Cambiar contrasena:
  - `python app.py set-password <usuario>`
- Eliminar usuario:
  - `python app.py delete-user <usuario>`

Al crear o cambiar contrasena, el comando la pide por terminal para no dejarla escrita en el historial del shell.

## Publicar proyectos (desde servidor)

- No hay subida desde la web.
- Cada proyecto debe estar en su propia carpeta dentro de `uploaded_pages/`.
- Ahora puedes separarlos por categoria usando estas carpetas contenedoras:
  - `uploaded_pages/paginas-musicales/`
  - `uploaded_pages/paginas-interactivas/`
- Estructura mínima:
  - `uploaded_pages/paginas-musicales/mi-proyecto/index.html`
- Puedes incluir assets libremente:
  - `uploaded_pages/paginas-musicales/mi-proyecto/css/...`
  - `uploaded_pages/paginas-musicales/mi-proyecto/js/...`
  - `uploaded_pages/paginas-musicales/mi-proyecto/media/...`
- Changelog opcional por proyecto:
  - `uploaded_pages/paginas-musicales/mi-proyecto/changelog.json`
  - `uploaded_pages/paginas-musicales/mi-proyecto/CHANGELOG.md`
  - `uploaded_pages/paginas-musicales/mi-proyecto/version.txt`
- Compatibilidad:
  - `uploaded_pages/mi-proyecto/index.html` sigue funcionando como ruta legacy y se muestra como pagina musical.

## Qué hace

- Home de presentación en `templates/index.html`.
- Apartado flotante de registro/login en `templates/index.html` con sesion Flask.
- Likes por proyecto para destacar paginas.
- Changelog publico por proyecto en ruta separada.
- Monitor publico en modo lectura y comandos solo para owner.
- `monitor.py` puede levantar un placeholder temporal de mantenimiento con el estilo del sitio cuando el backend cae por completo y el puerto queda libre.
- Si `TEMPLATES_AUTO_RELOAD=1`, los cambios en `templates/*.html` se reflejan sin reiniciar.
- Registra visitas en `analytics/visits.jsonl` con origen (`instagram`, `discord`, `link`, `direct`).
- Las visitas `internal` (navegación dentro del mismo dominio) se ignoran y no cuentan en estadísticas.
- Emite actualizaciones de visitas y chat en tiempo real por Socket.IO (`visits:update`, `chat:update`) cuando `python-socketio` está instalado.
- Expone `GET /api/auth/session` para saber si hay una sesion activa.
- Lista proyectos detectados en `uploaded_pages/`, incluyendo subcarpetas de categorias.
- API:
  - `GET /api/pages`: lista carpetas que tengan `index.html`, incluyendo likes, vistas, version y changelog.
  - `GET /api/visits`: total de vistas de proyectos y conteo por origen.
  - `POST /api/pages/<slug>/like`: agrega like del usuario autenticado.
  - `DELETE /api/pages/<slug>/like`: quita like del usuario autenticado.
  - `GET /api/monitor/events`: muestra eventos del monitor en lectura publica.
  - `GET /api/chat/messages`: devuelve los ultimos mensajes para la sesion autenticada.
  - `POST /api/chat/messages`: publica un mensaje como el usuario autenticado.
- Rutas públicas:
  - `/pages/<nombre-carpeta>/` (carga su `index.html`)
  - `/pages/<nombre-carpeta>/<asset>` (sirve archivos internos)
  - `/projects/<nombre-carpeta>/changelog` (muestra el changelog/version del proyecto)
  - `/monitor` (monitor publico de backend y trafico)

## Medir origen recomendado

- Enlaces desde Instagram:
  - `https://tu-dominio.com/?utm_source=instagram`
- Enlaces desde Discord:
  - `https://tu-dominio.com/?utm_source=discord`
- Enlaces desde WhatsApp:
  - `https://tu-dominio.com/?utm_source=whatsapp`
- Enlaces genéricos:
  - `https://tu-dominio.com/?utm_source=link`

Tambien acepta `source`, `via`, `platform` y `ref_source` como alias de `utm_source`.
Si el navegador no manda `Referer`, intenta inferir el origen con `X-Requested-With`, `User-Agent` y `Sec-Fetch-Site`.

## Tiempo real (Socket.IO)

- Evento emitido por backend: `visits:update`
- Payload: incluye `stats` (mismo shape que `/api/visits`) y `event` con la visita reciente.
- Evento emitido por backend: `chat:update`
- Payload: incluye `messages` al conectar o `message` cuando entra uno nuevo.
- Si falta `python-socketio`, la app sigue funcionando y solo tendrás actualización manual.

## Fallback de mantenimiento

- Si `monitor.py` detecta que el backend dejó de responder y el proceso ya no existe, intenta servir una pantalla temporal de mantenimiento en el mismo puerto.
- La pantalla usa el look principal del portal, se refresca sola y avisa que la página volverá después del mantenimiento.
- Cuando el monitor detecta que el proceso principal reaparece o el backend vuelve a responder, suelta el puerto y apaga el placeholder.
- Es un mecanismo `best effort`: si otro proceso sigue ocupando el puerto aunque el backend esté caído, el placeholder no podrá entrar.

## Estructura

- `app.py`: backend Flask.
- `app.py` usa `waitress` cuando está instalada (modo producción).
- `templates/`: HTML del home.
- `static/`: CSS y JS del frontend.
- `uploaded_pages/`: proyectos estaticos por carpeta y por categoria.
