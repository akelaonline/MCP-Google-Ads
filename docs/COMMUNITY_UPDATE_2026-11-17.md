# Actualización de integración — 17 de noviembre de 2026

Google Ads MCP puede operar con clientes MCP compatibles, incluidos
ChatGPT mediante Secure MCP Tunnel y Claude Desktop mediante stdio local.

Ya están en main:

- Descubrimiento por MCC sin copiar todos los IDs de clientes:
  `GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS`.
- Exclusiones con prioridad, alcance estricto y congelado por proceso.
- Rechazo temprano de escrituras en READ_ONLY, antes de construir el cliente Ads o refrescar OAuth.
- Propuestas, confirmación, cifrado de pendientes y auditoría existentes.

## Empezá por acá

1. [Instalación común y perfiles](INSTALL_CLIENTS.md).
2. [ChatGPT por túnel](CHATGPT.md) o [Claude Desktop local](CLAUDE_DESKTOP.md).
3. [Edición con confirmación](EDITING_CAMPAIGNS.md).
4. [Estado de GTM/GA4](MEASUREMENT_STATUS.md).

El lanzador `scripts/run_profile.py` soporta los procesos adicionales que Claude
abre para Chat y Cowork/Code: mantiene el lock de la base principal y asigna
base y clave propias a cada proceso adicional. No elimina el aislamiento para
silenciar un error de inicio. Tres pruebas offline cubren concurrencia,
política/permisos y rechazo antes de iniciar el servidor.

## Qué se comprobó y qué no

Base de runtime: main `65c1725515402c440e1f5470ceb3fcb1564d10a9`,
TREE `fd0ac45d9ba3948403e36cf9c14c321a3904292e`.
Esta actualización agrega tutoriales y un lanzador opcional de perfiles con sus tests;
no modifica las tools, el cliente Google Ads ni la safety layer de esa base.

| Capacidad | Evidencia / límite |
|---|---|
| Suite combinada de #20 y #21 | Reporte de 547 tests, Ruff y lifecycle de 463 tools; no es una certificación nueva de escritura en vivo |
| Google Ads de lectura con MCC | Lecturas reales reportadas en dos clientes y rechazo de cuentas fuera de alcance/excluidas |
| ChatGPT por túnel | Túnel conectado y consultas reales de Ads verificadas |
| Editor local en Claude Desktop | El cliente respondió a initialize y tools/list; consulta de Google y edición real pendientes de la prueba en la sesión |
| Escritura real desde ChatGPT con este montaje | No verificada; una prueba de propuesta de presupuesto fue rechazada por la revisión del cliente antes de llegar al MCP |
| GTM/GA4 | Base separada: 142 tests pasan; gate completo y OAuth/E2E aún pendientes |
| Merchant API | Onboarding y validación real separados; no habilitados por esta actualización |

**Una conexión READ_ONLY no prueba que ChatGPT sea incapaz de editar.**
La documentación oficial actual admite tools de lectura y escritura.
Los permisos efectivos del cliente, el modo del proceso MCP y la autorización
de Google son capas diferentes. No garantizamos acceso por un nombre de plan.

Una lectura exitosa no demuestra una escritura, un preflight no demuestra
OAuth válido y un instalador exitoso no demuestra que el cliente cargó las tools.
Para editar, elegí primero un cambio concreto revisable y seguí el flujo de aprobación.
No crees recursos de gasto para comprobar conectividad.

No hay nueva release ni publicación de GTM/GA4 en main con esta documentación.
