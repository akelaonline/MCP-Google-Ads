# Connecting ChatGPT, Claude Desktop and other MCP clients

Google Ads MCP supports read and write operations. Effective access depends on
client permissions, the server profile and Google Ads permissions. READ_ONLY=true
blocks mutations regardless of which client sends the request.

## Start here

| Task | Guide |
|---|---|
| Install with private OAuth/configuration and per-process storage | [Common setup](INSTALL_CLIENTS.md) |
| Connect ChatGPT web through Secure MCP Tunnel | [ChatGPT](CHATGPT.md) |
| Connect Claude Desktop via local stdio | [Claude Desktop](CLAUDE_DESKTOP.md) |
| Propose, approve, confirm and verify campaign changes | [Editing campaigns](EDITING_CAMPAIGNS.md) |
| Discover MCC clients without entering every ID | [MCC scope](MCC_SCOPE_DISCOVERY.md) |
| GTM/GA4 integration status | [Measurement status](MEASUREMENT_STATUS.md) |
| Current integration evidence and limits | [Community update](COMMUNITY_UPDATE_2026-11-17.md) |

The step-by-step client guides are in Spanish. They include copyable commands,
configuration, troubleshooting and official source links.

## Local and remote are different

Claude Desktop can launch a stdio process on the Mac. Its local JSON configuration
does not register a remote connector in claude.ai. Use the native Desktop app and
check which tools are enabled in the actual conversation.

ChatGPT web can reach a local stdio server through OpenAI Secure MCP Tunnel.
The runtime key authenticates the tunnel, while Google OAuth remains local to
the Ads server. This route does not require enabling the repository HTTP mode.

A generic remote HTTP client needs a separately authenticated boundary. The repo
has no remote identity provider. GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true removes
a startup check; it does not add authentication. Do not expose an unprotected
write-capable endpoint.

## Server policy remains authoritative

The server enforces READ_ONLY, account scope, risk classification, proposal and
confirmation, encrypted pending storage and audit history. The client must still
wait for the operator to review the proposed change before calling confirmation.
A pending ID is a technical step, not evidence of human review.

READ_ONLY rejects classified write tools before building an Ads client or
refreshing OAuth. Reports and GAQL can still run. An error from a client security
review happens before the MCP and must not be described as a server rejection.

## Simultaneous clients and processes

Different processes must not share a pending-action DB. In this version,
confirmation/cancellation locks are process-local. Keep profile files, audit DBs
and encryption keys separate. Reusing the same OAuth identity is possible when
it has the required permissions; that does not make pending state shareable.

The optional POSIX launcher scripts/run_profile.py keeps one primary DB owner
and allocates isolated DB/key directories for additional Claude processes.
Pending actions in an additional instance stay with that instance's connection;
the files are retained after shutdown but another fresh instance does not recover
them automatically. Review and propose again after reconnecting.

For a sequential migration, stop the previous owner before reusing an existing
profile and its DB/key. For concurrent clients, use separate profiles.

Start by reading a permitted account. For a write test, agree on a concrete
change and inspect the proposal before confirmation. Creating a budget as a
connectivity check is not a read-only test.
