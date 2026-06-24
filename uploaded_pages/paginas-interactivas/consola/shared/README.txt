Consola shared folder
=====================

This directory is exposed to the web console as /.

The browser console can only read files from here. To change what appears in
the console, connect to the server with SSH and create, edit, move, or remove
files in this directory.

Example:
  cd /srv/http/persrepo/uploaded_pages/paginas-interactivas/consola/shared
  echo "hola desde ssh" > mensaje.txt
