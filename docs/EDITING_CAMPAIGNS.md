# Editar campañas con confirmación

## Qué habilita una edición

Se necesitan las tres condiciones:

1. El cliente expone la tool y permite la llamada.
2. El proceso MCP tiene READ_ONLY=false, alcance correcto y autoaprobaciones apagadas.
3. La identidad OAuth tiene permisos en Google Ads.

Un error del cliente, del modo READ_ONLY o de Google representa capas distintas.
Una llamada rechazada no demuestra por sí sola que el plan de ChatGPT no admite edición.

## Crear un perfil editor

Partí del perfil de lectura de [la instalación común](INSTALL_CLIENTS.md).
Este ejemplo crea uno **nuevo** para Claude; si ya existe, se detiene.
Para un editor de ChatGPT usá otro nombre, otra base y otra clave,
y un túnel distinto mientras mantengas conectado el de lectura.

```bash
"$HOME/.google_ads_mcp_profiles/venv/bin/python" - <<'PY'
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import dotenv_values, set_key

root = Path.home() / ".google_ads_mcp_profiles"
source = root / "chatgpt-readonly/ads.env"
target = root / "claude-editor"
if target.exists():
    raise SystemExit("El perfil ya existe; no se sobrescribió.")
target.mkdir(mode=0o700)
env = target / "ads.env"
with env.open("xb") as stream:
    env.chmod(0o600)
    stream.write(source.read_bytes())
updates = {
    "GOOGLE_ADS_MCP_READ_ONLY": "false",
    "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST": "true",
    "GOOGLE_ADS_MCP_AUTO_APPROVE": "false",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND": "false",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE": "false",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE": "false",
    "GOOGLE_ADS_MCP_TRANSPORT": "stdio",
    "GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP": "false",
    "GOOGLE_ADS_MCP_AUDIT_DB": str(target / "audit.db"),
    "GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY": Fernet.generate_key().decode(),
}
for key, value in updates.items():
    set_key(str(env), key, value)
env.chmod(0o600)
print("Perfil editor preparado; no se llamó a Google.")
PY
```

El OAuth de Ads puede ser el mismo; la base y la clave de pendientes son nuevas.
El código, configuración y credenciales deben estar en carpetas privadas.
Con MCC, el servidor consulta la jerarquía al iniciar.

El ejemplo inicial de [ChatGPT](CHATGPT.md) usa solo lectura.
Su sección de edición explica cómo seleccionar el perfil nuevo y `mode = "editor"`.
No sirve cambiar únicamente el nombre del complemento.
El lanzador comprueba la política y mantiene cada proceso en su propia base. No cambies el perfil activo de reporting
sin revisar qué otras conversaciones lo usan.

## Primera edición: elegir un cambio real y acotado

No crees presupuestos, campañas o conversiones «para ver si conecta».
Primero comprobá lectura. Después identificá el cambio exacto con el operador.

Ejemplo de solicitud, reemplazando todos los campos:

> En la cuenta CUSTOMER_ID, campaña CAMPAIGN_ID, proponé cambiar el nombre
> de NOMBRE_ACTUAL a NOMBRE_NUEVO. No confirmes nada.
> Mostrame cuenta, ID, valor leído actualmente y valor propuesto.

No inventes IDs. Usá una campaña de prueba o un cambio real aprobado.
Un rename también modifica una cuenta: requiere revisión del operador.

## Qué revisar en la propuesta

- Cuenta y campaña correctas.
- Valor actual obtenido por lectura reciente.
- Nuevo valor exacto y alcance de las operaciones.
- Efectos sobre presupuesto, pujas, estado o publicación, cuando correspondan.
- `pending_action_id`, resumen y vencimiento de la acción.

La propuesta no aplica el cambio; no equivale a un dry-run de Google.
Si el dato cambió o la propuesta venció, cancelá y prepará otra.
Las lecturas que preceden una propuesta pueden contactar Google aun sin mutación.

## Confirmar o cancelar

Después de revisar, el operador puede pedir:

```text
Confirmá únicamente pending_action_id=<ID_REVISADO>.
```

El cliente llama a `confirm_pending_action`. Después debe volver a consultar
el recurso y mostrar el resultado junto con la referencia de auditoría.

Para descartar:

```text
Cancelá pending_action_id=<ID_REVISADO>.
```

El MCP implementa dos pasos técnicos. El cliente debe esperar la aprobación humana;
no supongas que un action ID demuestra que una persona revisó el cambio.
No habilites autoaprobaciones como solución a una llamada bloqueada.

## Dos clientes y límites

No compartas la DB ni la clave entre procesos. Una acción pertenece al perfil
que la creó: no la confirmes desde otro cliente con otra base.
Coordiná un único ejecutor para la misma campaña.

Una campaña PAUSED puede crearse sin generar delivery, pero crearla sigue siendo
una mutación. La generación de borradores en una conversación no cambia Google Ads.

GTM, GA4 y Merchant requieren integraciones/alcances propios:
la MCC de Ads no concede acceso a sus contenedores, propiedades o cuentas.

## Ejecución real observada y alcance de la evidencia

El 17/11/2026, el operador reportó la ejecución desde Claude Desktop de un bloque
aprobado: dos keywords nuevas en PHRASE y pausa de tres BROAD del mismo grupo.
Una lectura independiente mediante ChatGPT READ_ONLY encontró quince criterios
no eliminados: doce activos y tres pausados. Los diez criterios previos exactos/de
frase seguían activos. Presupuestos, estrategias y límites CPC de las cuatro
campañas consultadas coincidían con la línea base.

Las altas y pausas fueron fases separadas, no una transacción atómica. La verificación
no demuestra por sí sola qué proceso realizó cada cambio: el detalle de confirmaciones
y auditoría debe conservarse en el perfil ejecutor. Tampoco prueba una mejora comercial
ni garantiza un techo de gasto por día. No se cambiaron presupuestos como parte del bloque.
La edición real desde ChatGPT sigue sin verificarse en este montaje.
