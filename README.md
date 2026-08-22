<div align="center">

## 🌐 Elegí tu idioma / Choose your language

| [**🇦🇷🇪🇸 Leer en Español**](README.md) | [**🇬🇧🇺🇸 Read in English**](README.en.md) |
|:---:|:---:|
| *(Estás acá)* | *(You are here → click to switch)* |

---

# Google Ads MCP

**El servidor MCP para operar Google Ads desde Claude — no solo leerlo.**

Reportes, campañas, presupuestos, audiencias, conversiones y Performance Max, controlados por vos: cada escritura se propone, se previsualiza y espera tu confirmación antes de tocar una sola cuenta real.

Creado y mantenido por [**Akela**](https://github.com/akelaonline)

[![License: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Google Ads API v25](https://img.shields.io/badge/Google%20Ads%20API-v25-4285F4.svg)](https://developers.google.com/google-ads/api)
[![Versión](https://img.shields.io/badge/versión-0.16.8-informational.svg)](docs/RELEASE_0.16.8.md)
[![Tests](https://img.shields.io/badge/tests-346%2F346-success.svg)](docs/RELEASE_0.16.8.md)

[Inicio rápido](#inicio-rápido) · [Seguridad](#seguridad-de-fábrica) · [Validación](#validar-antes-de-producción) · [Cobertura](docs/V25_SERVICE_COVERAGE.md) · [Documentación](#documentación)

</div>

---

## Qué es esto

**Google Ads MCP** es un servidor [Model Context Protocol](https://modelcontextprotocol.io) que conecta a Claude (o cualquier cliente MCP compatible) directamente con la API v25 de Google Ads — para **gestionar** cuentas, no solo mirarlas.

Pensado para agencias y gestores de cuentas que administran campañas de **Google Ads y Meta Ads** desde un mismo asistente: reportes y GAQL crudo; campañas, presupuestos y estrategias de puja; anuncios, assets, keywords y segmentación; audiencias y Customer Match; conversiones y objetivos; Performance Max; experimentos; Smart Campaigns; batch jobs; acceso a cuentas y MCC; facturación y vínculos de producto; planificación; y servicios especializados de v25.

Palabras clave: *automatización de Google Ads con IA, gestión de campañas PPC con Claude, servidor MCP para publicidad digital, control de gasto publicitario con IA, agencia de marketing digital con Claude, integración Google Ads API v25, asistente de IA para Google Ads.*

Toda escritura real sigue el mismo camino, sin atajos:

```text
proponer → previsualizar → confirmar → ejecutar → auditar
```

Para despliegues de solo reporte:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

En modo solo lectura, los reportes, GAQL y la auditoría siguen disponibles, pero se bloquean tanto las propuestas de escritura nuevas como la confirmación de acciones pendientes previas.

## Por qué confiar en esta herramienta

- **Nunca ejecuta sin tu confirmación.** Cada escritura queda "pendiente" hasta que vos la aprobás explícitamente — nada se aplica a una cuenta real por accidente.
- **Aislamiento entre clientes verificado.** Si administrás varias cuentas desde una MCC, el servidor bloquea —antes de llamar a Google— cualquier operación que intente mezclar recursos de dos clientes distintos.
- **Auditoría completa y reversible.** Toda acción propuesta, confirmada o cancelada queda registrada; las acciones pendientes sobreviven incluso a un reinicio del servidor.
- **Validado en producción real**, no solo en teoría: cada versión pasa una batería de pruebas automáticas (346/346 en la 0.16.8) y una validación manual contra cuentas reales antes de recomendarse para uso diario.

## Versión actual: 0.16.8

**0.16.8 es la versión recomendada hoy.** No reemplaces una instalación productiva que ya funciona por 0.16.0, 0.16.1 o 0.16.2 — esas versiones tenían fallas conocidas y corregidas más adelante.

La serie v0.16 se validó de forma iterativa, siempre contra un entorno local real:

- **0.16.0**: fallaba al importar el servidor (`from_micros()` faltante); el aislamiento MCC recursivo tampoco cubría valores `Struct`/map de protobuf.
- **0.16.1**: arregla el arranque y el recorrido recursivo. La corrida local pasó a detectar **231 tests**, exponiendo 13 fallas de dobles de prueba desactualizados y avisos de registro duplicado de herramientas.
- **0.16.2**: sincroniza los clientes de prueba con el contrato de aislamiento real y fija la propiedad determinística de cada herramienta pública. El servidor se construye limpio (0 avisos de duplicados), pero quedaban 3 fallas de fixtures y 22 hallazgos de Ruff.
- **0.16.3**: resuelve las 3 fallas de pytest y los 22 hallazgos de Ruff restantes, sin debilitar ninguna barrera de seguridad. `validate_local.py` queda verde de punta a punta (smoke, Ruff, 232/232 pytest).
- **0.16.4**: cierra vacíos funcionales — actualizar/quitar franjas horarias de anuncios, opciones de URL de seguimiento (cuenta/campaña/grupo de anuncios), carga de conversiones telefónicas, App Campaigns (v25 `MULTI_CHANNEL`), Dynamic Search Ads completo. Corrige además cuatro bugs latentes de contrato v25 y suma una prueba que verifica cada servicio/método contra los stubs reales de v25.
- **0.16.5**: consentimiento GDPR en cargas offline/enhanced, reporte de cuota de impresiones perdida, grupos de productos para Standard Shopping, rotación de anuncios por campaña.
- **0.16.6**: assets extendidos (formulario de leads, precio, ubicación, app móvil, deep link), segmentación positiva de ubicaciones, límites de frecuencia, exclusión de audiencias a nivel campaña/grupo, variables personalizadas de conversión.
- **0.16.7**: ajustes menores — exclusión de tipos de asset por campaña, fechas de campaña, filtros de historial de cambios, límites de CPC en estrategias Target CPA/ROAS.
- **0.16.8**: corrige un bug de registro silencioso de herramientas duplicadas — solo los módulos legacy declarados explícitamente pueden omitirse; `create_conversion_value_rule` ahora pertenece a `conversions.py` (versión tipada), y la variante en formato protobuf-JSON queda disponible aparte como `create_conversion_value_rule_from_json`. Blindado con una prueba de registro dedicada.

`python scripts/validate_local.py` está verde de punta a punta (smoke, Ruff, **346/346 pytest**) sobre 0.16.8 — validado además con pruebas reales de punta a punta contra una cuenta de Google Ads en producción: modo solo lectura, aislamiento entre clientes, proponer/cancelar, proponer/confirmar, y recuperación de acciones pendientes tras un reinicio.

Ver [`docs/RELEASE_0.16.8.md`](docs/RELEASE_0.16.8.md) y las notas de cada versión 0.16.4–0.16.7 en [`docs/`](docs/).

### Propiedad determinística de cada herramienta

La herramienta detectó implementaciones nuevas y viejas compitiendo por los mismos nombres. Los dueños canónicos son explícitos (actualizados en 0.16.8 tras la revisión del registro):

```text
list_asset_group_signals             -> pmax_signals_listing.py
add_asset_group_signal               -> pmax_signals_listing.py
list_asset_group_listing_filters     -> pmax_signals_listing.py
create_conversion_value_rule         -> conversions.py        (condiciones tipadas)
list_conversion_value_rules          -> remaining_core_services.py (lectura completa)
```

Las definiciones legacy declaradas (por ejemplo `performance_max.py` para las señales de asset group, o la variante protobuf-JSON de creación, que sigue disponible como `create_conversion_value_rule_from_json`) deliberadamente no se registran. **Solo los módulos declarados explícitamente como legacy superado pueden omitirse en silencio** — cualquier otro módulo que defina el mismo nombre público de herramienta hace fallar la construcción del servidor, y `tests/test_tool_registry_sweep.py` verifica que el servidor real ensamblado sea dueño de cada herramienta canónica y que no exista ningún duplicado no declarado en todo el árbol.

## Seguridad de fábrica

### Aislamiento MCC / entre clientes

Usá una lista explícita de cuentas permitidas cuando una misma credencial pueda alcanzar varios clientes:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

El servidor:

- bloquea lecturas/escrituras fuera de la lista permitida;
- filtra el descubrimiento de cuentas;
- filtra filas de `customer_client`, `customer_client_link` y `customer_manager_link`, incluso en GAQL crudo;
- inspecciona recursivamente las referencias a recursos de cliente en cada operación CREATE/UPDATE/REMOVE, incluyendo mapas/Structs de protobuf y campos repetidos;
- permite el vínculo intencional entre dos clientes (manager/client) solo cuando ambos están en la lista permitida.

### Niveles de riesgo

Cada escritura se clasifica como:

- `standard`
- `spend` (afecta gasto/entrega)
- `destructive`
- `sensitive`

Las operaciones que cambian la entrega son conservadoras. Cambios en keywords habilitadas, segmentación, capacidad de conversión, adjuntar assets en vivo, y editar un RSA existente se clasifican como `spend` aunque la operación no mencione un monto explícito en dinero.

Política recomendada en producción:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

### Confirmaciones pendientes durables

Las propuestas quedan persistidas en SQLite y los argumentos de reintento se cifran con Fernet. Proporcioná una clave estable:

```dotenv
GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY=<clave-fernet>
```

o dejá que el servidor genere `<audit-db>.pending.key` junto a la base. Si falta o se corrompe la clave, la confirmación falla de forma segura (no ejecuta nada).

Usá un solo proceso del servidor por `audit.db`; el bloqueo de acciones pendientes es local al proceso, no distribuido.

## Capacidades

| Área | Cobertura |
|---|---|
| Cuentas y MCC | descubrimiento/jerarquía, vínculos manager/cliente, usuarios/roles/invitaciones, configuración de cuenta |
| Reportes | campañas, grupos de anuncios, anuncios, keywords, términos de búsqueda, dispositivos, geo, assets, audiencias, shopping, cuota de impresiones / IS perdida, historial de cambios (con filtros), GAQL crudo |
| Campañas | Search, Standard Shopping (con grupos de productos), Performance Max, Demand Gen, **App Campaigns (ACi/ACe)**, **Dynamic Search Ads**, Smart Campaigns, rotación de anuncios, límites de frecuencia, fechas de campaña, controles de herencia de extensiones |
| Presupuesto y pujas | ciclo de vida del presupuesto, CPC manual, Maximizar Clics/Conversiones/Valor, CPA/ROAS/cuota de impresiones objetivo (+ techo/piso de CPC), estrategias de cartera, modificadores de puja |
| Anuncios y assets | RSA, Display adaptable, Demand Gen, imágenes/video/llamadas/sitelinks/callouts/snippets/promociones/Business Message/WhatsApp/**formulario de leads/precio/ubicación/app móvil/deep link** |
| Keywords y segmentación | ciclo de vida, pujas, tipos de concordancia, negativas, exclusiones compartidas/de cuenta, ubicación/idioma/dispositivo/audiencia/tema, **ubicaciones positivas**, **exclusión de audiencias**, franjas horarias (agregar/actualizar/quitar), opciones de URL de seguimiento |
| Audiencias | remarketing, listas de usuarios (UserList), Customer Match, Audience, CustomAudience, CustomInterest |
| Conversiones y objetivos | acciones, cargas offline/**telefónicas**/enhanced (**consentimiento GDPR**, variables personalizadas), ajustes, variables personalizadas, reglas y sets de valor, objetivos unificados v25 |
| Performance Max | grupos de campaña/assets, señales, filtros de listado SHOPPING/RETAIL/WEBPAGE, guías de marca, previsualizaciones |
| Experimentos | ciclo de vida, brazos, programación/errores/promoción/graduación/finalización, splits de tráfico atómicos |
| Batch / Smart Bidding | batch jobs controlados, ajustes de estacionalidad, exclusiones de datos |
| Facturación y vínculos | cuentas de pago, configuración de facturación, presupuestos de cuenta/facturas, ProductLink/Invitation, DataLink, YouTube/analítica de apps |
| Planificación / especializado | Keyword Planner, Reach Planner, sugerencias de viajes/marca, Local Services, identidad, incentivos, visibilidad SKAd, carga de YouTube |
| Con acceso restringido | Audience Insights, Benchmarks, Creator Insights; generación de assets (beta cerrada) |

Ver [`docs/V25_SERVICE_COVERAGE.md`](docs/V25_SERVICE_COVERAGE.md) y [`docs/TOOLS.md`](docs/TOOLS.md).

## Inicio rápido

```bash
git clone https://github.com/akelaonline/MCP-Google-Ads.git
cd MCP-Google-Ads
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

Configurá al menos:

```dotenv
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
```

Ejemplo local por stdio:

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "/ruta/absoluta/a/MCP-Google-Ads/.venv/bin/python",
      "args": ["-m", "google_ads_mcp.server"],
      "env": {
        "GOOGLE_ADS_MCP_ENV_FILE": "/ruta/absoluta/a/MCP-Google-Ads/.env"
      }
    }
  }
}
```

Se recomienda `stdio`. El transporte HTTP queda bloqueado por defecto; si se habilita deliberadamente, hacerlo detrás de tu propio límite autenticado. `GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true` **no** agrega autenticación por sí solo.

## Validar antes de producción

Después de actualizar desde `main`, validá el checkout exacto **antes** de reemplazar un MCP en funcionamiento:

```bash
git fetch origin
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/validate_local.py
```

El validador corre:

```text
smoke offline aislado -> Ruff -> pytest completo
```

El smoke test usa una base de auditoría temporal y configuración solo-lectura, importa cada módulo de herramientas, construye el servidor, prueba la regresión de `from_micros()`, ejercita el aislamiento MCC anidado, y verifica la propiedad determinística de cada herramienta.

Recién avanzá cuando termine con:

```text
LOCAL VALIDATION GREEN
validated commit: <sha>
validated version: 0.16.8
```

Después seguí [`docs/VALIDATION_CHECKLIST.md`](docs/VALIDATION_CHECKLIST.md) para la secuencia contra cuenta real: chequeos de solo lectura, aislamiento MCC, proponer/cancelar, proponer/confirmar, recuperación tras reinicio, bloqueo cross-cliente, vínculo legítimo manager/cliente, límites de riesgo y protección ante doble confirmación.

Este repositorio no tiene GitHub Actions a propósito; la validación es local y manual.

## Límites de alcance

Este MCP envuelve la API de Google Ads, no cada producto publicitario adyacente de Google.

- La edición de catálogo/feed de Merchant Center pertenece a Merchant API; el vínculo del lado de Ads y las operaciones de Shopping/PMax sí están cubiertas acá.
- La administración de Google Business Profile es un producto aparte.
- Smart Shopping (legado) debería migrarse a Performance Max.
- No se emulan escrituras de video legadas ya eliminadas por Google.
- Los servicios beta o con acceso restringido de Google siguen requiriendo elegibilidad del lado de Google.
- `ReservationService` no está disponible públicamente y no se simula.

## Documentación

- [Notas de la versión 0.16.8](docs/RELEASE_0.16.8.md)
- [Notas de la versión 0.16.7](docs/RELEASE_0.16.7.md)
- [Notas de la versión 0.16.6](docs/RELEASE_0.16.6.md)
- [Notas de la versión 0.16.5](docs/RELEASE_0.16.5.md)
- [Notas de la versión 0.16.4](docs/RELEASE_0.16.4.md)
- [Notas de la versión 0.16.3](docs/RELEASE_0.16.3.md)
- [Procedimiento seguro de actualización local](docs/UPDATE_LOCAL.md)
- [Checklist de validación en producción](docs/VALIDATION_CHECKLIST.md)
- [Instalación](docs/SETUP.md)
- [Clientes MCP compatibles](docs/CLIENTS.md)
- [Modelo de seguridad](docs/SAFETY.md)
- [Referencia de herramientas](docs/TOOLS.md)
- [Cobertura de la API v25 de Google Ads](docs/V25_SERVICE_COVERAGE.md)
- [Herramientas para agencias](docs/AGENCY_TOOLS.md)
- [Batch jobs y Smart Bidding](docs/BATCH_SMART_BIDDING.md)
- [Ejemplos](docs/EXAMPLES.md)
- [Preguntas frecuentes](docs/FAQ.md)
- [Historial de cambios](CHANGELOG.md)

## Licencia

MIT. Ver [`LICENSE`](LICENSE).
