# MKT Measurement Ops

Measurement Ops is the orchestration layer for the Google Marketing suite.

It intentionally lives beside the Google Ads MCP instead of inside its runtime.
The product is one suite; the providers remain isolated so Ads, GTM, GA4, web
audit and site deployment can evolve and fail independently.

## v0.1 architecture

```text
LLM / MCP client
       |
Measurement Ops
       |
+------+------+------+------+------+
| Ads  | GTM  | GA4  | Audit| Site |
+------+------+------+------+------+
                           |
                  +--------+--------+
                  |                 |
              WordPress            Astro
              adapter              GitHub adapter
```

## Operating contract

1. Audit before changing anything.
2. Prefer GTM workspaces and Git branches over direct production edits.
3. Never store site, Google or Git credentials in the Site Registry.
4. Never publish GTM or deploy a site without explicit confirmation.
5. Every implementation ends with runtime verification, not merely API success.
6. A production result must include evidence: dataLayer/event observation,
   GA4 request verification, consent state where relevant, and target IDs.

## Initial providers

- Google Ads: existing MCP provider in this repository.
- GTM: adapter to be built against Google Tag Manager API v2, using the
  Sprawz/Paolo project as a coverage reference.
- GA4: Admin + Data API adapter.
- Web Audit: browser-based audit and verification, informed by Samarth's
  crawler/tag-suggestion/verification architecture.
- WordPress: controlled adapter; no arbitrary theme editing in the normal path.
- Astro: GitHub branch/build/PR/deploy adapter.

## Site Registry

The registry maps one business site to the systems needed to operate measurement:
domain, platform, deployment mode, GTM account/container, GA4 property, Ads
customer and repository/WordPress endpoint.

It stores routing metadata only. Secrets stay in the provider credential stores.

## POC acceptance

The architecture is accepted only after two real end-to-end pilots:

- one WordPress site;
- one Astro site.

Each pilot must support: audit -> measurement plan -> GTM workspace -> site
change if needed -> browser verification -> explicit publish/deploy approval ->
post-production verification.
