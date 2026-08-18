from pathlib import Path

path = Path("CHANGELOG.md")
text = path.read_text()
marker = "# Changelog\n\n"
entry = """## 0.13.0 — 2026-08-18

### Added
- **Customer isolation:** optional `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` scopes reads, writes, and account discovery to known Google Ads customer IDs.
- **Strict deployment mode:** `GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true` refuses startup when no customer scope is configured.
- **Risk-aware approvals:** write actions are centrally classified as `standard`, `spend`, `destructive`, or `sensitive`.
- Separate production auto-approve controls for spend, destructive, and sensitive/account-access actions; all default to false.

### Changed
- Production `GOOGLE_ADS_MCP_AUTO_APPROVE=true` now auto-executes only standard-risk writes unless a high-risk category is explicitly opted in.
- Customer scope is enforced in both the Google Ads client wrapper and the safety layer for defense in depth.
- Pending actions now expose `risk_level` and `confirmation_reason`.
- README, setup, safety documentation, and environment examples now include the recommended multi-client deployment model.

### Compatibility
- Deployments without a customer allowlist retain the previous account scope.
- Internal/direct `SafetyLayer(auto_approve=True)` callers that omit the new policy parameters retain legacy execution semantics; the production context always passes explicit high-risk policy settings.

See `docs/RELEASE_0.13.0.md` for full release and deployment notes.

"""
if "## 0.13.0 — 2026-08-18" not in text:
    if not text.startswith(marker):
        raise SystemExit("Unexpected CHANGELOG header")
    text = marker + entry + text[len(marker):]
    path.write_text(text)
