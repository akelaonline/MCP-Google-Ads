from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AstroFileChange:
    path: str
    action: str
    content: str
    reason: str


def gtm_head_component_source() -> str:
    return """---
const gtmId = import.meta.env.PUBLIC_GTM_ID;
---

{gtmId && (
  <script is:inline define:vars={{ gtmId }}>
    (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer',gtmId);
  </script>
)}
"""


def gtm_body_component_source() -> str:
    return """---
const gtmId = import.meta.env.PUBLIC_GTM_ID;
---

{gtmId && (
  <noscript>
    <iframe
      src={`https://www.googletagmanager.com/ns.html?id=${gtmId}`}
      height="0"
      width="0"
      style="display:none;visibility:hidden"
      title="Google Tag Manager"
    />
  </noscript>
)}
"""


def datalayer_helper_source() -> str:
    return """export type DataLayerPayload = {
  event: string;
  [key: string]: string | number | boolean | null | undefined;
};

declare global {
  interface Window {
    dataLayer?: DataLayerPayload[];
  }
}

export function pushDataLayer(payload: DataLayerPayload): void {
  if (typeof window === "undefined") return;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(payload);
}
"""


def build_astro_measurement_plan(*, layout_path: str = "src/layouts/Layout.astro") -> dict:
    changes = (
        AstroFileChange(
            path="src/components/measurement/GoogleTagManagerHead.astro",
            action="create_or_replace",
            content=gtm_head_component_source(),
            reason="Managed GTM bootstrap script for the document head.",
        ),
        AstroFileChange(
            path="src/components/measurement/GoogleTagManagerBody.astro",
            action="create_or_replace",
            content=gtm_body_component_source(),
            reason="Managed GTM noscript iframe for the start of the document body.",
        ),
        AstroFileChange(
            path="src/lib/measurement.ts",
            action="create_or_replace",
            content=datalayer_helper_source(),
            reason="Typed dataLayer helper for events that cannot be observed reliably from GTM alone.",
        ),
    )
    return {
        "environment": {"PUBLIC_GTM_ID": "GTM-XXXXXXX"},
        "layout_path": layout_path,
        "layout_instruction": (
            "Import GoogleTagManagerHead and render it once inside <head>. "
            "Import GoogleTagManagerBody and render it once immediately after <body>. "
            "Use the correct relative paths for the chosen global layout. "
            "Do not install either component if the site audit already found an existing GTM bootstrap."
        ),
        "changes": [
            {
                "path": change.path,
                "action": change.action,
                "content": change.content,
                "reason": change.reason,
            }
            for change in changes
        ],
        "verification": [
            "Astro build succeeds",
            "exactly one GTM bootstrap script is present",
            "exactly one GTM noscript iframe is present",
            "GTM container ID matches PUBLIC_GTM_ID",
            "browser audit sees GTM after deploy",
        ],
    }
