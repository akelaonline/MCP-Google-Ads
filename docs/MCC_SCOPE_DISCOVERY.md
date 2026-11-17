# Allowlist derivada de un MCC

En vez de copiar cada cliente a `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`, nombrá el/los MCC:

```env
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1111111111          # el MCC (opcional si hay un único manager)
GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS=1111111111    # MCC cuyos clientes entran al alcance
GOOGLE_ADS_MCP_EXCLUDED_CUSTOMER_IDS=            # clientes a dejar afuera (deny gana)
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true   # se mantiene fail-closed
```

## Reglas
- Al iniciar, el servidor lee `customer_client` del MCC (GAQL de solo lectura) y congela el resultado en la allowlist normal. Cliente, safety, replay y Merchant siguen aplicando exactamente los mismos controles.
- Alcance efectivo = IDs explícitos + el/los MCC + clientes **ENABLED no-manager** − `EXCLUDED_CUSTOMER_IDS`.
- Si el descubrimiento falla, el alcance **no se amplía**: quedan solo los IDs explícitos y el MCC. Con allowlist requerida y alcance vacío, el servidor no arranca.
- El alcance es fijo durante la vida del proceso: un cliente nuevo del MCC se deniega hasta reiniciar.
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` debe ser uno de los managers (o vacío si hay uno solo; con varios es obligatorio).
- Los logs no incluyen IDs ni texto de excepciones.
