from __future__ import annotations

import ipaddress
import re
import socket
from collections import deque
from dataclasses import asdict, dataclass
from functools import lru_cache
from urllib.parse import urljoin, urlparse


_GTM_RE = re.compile(r"\bGTM-[A-Z0-9]+\b", re.IGNORECASE)
_GA4_RE = re.compile(r"\bG-[A-Z0-9]+\b", re.IGNORECASE)
_ADS_RE = re.compile(r"\bAW-[0-9]+\b", re.IGNORECASE)
_DOWNLOAD_RE = re.compile(r"\.(pdf|zip|docx?|xlsx?|pptx?|csv|rar|7z|mp4|mp3)(?:[?#]|$)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class PageAudit:
    url: str
    title: str
    forms: tuple[dict, ...]
    whatsapp_links: tuple[str, ...]
    phone_links: tuple[str, ...]
    email_links: tuple[str, ...]
    download_links: tuple[str, ...]
    internal_links: tuple[str, ...]
    gtm_ids: tuple[str, ...]
    ga4_ids: tuple[str, ...]
    ads_ids: tuple[str, ...]
    form_providers: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class UnsafeUrlError(ValueError):
    pass


@lru_cache(maxsize=512)
def _resolved_ips(hostname: str) -> tuple[str, ...]:
    rows = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    return tuple(sorted({row[4][0] for row in rows}))


def _unsafe_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("only http/https URLs are allowed")
    if not parsed.hostname:
        raise UnsafeUrlError("URL hostname is required")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("userinfo in URLs is not allowed")

    host = parsed.hostname.rstrip(".").lower()
    try:
        if _unsafe_ip(host):
            raise UnsafeUrlError(f"private or special IP is blocked: {host}")
    except ValueError:
        try:
            resolved = _resolved_ips(host)
        except socket.gaierror as exc:
            raise UnsafeUrlError(f"hostname could not be resolved: {host}") from exc
        if not resolved:
            raise UnsafeUrlError(f"hostname resolved to no addresses: {host}")
        if any(_unsafe_ip(ip) for ip in resolved):
            raise UnsafeUrlError(f"hostname resolves to a private or special IP: {host}")
    return url


def _site_key(hostname: str) -> str:
    value = hostname.lower().rstrip(".")
    return value[4:] if value.startswith("www.") else value


def _same_site(url: str, root_host: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname is not None and _site_key(parsed.hostname) == _site_key(root_host)


def _providers(html: str) -> tuple[str, ...]:
    lowered = html.lower()
    signals = {
        "contactform7": ("wpcf7",),
        "gravityforms": ("gform_wrapper", "gravityforms"),
        "wpforms": ("wpforms-form", "wpforms-container"),
        "elementor": ("elementor-form",),
        "hubspot": ("hbspt-form", "hs-form"),
        "typeform": ("typeform", "data-tf-widget"),
        "marketo": ("mktoform", "munchkin"),
        "calendly": ("calendly-inline-widget", "calendly.com"),
    }
    return tuple(sorted(name for name, needles in signals.items() if any(needle in lowered for needle in needles)))


class WebAuditor:
    """Read-only Chromium auditor. It never clicks or submits forms."""

    def __init__(self, *, headless: bool = True, nav_timeout_ms: int = 30_000) -> None:
        self.headless = headless
        self.nav_timeout_ms = nav_timeout_ms

    def audit(self, start_url: str, *, max_pages: int = 5) -> dict:
        assert_public_http_url(start_url)
        max_pages = max(1, min(max_pages, 25))
        root_host = urlparse(start_url).hostname
        assert root_host is not None

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is required for web audit; install the 'web' extra and Chromium") from exc

        pages: list[PageAudit] = []
        queue: deque[str] = deque([start_url])
        visited: set[str] = set()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context()

            def guard_route(route) -> None:
                try:
                    assert_public_http_url(route.request.url)
                except (UnsafeUrlError, ValueError):
                    route.abort()
                    return
                route.continue_()

            context.route("**/*", guard_route)
            page = context.new_page()
            page.set_default_navigation_timeout(self.nav_timeout_ms)

            while queue and len(pages) < max_pages:
                url = queue.popleft()
                normalized = url.split("#", 1)[0]
                if normalized in visited:
                    continue
                visited.add(normalized)
                assert_public_http_url(normalized)
                response = page.goto(normalized, wait_until="domcontentloaded")
                if response is None or response.status >= 400:
                    continue
                page.wait_for_timeout(750)

                extracted = page.evaluate(
                    """() => ({
                        title: document.title || '',
                        links: Array.from(document.querySelectorAll('a[href]')).map(a => a.href).filter(Boolean),
                        forms: Array.from(document.querySelectorAll('form')).map(f => ({
                            id: f.id || null,
                            name: f.getAttribute('name'),
                            action: f.action || null,
                            method: (f.method || 'get').toLowerCase(),
                            classes: f.className || ''
                        }))
                    })"""
                )
                html = page.content()
                links = tuple(dict.fromkeys(str(link) for link in extracted.get("links", [])))
                internal = tuple(link for link in links if _same_site(link, root_host))
                whatsapp = tuple(link for link in links if "wa.me/" in link.lower() or "api.whatsapp.com/" in link.lower())
                phone = tuple(link for link in links if link.lower().startswith("tel:"))
                email = tuple(link for link in links if link.lower().startswith("mailto:"))
                downloads = tuple(link for link in links if _DOWNLOAD_RE.search(link))

                audit = PageAudit(
                    url=page.url,
                    title=str(extracted.get("title", "")),
                    forms=tuple(extracted.get("forms", [])),
                    whatsapp_links=whatsapp,
                    phone_links=phone,
                    email_links=email,
                    download_links=downloads,
                    internal_links=internal,
                    gtm_ids=tuple(sorted(set(_GTM_RE.findall(html.upper())))),
                    ga4_ids=tuple(sorted(set(_GA4_RE.findall(html.upper())))),
                    ads_ids=tuple(sorted(set(_ADS_RE.findall(html.upper())))),
                    form_providers=_providers(html),
                )
                pages.append(audit)

                for link in internal:
                    candidate = link.split("#", 1)[0]
                    if candidate not in visited:
                        queue.append(candidate)

            context.close()
            browser.close()

        all_gtm = sorted({value for item in pages for value in item.gtm_ids})
        all_ga4 = sorted({value for item in pages for value in item.ga4_ids})
        all_ads = sorted({value for item in pages for value in item.ads_ids})
        providers = sorted({value for item in pages for value in item.form_providers})

        return {
            "start_url": start_url,
            "pages_scanned": len(pages),
            "tracking": {"gtm_ids": all_gtm, "ga4_ids": all_ga4, "ads_ids": all_ads},
            "opportunities": {
                "forms": sum(len(item.forms) for item in pages),
                "whatsapp_links": sum(len(item.whatsapp_links) for item in pages),
                "phone_links": sum(len(item.phone_links) for item in pages),
                "email_links": sum(len(item.email_links) for item in pages),
                "download_links": sum(len(item.download_links) for item in pages),
                "form_providers": providers,
            },
            "pages": [item.to_dict() for item in pages],
        }
