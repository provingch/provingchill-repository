# Consola

Consola web estilo Linux conectada a una carpeta real del servidor en modo solo lectura.

La idea es usar SSH para controlar los archivos de una carpeta intermediaria, mientras que la consola del navegador solo puede explorarlos y leerlos.

## Carpeta intermediaria

Por defecto, la consola expone esta carpeta como `/`:

```bash
/srv/http/persrepo/uploaded_pages/paginas-interactivas/consola/shared
```

Puedes cambiarla al iniciar el backend:

```bash
CONSOLA_SHARED_ROOT=/ruta/que/controlas/por/ssh python backend/main.py
```

La consola bloquea operaciones de escritura como `touch`, `mkdir`, `rm`, `mv`, `cp`, `nano`, `chmod` y redirecciones.

## Instalar dependencias

Desde el venv del repo:

```bash
cd /srv/http/persrepo
source venv/bin/activate
python -m pip install -r uploaded_pages/paginas-interactivas/consola/backend/requirements.txt
```

## Iniciar backend

```bash
cd /srv/http/persrepo/uploaded_pages/paginas-interactivas/consola
/srv/http/persrepo/venv/bin/python backend/main.py
```

El backend escucha en:

```bash
http://localhost:8000
```

Si necesitas otro puerto:

```bash
CONSOLA_BACKEND_PORT=8010 /srv/http/persrepo/venv/bin/python backend/main.py
```

## Abrir frontend

En el sitio principal:

```text
/pages/paginas-interactivas/consola/
```

Si el backend está en otro host o puerto, abre el frontend con:

```text
/pages/paginas-interactivas/consola/?api=http://TU_HOST:8000
```

## Comandos disponibles

| Comando | Descripción |
| --- | --- |
| `help` | Mostrar ayuda |
| `ls`, `ls -la` | Listar archivos |
| `pwd` | Ver ruta actual |
| `cd` | Cambiar directorio dentro de la carpeta compartida |
| `cat` | Leer archivo de texto |
| `head`, `tail` | Leer primeras o últimas líneas |
| `grep` | Buscar texto dentro de un archivo |
| `find` | Buscar archivos por nombre |
| `tree` | Ver árbol de directorios |
| `stat` | Ver metadatos |
| `file` | Detectar tipo aproximado |
| `df` | Ver uso del disco real |
| `date`, `whoami`, `neofetch` | Info del entorno |
| `clear`, `cmatrix` | Utilidades visuales |

## Seguridad

El backend resuelve todas las rutas contra `CONSOLA_SHARED_ROOT` y rechaza escapes con `..`. El navegador no ejecuta comandos del sistema: solo llama a endpoints que implementan comandos permitidos de lectura.
