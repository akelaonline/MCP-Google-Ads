# Instalación: ChatGPT y Claude Desktop

Esta guía instala Google Ads MCP en un Mac con Python 3.11 o posterior.
Para otras plataformas, adaptá las rutas y consultá [SETUP](SETUP.md).

## 1. Elegí dónde vas a conversar

| Cliente | Conexión | Dónde aparece |
|---|---|---|
| ChatGPT web | Secure MCP Tunnel de OpenAI hacia un proceso local stdio | Complemento/plugin de ChatGPT |
| Claude Desktop | Proceso local stdio | Aplicación Claude del Mac |
| claude.ai en el navegador | Necesita un servidor remoto autenticado | No lee la configuración local de Claude Desktop |

Un proyecto de Claude organiza conversaciones; no instala ni conecta servidores.
Podés usar tu proyecto habitual desde la aplicación Desktop.

**El servidor puede leer y editar.** Con `GOOGLE_ADS_MCP_READ_ONLY=true`,
las escrituras están bloqueadas independientemente del cliente.
Con `false` y las cuatro autoaprobaciones apagadas, las escrituras normales
producen una propuesta; la tool de confirmación ejecuta la operación.
La aprobación que muestra el cliente y la confirmación del MCP son controles diferentes.

## 2. Instalación nueva, fuera de una instalación activa

Estos comandos usan una carpeta nueva. Si ya existe, seguí
[actualización y rollback](UPDATE_AND_ROLLBACK_0.18.1.md); no reemplaces tus credenciales.

```bash
mkdir -p "$HOME/.google_ads_mcp_profiles"
chmod 700 "$HOME/.google_ads_mcp_profiles"
git clone https://github.com/akelaonline/MCP-Google-Ads.git "$HOME/.google_ads_mcp_profiles/code"
python3 -m venv "$HOME/.google_ads_mcp_profiles/venv"
"$HOME/.google_ads_mcp_profiles/venv/bin/python" -m pip install -c "$HOME/.google_ads_mcp_profiles/code/constraints-certified.txt" -e "$HOME/.google_ads_mcp_profiles/code[dev,auth]"
mkdir -p "$HOME/.google_ads_mcp_profiles/chatgpt-readonly"
chmod 700 "$HOME/.google_ads_mcp_profiles/chatgpt-readonly"
cp -n "$HOME/.google_ads_mcp_profiles/code/.env.example" "$HOME/.google_ads_mcp_profiles/chatgpt-readonly/ads.env"
chmod 600 "$HOME/.google_ads_mcp_profiles/chatgpt-readonly/ads.env"
```

No guardes secretos dentro del checkout. Las rutas de configuración deben ser
absolutas. En macOS podés abrir el archivo con:

```bash
open -e "$HOME/.google_ads_mcp_profiles/chatgpt-readonly/ads.env"
```

## 3. OAuth y alcance

Completá localmente Client ID, Client Secret y Refresh Token siguiendo
[SETUP](SETUP.md). Si ya tenés OAuth válido para Google Ads, cambiar de cliente
MCP o pasar de lectura a edición no exige por sí mismo repetirlo.
La identidad de Google debe tener permiso de edición en la cuenta para ejecutar cambios.

El helper OAuth existente imprime el refresh token en la Terminal:
copialo únicamente al archivo privado; no compartas esa salida, capturas ni logs.

Para una MCC, usá su ID de diez dígitos en estas dos variables
(`1111111111` es un ejemplo, reemplazalo):

```dotenv
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1111111111
GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS=1111111111
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=
GOOGLE_ADS_MCP_EXCLUDED_CUSTOMER_IDS=
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
GOOGLE_ADS_MCP_READ_ONLY=true
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
GOOGLE_ADS_MCP_TRANSPORT=stdio
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=false
GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS=
GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST=false
```

El MCC descubre clientes ENABLED al iniciar. Las exclusiones ganan siempre
y el alcance se congela hasta reiniciar: [reglas completas](MCC_SCOPE_DISCOVERY.md).
`list_accessible_customers` no enumera necesariamente todos los hijos del MCC;
usá también `get_account_hierarchy`.

## 4. Base y clave propias del perfil

Este paso guarda una clave Fernet en el archivo privado sin imprimirla.
No modifica una clave ya existente.

```bash
"$HOME/.google_ads_mcp_profiles/venv/bin/python" - <<'PY'
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import dotenv_values, set_key
profile = Path.home() / ".google_ads_mcp_profiles/chatgpt-readonly"
env = profile / "ads.env"
values = dotenv_values(env, interpolate=False)
set_key(str(env), "GOOGLE_ADS_MCP_AUDIT_DB", str(profile / "audit.db"))
if not values.get("GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY"):
    set_key(str(env), "GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY", Fernet.generate_key().decode())
env.chmod(0o600)
print("Base y clave configuradas; no se imprimieron secretos.")
PY
```

No exportes otras variables `GOOGLE_ADS_*` en la Terminal que inicia el MCP:
el entorno del proceso tiene precedencia sobre el archivo dotenv.

## 5. Validar y conectar

Validación offline del código:

```bash
"$HOME/.google_ads_mcp_profiles/venv/bin/python" "$HOME/.google_ads_mcp_profiles/code/scripts/validate_local.py"
```

Preflight de este perfil de lectura, sin llamadas a Google:

```bash
"$HOME/.google_ads_mcp_profiles/venv/bin/python" "$HOME/.google_ads_mcp_profiles/code/scripts/lab_preflight.py" --lab-dir "$HOME/.google_ads_mcp_profiles/chatgpt-readonly" --env-file "$HOME/.google_ads_mcp_profiles/chatgpt-readonly/ads.env" --repo-root "$HOME/.google_ads_mcp_profiles/code"
```

El preflight de laboratorio exige READ_ONLY=true: no sirve como gate de un editor.
El lanzador de perfiles valida ambos modos localmente:

```bash
"$HOME/.google_ads_mcp_profiles/venv/bin/python" "$HOME/.google_ads_mcp_profiles/code/scripts/run_profile.py" --env "$HOME/.google_ads_mcp_profiles/chatgpt-readonly/ads.env" --mode readonly --check
```

`--check` no construye el cliente Ads ni llama a Google.

Continuá por [ChatGPT](CHATGPT.md) o [Claude Desktop](CLAUDE_DESKTOP.md).
Para un editor, seguí [edición con confirmación](EDITING_CAMPAIGNS.md).

## Dos clientes simultáneos

Pueden consultar el mismo MCC con el mismo OAuth. Cada proceso necesita su propio
archivo de configuración, base de auditoría y clave de pendientes.
**No compartas una base entre procesos**: los controles de confirmación en esta
versión son locales al proceso. No ejecutes una misma propuesta desde dos clientes.
Separá el trabajo sobre una misma campaña para evitar cambios concurrentes.
