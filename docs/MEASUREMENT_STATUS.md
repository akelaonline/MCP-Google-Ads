# GTM y GA4: estado y próximo paso

Actualizado: 17 de noviembre de 2026.

Google Ads MCP en main **no incorpora** la suite GTM/GA4.
El trabajo existente está en [PR #14](https://github.com/akelaonline/MCP-Google-Ads/pull/14),
rama `feature/measurement-ops-v0.1`, paquete `suite/measurement_ops/`.
Es una integración separada; no hace falta terminarla para editar campañas de Ads.

## Validación de la base existente

HEAD examinado: `f570f6386af924cebfd2c4a5c207233050bd57f6`.

En una copia aislada se verificaron los hashes Git de los 60 archivos y se ejecutó
el validador existente con Python 3.12, Ruff 0.8.6 y credenciales ausentes:

| Comprobación | Resultado |
|---|---|
| Compilación Python | PASS |
| Ruff | PASS |
| pytest | 142 PASS |
| Imports de todos los módulos | PASS |
| Lint del plugin WordPress | Pendiente: PHP no está instalado en ese entorno |
| Validador completo | NO GREEN: se detiene por el prerrequisito PHP |
| OAuth y lectura real GTM/GA4 | Pendientes |
| Escritura, publicación y pilotos web | No realizados |

Esto no certifica acceso a una cuenta real ni publicación en producción.
El PR permanece draft. No fue mergeado ni activado con el servidor Ads.

## Qué falta, en orden

1. Completar el gate offline incluyendo PHP.
2. En Google Cloud, habilitar Tag Manager API, Analytics Admin API y Analytics Data API.
3. Autorizar localmente los grants dedicados de lectura de GTM y GA4.
   Los helpers y el procedimiento están en
   [OAuth del PR](https://github.com/akelaonline/MCP-Google-Ads/blob/feature/measurement-ops-v0.1/suite/measurement_ops/docs/OAUTH_READONLY_SETUP.md).
4. Listar identidades accesibles y verificar el sitio, contenedor GTM y propiedad GA4 correctos.
5. Completar [Issue #15](https://github.com/akelaonline/MCP-Google-Ads/issues/15)
   con lecturas reales, sin tocar tags ni enviar formularios.
6. Para edición posterior, validar workspace aislado, preview, eventos reales y consentimiento;
   publicar únicamente una versión revisada y aprobada.
7. Completar los pilotos WordPress/Astro previstos en el PR.

Al inicio deben seguir apagados `GTM_ENABLE_PREVIEW`, `GTM_ENABLE_WRITES`
y `GTM_ENABLE_PUBLISH`. No reutilices el refresh token de Ads como si tuviera scopes GTM/GA4.
La relación cuenta Ads → contenedor GTM → propiedad GA4 se verifica por cliente;
no se deduce automáticamente del MCC.

## Fuentes

- [GTM API: autorización y scopes](https://developers.google.com/tag-platform/tag-manager/api/v2/authorization)
- [PR #14](https://github.com/akelaonline/MCP-Google-Ads/pull/14)
- [Issue #15](https://github.com/akelaonline/MCP-Google-Ads/issues/15)
