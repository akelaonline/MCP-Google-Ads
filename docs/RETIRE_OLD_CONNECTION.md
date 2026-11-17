# Retirar una conexión anterior de Claude Desktop

Este procedimiento retira un registro MCP local. No desinstala Python ni elimina
archivos. Usalo una vez comprobado el perfil nuevo y terminadas las tareas de la
conexión anterior.

## 1. Identificar qué conservar

El nombre del servidor es una etiqueta, no una versión del código.
En una migración típica:

| Entrada | Acción |
|---|---|
| `google-ads-editor`, nuevo editor ya verificado | Conservar |
| `google-ads`, entrada anterior identificada como reemplazada | Retirar de Claude |
| Complemento de ChatGPT por túnel, en su perfil de lectura | Conservar; es independiente del registro de Claude |

No elimines una entrada solo porque se llama `google-ads`: comprobá primero su
Command y Arguments, qué perfil abre y si otras tareas todavía la usan.

## 2. Respaldar la configuración local

El archivo en macOS es:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Cuando terminen las tareas abiertas, cerrá Claude Desktop con Cmd-Q.
Creá una copia privada del JSON. Este ejemplo usa solo la biblioteca estándar
de Python; adaptá `python3` si tu instalación usa un ejecutable absoluto:

```bash
python3 - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import os

config = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
if config.is_symlink() or not config.is_file():
    raise SystemExit("Se esperaba un archivo de configuración regular; no se cambió nada.")
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
backup = config.with_name(config.name + ".bak-retire-" + stamp)
fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "wb") as stream:
    stream.write(config.read_bytes())
print("Respaldo privado creado. No se mostraron credenciales.")
PY
```

No publiques el JSON ni su copia: otras conexiones pueden contener secretos.

## 3. Retirar únicamente la entrada vieja

Volvé a abrir Claude Desktop y entrá a:

**Settings → Desktop app → Extensions → Manage → Local MCP servers**

En la interfaz que muestra la lista a la izquierda y Command/Arguments a la derecha:

1. Seleccioná la entrada anterior, por ejemplo `google-ads`.
2. Comprobá que no seleccionaste `google-ads-editor`.
3. Usá el icono de papelera del panel derecho y confirmá la eliminación de esa entrada.
4. Cerrá Claude con Cmd-Q y volvé a abrirlo.

En versiones con otra interfaz, usá Edit config y quitá únicamente el miembro
correspondiente dentro de `mcpServers`. Conservá todas las demás entradas y
preferencias; no reemplaces el JSON completo por un ejemplo de instalación.

Si necesitás restaurar, cerrá Claude y compará la copia con el JSON actual.
Reinsertá la entrada retirada sin sobrescribir otras conexiones agregadas después.

## 4. Validación posterior

En una conversación nueva, seleccioná únicamente el editor y pedí:

> Usá google-ads-editor para consultar el resumen de una cuenta permitida.
> No propongas ni confirmes modificaciones.

Comprobá también que ChatGPT conserva su consulta de lectura por túnel.
Una consulta correcta es suficiente: no hagas una edición de prueba para validar
una limpieza de configuración.

## 5. Archivos y dependencias

Retirar la entrada vieja no exige borrar ninguna carpeta. Antes de desinstalar
archivos, revisá Command y Arguments de los perfiles que conservás, los scripts de
inicio y cualquier instalación editable que apunte al checkout anterior.

En el montaje de laboratorio que originó esta guía, el editor usa el Python de
`~/.google_ads_mcp_lab/venv/bin/python` aunque su lanzador y estado estén en
`~/.google_ads_mcp_operator/`. Borrar el laboratorio rompería el editor y el túnel
de lectura. Las instrucciones de instalación nueva usan otras rutas; no renombres
ni migres perfiles funcionales solo para hacerlos coincidir con los ejemplos.

Conservá bases de auditoría, claves de pendientes y respaldos privados hasta
revisar su retención. No revoques el OAuth compartido para retirar una entrada:
eso puede interrumpir los perfiles que lo siguen usando.
