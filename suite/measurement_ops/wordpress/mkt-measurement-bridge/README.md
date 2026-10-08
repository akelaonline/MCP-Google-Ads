# MKT Measurement Bridge

WordPress companion plugin for Measurement Ops.

## Requirements

- WordPress 6.9+
- WordPress MCP Adapter when abilities are invoked through MCP
- an authenticated WordPress administrator for write abilities

## Abilities

- `mkt-measurement/get-config` — read the bridge-managed GTM state.
- `mkt-measurement/set-gtm-container` — configure GTM injection. Requires
  `manage_options` and `confirm=true`.

The plugin deliberately does **not** expose arbitrary PHP/theme editing.

## Injection

When enabled, the plugin inserts the standard GTM script via `wp_head` and the
noscript iframe via `wp_body_open`. The Measurement Ops web auditor must run
before enabling it to avoid duplicating a GTM installation already managed by
another plugin/theme.

## Safety

Publishing a GTM version remains a separate operation in Measurement Ops. This
plugin only installs the chosen container ID on the WordPress site.
