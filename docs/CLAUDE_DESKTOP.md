# Claude Desktop: lectura y edición local

Empezá por [la instalación común](INSTALL_CLIENTS.md).
Necesitás **la aplicación Claude Desktop**. La configuración JSON local
no aparece automáticamente en `claude.ai` dentro de un navegador.

## 1. Preparar un perfil propio

Si ChatGPT usa `chatgpt-readonly`, Claude debe usar otro perfil:
[crear el perfil editor](EDITING_CAMPAIGNS.md#crear-un-perfil-editor).
Conservá todas las autoaprobaciones apagadas.
Para un segundo perfil de lectura, mantené READ_ONLY=true y usá igualmente otra base y clave.

No hace falta crear un túnel OpenAI ni una clave OpenAI para el stdio de Claude.

## 2. Agregar el servidor

Abrí Claude Desktop al menos una vez. En macOS, el archivo es:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Si ya existe, hacé una copia privada antes de editarlo. Agregá la entrada dentro
de `mcpServers`, conservando las entradas y preferencias que ya tenías.
Reemplazá `TU_USUARIO` por el usuario real del Mac; no uses `~` en el JSON.

```json
{
  "mcpServers": {
    "google-ads-editor": {
      "command": "/Users/TU_USUARIO/.google_ads_mcp_profiles/venv/bin/python",
      "args": [
        "/Users/TU_USUARIO/.google_ads_mcp_profiles/code/scripts/run_profile.py",
        "--env",
        "/Users/TU_USUARIO/.google_ads_mcp_profiles/claude-editor/ads.env",
        "--mode",
        "editor"
      ]
    }
  }
}
```

El JSON solo contiene rutas y el modo requerido; las credenciales quedan en el env privado.
El lanzador elimina variables Google Ads heredadas, valida el modo y apaga el acceso si la política no coincide.
Claude puede abrir procesos distintos para Chat y Cowork/Code. El primero conserva la base principal;
los adicionales reciben bases y claves privadas en `instances/`.
Las propuestas deben confirmarse en la conexión que las originó.
Después de reiniciar una instancia adicional, su historial queda conservado, pero no se recupera automáticamente en otra conexión:
revisá y prepará una nueva propuesta; no cambies rutas para intentar confirmar una antigua.

Cuando terminen las tareas abiertas, cerrá Claude Desktop con **Cmd-Q**
y volvé a abrirlo. Abrí una conversación nueva.
Podés hacerlo dentro del mismo proyecto de campañas que ya utilizás.

## 3. Verificar dónde apareció

Desde el cuadro de chat: **+ → Connectors/Conectores**. Habilitá
`google-ads-editor` y evitá seleccionar otra conexión Ads en esa conversación.

Según la versión, el estado y los logs locales están en:

- **Settings → Desktop app → Manage junto a Extensions → Local MCP servers**;
- o **Settings → Developer → This computer** en la interfaz anterior.

Si el modelo dice que no tiene herramientas, revisá esa pantalla.
El modelo solo puede usar herramientas realmente expuestas a esa sesión;
mencionar un nombre en el prompt no conecta un servidor.

## 4. Primera prueba: solo una consulta

> Usá únicamente las herramientas del servidor local google-ads-editor.
> Consultá la jerarquía del MCC y el resumen de una cuenta permitida.
> No propongas ni confirmes modificaciones.

Comprobá nombre, moneda, zona horaria e identidad de la cuenta.
La instalación/configuración no demuestra por sí sola que el servidor arrancó.

Para editar, seguí [propuesta → aprobación → confirmación](EDITING_CAMPAIGNS.md).
Las autoaprobaciones apagadas no certifican por sí solas una aprobación humana:
el operador debe revisar la propuesta y el cliente debe esperar esa autorización.

## No aparece: diagnóstico corto

| Síntoma | Revisá |
|---|---|
| Solo aparecen Gmail, Drive u otros servicios de la cuenta | Que estés en Desktop y que los MCP locales estén habilitados en esa conversación |
| Entrada ausente en servidores locales | JSON correcto, archivo correcto y reinicio completo de la aplicación |
| Entrada con error de arranque | Ruta del Python, dependencias y log del servidor |
| `ModuleNotFoundError` | El Python absoluto del venv instalado |
| `READ_ONLY` al proponer | Que seleccionaste el editor y reiniciaste el proceso correcto |
| Hay `google-ads` y `google-ads-editor` | Usá únicamente el perfil elegido; no desactives otra instalación activa sin revisar sus tareas |
| «El editor ya está ejecutándose» / error solo en Cowork y Code | Es un lanzador anterior que rechaza procesos adicionales. El lanzador de esta guía los aísla; no borres locks ni compartas la DB para sortearlo |

No publiques logs crudos: pueden contener IDs de cuentas y errores con datos de recursos.
Nunca compartas el contenido del env ni el JSON completo si contiene otros secretos.

## Retirar una conexión anterior

Después de comprobar una lectura y la edición autorizada con el perfil nuevo,
podés retirar la entrada anterior desde la misma pantalla de servidores locales.
Conservá `google-ads-editor`; eliminá únicamente la entrada vieja que identificaste.
Seguí [el procedimiento con respaldo y revisión de dependencias](RETIRE_OLD_CONNECTION.md).
Quitar la entrada no requiere borrar el laboratorio, el venv, el OAuth ni los historiales.

## Claude web

El navegador necesita un MCP remoto alcanzable por Anthropic.
El servidor de este repo no incluye autenticación HTTP, por lo que no hay una
receta de exposición pública lista para producción.
El túnel de OpenAI no se convierte en un conector remoto de Claude.
Para la ruta local, usá Desktop.

Fuentes:
[servidores locales](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) ·
[conectores remotos y diferencia de red](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).
