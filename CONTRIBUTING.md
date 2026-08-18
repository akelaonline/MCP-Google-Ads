# Contributing

Thanks for helping improve Google Ads MCP.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
make check
```

The current release targets **Google Ads API v25** through the tested 31.x `google-ads` Python client line.

## Pull requests

Keep changes focused and explain:

- what changed;
- why it changed;
- whether it affects reads, writes or both;
- which Google Ads API resource/service contract it relies on;
- how it was validated.

## Non-negotiable write-safety rule

Every mutating MCP tool must go through:

```python
ctx.safety.propose(...)
```

The actual Google Ads mutation belongs inside the `execute` callable supplied to the safety layer. Do not call a live mutate directly from the outer tool body.

## Multi-resource writes

If several resources must exist together, prefer the atomic `GoogleAdsService.Mutate` path exposed by the client wrapper.

Examples:

- create Asset + attach CampaignAsset;
- create image assets + visual ad;
- create PMax assets + AssetGroup + AssetGroupAsset links.

Do not claim a flow is atomic when it is implemented as independent mutate RPCs.

## Google Ads API compatibility

Do not rely only on permissive test fakes for protobuf-heavy code.

When a change touches Google Ads fields, enums, operation types, service paths or resource shapes:

1. check the current v25 generated client/docs;
2. add/update a test that instantiates the real `google-ads` v25 protobuf type where practical;
3. never reintroduce removed patterns guarded by `tests/test_source_guardrails.py` or `tests/test_v25_source_guardrails_extended.py`.

When the project moves to a new API version, update the explicit version and dependency constraint together with the contract suite.

## Image/network inputs

Tool modules must use the central safe public-HTTPS image fetcher. Do not add direct `urllib`, `requests`, `httpx` or socket downloads for user/model-controlled image URLs without equivalent SSRF protections.

## PII

Do not place raw Customer Match / enhanced-conversion identifiers in audit payloads or logs. Normalize/hash locally where the Google Ads contract requires hashed identifiers.

## Style and checks

Before opening or updating a PR:

```bash
make check
```

This runs dependency validation, smoke test, Ruff and pytest.

Format with:

```bash
ruff format src tests scripts
```

## Documentation

If a public tool signature or behavior changes, update `docs/TOOLS.md` and relevant examples/FAQ in the same PR.
