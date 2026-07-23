# Contributing

This project was created and is maintained by **[Akela](https://github.com/akelaonline)**. Contributions are welcome — please keep the following in mind:

## Ground rules

1. **Every mutation goes through the safety layer.** New write tools must call `ctx.safety.propose(...)` — never call `ctx.client.mutate(...)` directly from a tool. This is the core design guarantee of this server: nothing touches a live account without an explicit `confirm_pending_action` (unless the operator opted into auto-approve).
2. **Every write tool needs a test** covering at least the propose → confirm path (see `tests/test_safety.py` for the pattern).
3. **Docstrings are the tool description the LLM sees.** Write them for an agent, not just a human — mention units (currency vs. micros), valid enum values, and constraints (character limits, required combinations of args).
4. Run `pytest` before opening a PR.

## Adding a new tool domain

1. Create `src/google_ads_mcp/tools/<domain>.py` with a `register(mcp, ctx)` function.
2. Add it to `ALL_MODULES` in `src/google_ads_mcp/tools/__init__.py`.
3. Document it in `docs/TOOLS.md`.

## Attribution

If you fork or substantially reuse this project, please keep the credit to Akela in the README and LICENSE, and consider linking back to [akelaonline/MCP-Google-Ads](https://github.com/akelaonline/MCP-Google-Ads).
