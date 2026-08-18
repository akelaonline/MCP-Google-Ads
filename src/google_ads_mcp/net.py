"""Network helpers for safely fetching public image assets.

The MCP accepts public image URLs for several ad/asset creation tools. Those
URLs are model/user controlled, so they must not be allowed to reach loopback,
private networks, link-local ranges, or cloud metadata endpoints.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request

from .errors import GoogleAdsMcpError

_DEFAULT_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


def install_safe_urlopen() -> None:
    """Replace urllib.request.urlopen with a public-HTTPS-only wrapper.

    Existing tool modules use urllib directly. Installing this once during
    server startup protects all of those call sites, including redirects,
    without relying on every future tool to remember the SSRF checks.
    """
    if urllib.request.urlopen is not safe_public_urlopen:
        urllib.request.urlopen = safe_public_urlopen


def safe_public_urlopen(
    url,
    data=None,
    timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
    *args,
    **kwargs,
):
    """urllib-compatible opener that blocks non-public/non-HTTPS destinations."""
    if isinstance(url, urllib.request.Request):
        request = url
        target = request.full_url
    else:
        target = str(url)
        request = urllib.request.Request(target, data=data)

    _validate_public_https_url(target)
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    return opener.open(request, timeout=timeout)


def fetch_public_https_image(
    url: str,
    *,
    timeout: int = 30,
    max_bytes: int = _DEFAULT_MAX_IMAGE_BYTES,
) -> bytes:
    """Fetch an image from a public HTTPS URL with SSRF and size protections."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "google-ads-mcp/0.12"},
        method="GET",
    )
    try:
        with safe_public_urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            _validate_public_https_url(final_url)

            content_type = response.headers.get_content_type().lower()
            if content_type not in _ALLOWED_CONTENT_TYPES:
                raise GoogleAdsMcpError(
                    f"Remote URL must return a supported image Content-Type; got "
                    f"'{content_type}'."
                )

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > max_bytes:
                        raise GoogleAdsMcpError(
                            f"Remote image exceeds the {max_bytes} byte size limit."
                        )
                except ValueError:
                    pass

            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise GoogleAdsMcpError(
                    f"Remote image exceeds the {max_bytes} byte size limit."
                )
            if not data:
                raise GoogleAdsMcpError("Remote image response was empty.")
            return data
    except GoogleAdsMcpError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as ex:
        raise GoogleAdsMcpError(f"Could not fetch remote image: {ex}") from ex


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validate_public_https_url(url: str) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError as ex:
        raise GoogleAdsMcpError(f"Invalid remote asset URL: {ex}") from ex

    if parsed.scheme.lower() != "https":
        raise GoogleAdsMcpError("Remote asset URLs must use HTTPS.")
    if not parsed.hostname:
        raise GoogleAdsMcpError("Remote asset URL must include a hostname.")
    if parsed.username or parsed.password:
        raise GoogleAdsMcpError(
            "Remote asset URLs with embedded credentials are not allowed."
        )
    try:
        port = parsed.port
    except ValueError as ex:
        raise GoogleAdsMcpError(f"Invalid URL port: {ex}") from ex
    if port not in (None, 443):
        raise GoogleAdsMcpError(
            "Remote asset URLs may only use the standard HTTPS port 443."
        )

    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise GoogleAdsMcpError("Localhost remote asset URLs are not allowed.")

    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as ex:
        raise GoogleAdsMcpError(f"Could not resolve remote hostname '{host}'.") from ex

    if not addresses:
        raise GoogleAdsMcpError(f"Could not resolve remote hostname '{host}'.")

    for entry in addresses:
        ip_text = entry[4][0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError as ex:
            raise GoogleAdsMcpError(f"Invalid resolved IP address '{ip_text}'.") from ex
        if not ip.is_global:
            raise GoogleAdsMcpError(
                f"Remote hostname '{host}' resolves to a non-public address; "
                "request blocked."
            )
