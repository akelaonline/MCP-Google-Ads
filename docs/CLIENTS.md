# Connecting Google Ads MCP from Claude or another MCP client

Google Ads MCP is a server. It does not require a specific AI client: any client that can speak Model Context Protocol and invoke the exposed tools can operate it, subject to the server's own safety and customer-isolation policy.

## Local clients: stdio — recommended

The safest/default mode is `stdio`. The MCP client launches the local Python process directly.

Example configuration shape:

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "/absolute/path/to/MCP-Google-Ads/.venv/bin/python",
      "args": ["-m", "google_ads_mcp.server"],
      "env": {
        "GOOGLE_ADS_MCP_ENV_FILE": "/absolute/path/to/MCP-Google-Ads/.env"
      }
    }
  }
}
```

This pattern is appropriate for Claude Desktop/Claude Code and any other MCP host that can launch a local stdio server.

The client does not receive the Google Ads refresh token directly; the local MCP process reads its own `.env` and performs Google Ads API calls.

## Remote/cloud clients

A cloud or web client cannot launch a process on your local computer through stdio. For that case the MCP server must run somewhere reachable by the client and use a network transport.

This repository supports HTTP, but intentionally does **not** include a remote identity provider. HTTP therefore remains blocked unless explicitly enabled:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=http
GOOGLE_ADS_MCP_HTTP_PORT=8080
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true
```

`GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true` only removes the startup block. It does not add authentication.

A remote deployment must place the MCP behind an authenticated and network-restricted boundary such as an authenticated reverse proxy or another access layer appropriate to the environment. Do not expose a write-capable instance directly to the public Internet.

## Server policy is authoritative

The AI client is not trusted to enforce production safety by itself. The MCP server centrally enforces:

- `GOOGLE_ADS_MCP_READ_ONLY`;
- customer allowlists;
- recursive cross-customer mutation isolation;
- MCC hierarchy/link read filtering;
- standard/spend/destructive/sensitive risk classification;
- propose/confirm execution flow;
- encrypted durable pending actions;
- execution audit history.

This means the same local server can be used by different MCP-capable clients without changing its Google Ads safety model.

## Recommended production pattern

For a local operator workstation:

```text
MCP-capable AI client
        |
      stdio
        |
Google Ads MCP (local Python process)
        |
 Google Ads API v25
```

For a remote/cloud operator:

```text
MCP-capable cloud client
        |
 authenticated network boundary
        |
Google Ads MCP (HTTP, private server)
        |
 Google Ads API v25
```

The second pattern is only safe when the external boundary authenticates and restricts access.

## Switching clients

No migration of Google Ads state is required when moving between MCP clients. Point the new client at the same server installation/configuration, or deploy the same repository/configuration in the intended environment.

Keep these server-side values stable where applicable:

- Google Ads OAuth/developer credentials;
- customer allowlist;
- audit DB;
- pending encryption key;
- read-only/approval policy.

## First connection test

Ask the client to:

```text
List my accessible Google Ads customer IDs.
```

Then, while write mode requires confirmation:

```text
Propose pausing campaign 123. Do not confirm it.
```

The expected result is a `pending_action_id` with no live change. Only an explicit `confirm_pending_action(action_id)` should execute the mutation.

See also:

- [`SETUP.md`](SETUP.md)
- [`SAFETY.md`](SAFETY.md)
- [`UPDATE_LOCAL.md`](UPDATE_LOCAL.md)
- [`VALIDATION_CHECKLIST.md`](VALIDATION_CHECKLIST.md)
