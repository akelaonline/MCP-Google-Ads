from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AstroFileChange:
    path: str
    action: str
    content: str
    reason: str


def gtm_component_source() -> str:
    return """---
const gtmId = import.meta.env.PUBLIC_GTM_ID;
---

{gtmId && (
  <>
    <script is:inline define:vars={{ gtmId }}>
      {(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
      new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
      j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
      'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
      })(window,document,'script','dataLayer',gtmId)}
    </script>
    <noscript>
      <iframe
        src={`https://www.googletagmanager.com/ns.html?id=${gtmId}`}
        height="0"
        width="0"
        style="display:none;visibility:hidden"
        title="Google Tag Manager"
      />
    </noscript>
  </>
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
            path="src/components/measurement/GoogleTagManager.astro",
            action="create_or_replace",
            content=gtm_component_source(),
            reason="Managed GTM bootstrap component using PUBLIC_GTM_ID.",
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
            "Import GoogleTagManager from '../components/measurement/GoogleTagManager.astro' "
            "using the correct relative path for the chosen layout and render it once in the global layout. "
            "Do not add a second GTM bootstrap if the site audit already found one."
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
            "build succeeds",
            "exactly one GTM bootstrap is present",
            "GTM container ID matches PUBLIC_GTM_ID",
            "browser audit sees GTM after deploy",
        ],
    }
