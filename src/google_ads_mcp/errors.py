"""Turn GoogleAdsException payloads into readable strings for the LLM."""

from __future__ import annotations


class GoogleAdsMcpError(RuntimeError):
    """Raised for any user-facing tool error (bad args, API failure, etc.)."""


def format_google_ads_exception(ex) -> str:
    """ex is a google.ads.googleads.errors.GoogleAdsException."""
    lines = [f"Google Ads API request failed (request-id: {ex.request_id})."]
    try:
        for error in ex.failure.errors:
            code = error.error_code
            field = code.WhichOneof("error_code") if code else "unknown"
            lines.append(f"  - [{field}] {error.message}")
            if error.location and error.location.field_path_elements:
                path = " > ".join(
                    fp.field_name for fp in error.location.field_path_elements
                )
                lines.append(f"    field path: {path}")
    except Exception:  # pragma: no cover - defensive, keep original error visible
        lines.append(str(ex))
    return "\n".join(lines)
