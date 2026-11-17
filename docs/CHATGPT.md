# ChatGPT: conexión por Secure MCP Tunnel

Empezá por [la instalación común](INSTALL_CLIENTS.md).
El servidor sigue en tu computadora; ChatGPT lo invoca mediante el túnel oficial.
No hace falta exponer un puerto público ni habilitar HTTP en Google Ads MCP.

## 1. Crear el túnel y la clave correcta

1. Entrá a [Tunnels de OpenAI Platform](https://platform.openai.com/settings/organization/tunnels).
2. Creá el túnel y asociá la organización/workspace que utilizará el complemento.
3. Copiá su ID completo, que empieza por `tunnel_`.
4. Descargá desde esa página el cliente oficial apropiado para tu sistema.
   Las [releases oficiales](https://github.com/openai/tunnel-client/releases)
   permiten verificar el SHA256 del archivo antes de ejecutarlo.
5. Creá una clave **runtime** en [API keys](https://platform.openai.com/settings/organization/api-keys).
   Su identidad necesita permisos Tunnels **Read + Use** para ese túnel.
   Crear/administrar túneles requiere Read + Manage.

Son valores distintos:

| Valor | Uso |
|---|---|
| ID `tunnel_...` | Identificar el túnel en el cliente y en ChatGPT |
| Clave API runtime `sk-...` | Autenticar el proceso tunnel-client ante OpenAI |
| OAuth de Google Ads | Lo lee el MCP desde el archivo privado |
| Client ID/Secret OAuth avanzado del complemento | No se usan en este ejemplo de servidor stdio sin OAuth MCP |

No uses una clave de administración para mantener conectado el túnel.
No pegues claves en chats, argumentos de comandos ni archivos del repositorio.

## 2. Iniciar un perfil de solo lectura

El siguiente ejemplo usa el ejecutable oficial ya descargado.
Reemplazá `/RUTA/ABSOLUTA/tunnel-client` por su ruta real.
Ejecutalo desde una Terminal interactiva del Mac; solicita la clave sin mostrarla.
El ID del túnel se pide por separado.

```bash
"$HOME/.google_ads_mcp_profiles/venv/bin/python" - <<'PY'
from pathlib import Path
import getpass
import os
import re
import shlex
import subprocess
from dotenv import dotenv_values

root = Path.home() / ".google_ads_mcp_profiles"
profile = root / "chatgpt-readonly/ads.env"
mode = "readonly"
binary = Path("/RUTA/ABSOLUTA/tunnel-client")
values = dotenv_values(profile, interpolate=False)
subprocess.run([str(root / "venv/bin/python"), str(root / "code/scripts/run_profile.py"), "--env", str(profile), "--mode", mode, "--check"], check=True)
tunnel = input("ID completo del túnel: ").strip() if os.isatty(0) else None
if tunnel is None:
    with open("/dev/tty") as terminal:
        print("ID completo del túnel: ", end="", flush=True)
        tunnel = terminal.readline().strip()
assert re.fullmatch(r"tunnel_(?:[a-z0-9]{4}_)?[a-z0-9]{32}", tunnel), "ID inválido"
key = getpass.getpass("Clave API runtime de OpenAI (no se muestra): ").strip()
assert key.startswith("sk-") and not any(c.isspace() for c in key), "Se esperaba una clave API, no el ID del túnel"
prefixes = ("GOOGLE_ADS_", "GOOGLE_MERCHANT_CENTER_", "CONTROL_PLANE_", "MCP_", "HEALTH_", "TUNNEL_CLIENT_", "CLOUDFLARED_")
env = {k: v for k, v in os.environ.items() if not k.startswith(prefixes) and k not in {"OPENAI_API_KEY", "OPENAI_ADMIN_KEY"}}
env.update({
    "GOOGLE_ADS_MCP_ENV_FILE": str(profile),
    "CONTROL_PLANE_API_KEY": key,
    "CONTROL_PLANE_TUNNEL_ID": tunnel,
    "MCP_COMMAND": shlex.join([str(root / "venv/bin/python"), str(root / "code/scripts/run_profile.py"), "--env", str(profile), "--mode", mode]),
    "MCP_OAUTH_DISCOVERY": "disabled",
    "HEALTH_LISTEN_ADDR": "127.0.0.1:0",
    "LOG_HTTP_RAW_UNSAFE": "false",
    "TRACING_ENABLED": "false",
    "ALLOW_REMOTE_UI": "false",
    "OPEN_WEB_UI": "false",
})
subprocess.run([str(binary), "doctor", "--explain"], env=env, check=True)
try:
    subprocess.run([str(binary), "run"], env=env, check=True)
except KeyboardInterrupt:
    pass
PY
```

Este es un ejemplo manual basado en el contrato oficial de tunnel-client;
no descarga ni certifica un binario automáticamente.
`doctor` correcto prueba la configuración del túnel, no los permisos de Google Ads.
Mantené la Terminal abierta, el Mac despierto y la conexión a Internet activa.
No ejecutes dos clientes de túnel para el mismo ID y canal.

## 3. Crear el complemento en ChatGPT

Con el túnel funcionando:

1. Abrí **Plugins/Complementos → + → Agregar servidor MCP personalizado**.
2. Poné un nombre, por ejemplo `Google Ads — Lectura`.
3. En Conexión, elegí **Túnel** y pegá el ID `tunnel_...`.
4. En Autenticación, elegí **Sin autenticación / None**.
5. Revisá el aviso, creá el complemento e instalalo si la interfaz lo requiere.
6. Abrí una conversación y seleccioná el complemento.

**None se refiere al OAuth entre ChatGPT y este MCP.**
El túnel se autentica con la clave runtime y Google Ads conserva su propio OAuth.

Si aparece «No se pudo detectar la configuración de OAuth», revisá la
autenticación principal: este servidor no ofrece un proveedor OAuth remoto.
No completes URLs de autorización inventadas ni pegues las credenciales de
Google Ads en la configuración OAuth avanzada del complemento.

## 4. Primera consulta y edición

Primer pedido:

> Usá únicamente el complemento Google Ads. Consultá la jerarquía de mi MCC
> y el resumen de una cuenta permitida. No propongas ni confirmes cambios.

La lista directa de accesibles y la jerarquía del MCC pueden tener tamaños distintos.
Una lectura real correcta confirma esta conexión; no certifica escrituras.

**ChatGPT admite herramientas MCP de lectura y escritura**, sujetas a permisos
y controles de la cuenta/workspace. No atribuyas un rechazo por READ_ONLY al plan.
Para editar:

1. Creá otro perfil siguiendo [edición con confirmación](EDITING_CAMPAIGNS.md), cambiando el directorio de destino del ejemplo a `chatgpt-editor`.
2. Creá otro túnel si vas a mantener el de lectura funcionando.
3. En el ejemplo de inicio de esta guía, cambiá solo las dos líneas de selección a:

```python
profile = root / "chatgpt-editor/ads.env"
mode = "editor"
```

4. Ingresá el ID del túnel editor. La validación local exige READ_ONLY=false, todas las autoaprobaciones apagadas y base privada.
5. Creá un complemento distinto, por ejemplo `Google Ads — Editor`, y refrescá las tools si el cliente lo pide.
6. Consultá primero una cuenta y luego elegí con el operador un cambio concreto antes de proponerlo o confirmarlo.

El modo `editor` solo habilita el flujo de confirmación. No aplica cambios por iniciar el proceso.
La edición real desde ChatGPT no se ha certificado en el montaje documentado aquí.

Si una revisión de seguridad del cliente rechaza una llamada, registrá la acción
y el motivo. Eso no equivale a un rechazo del MCP ni prueba una limitación del plan.
No repitas la operación por otro camino para saltar ese bloqueo.

## Fuentes oficiales

- [Agregar un servidor MCP a ChatGPT](https://developers.openai.com/api/docs/guides/custom-mcp-server)
- [Onboarding de tunnel-client](https://github.com/openai/tunnel-client/blob/v0.0.21/docs/onboarding.md)
- [Permisos de tunnel-client](https://github.com/openai/tunnel-client/blob/v0.0.21/docs/permissions.md)
