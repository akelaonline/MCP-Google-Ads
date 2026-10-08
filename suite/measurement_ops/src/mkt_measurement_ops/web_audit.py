from __future__ import annotations

import ipaddress
import re
import socket
from collections import deque
from dataclasses import asdict, dataclass
from functools import lru_cache
from urllib.parse import urlparse


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


def _form_haystack(form: dict) -> str:
    fields = form.get("fields") or []
    pieces = [
        str(form.get("id") or ""),
        str(form.get("name") or ""),
        str(form.get("action") or ""),
        str(form.get("classes") or ""),
        str(form.get("text") or ""),
        " ".join(str(item) for item in form.get("buttons") or []),
    ]
    for field in fields:
        pieces.extend(
            [
                str(field.get("type") or ""),
                str(field.get("name") or ""),
                str(field.get("id") or ""),
                str(field.get("placeholder") or ""),
                str(field.get("label") or ""),
                str(field.get("aria_label") or ""),
            ]
        )
    return " ".join(pieces).lower()


def classify_form(form: dict) -> str:
    """Conservative form-intent classifier; unknown forms stay 'other'."""
    fields = form.get("fields") or []
    field_types = {str(field.get("type") or "").lower() for field in fields}
    field_names = {str(field.get("name") or "").lower() for field in fields}
    haystack = _form_haystack(form)

    if "search" in field_types or field_names.intersection({"s", "q", "search", "query"}):
        return "search"
    if re.search(r"\b(buscar|búsqueda|search)\b", haystack):
        return "search"

    has_password = "password" in field_types
    if has_password:
        if re.search(r"\b(registr|register|sign\s?up|crear\s+cuenta|create\s+account)\b", haystack):
            return "signup"
        return "login"

    if re.search(r"\b(newsletter|suscrib|subscribe|mailing\s+list)\b", haystack):
        return "newsletter"

    has_email = "email" in field_types or any("email" in name or "mail" in name for name in field_names)
    has_phone = "tel" in field_types or any(
        token in name for name in field_names for token in ("phone", "telefono", "teléfono", "whatsapp")
    )
    has_message = "textarea" in field_types or any(
        token in name for name in field_names for token in ("message", "mensaje", "consulta", "comments")
    )
    lead_language = bool(
        re.search(
            r"\b(contact|contacto|consulta|consultar|presupuesto|cotiz|quote|enquiry|inquiry|"
            r"mensaje|message|hablar|asesor|demo|solicitar|request|enviar|send)\b",
            haystack,
        )
    )
    if (has_email or has_phone) and (has_message or lead_language):
        return "lead"

    return "other"


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
                            classes: typeof f.className === 'string' ? f.className : '',
                            text: (f.innerText || '').slice(0, 1500),
                            buttons: Array.from(f.querySelectorAll('button,input[type=submit]'))
                                .map(b => (b.innerText || b.value || b.getAttribute('aria-label') || '').trim())
                                .filter(Boolean)
                                .slice(0, 20),
                            fields: Array.from(f.querySelectorAll('input,textarea,select'))
                                .map(el => {
                                    let label = '';
                                    try {
                                        const wrapping = el.closest('label');
                                        const explicit = el.id ? f.querySelector('label[for="' + CSS.escape(el.id) + '"]') : null;
                                        label = ((wrapping || explicit)?.innerText || '').trim();
                                    } catch (_) {}
                                    return {
                                        type: (el.getAttribute('type') || el.tagName || '').toLowerCase(),
                                        name: el.getAttribute('name'),
                                        id: el.id || null,
                                        placeholder: el.getAttribute('placeholder'),
                                        aria_label: el.getAttribute('aria-label'),
                                        label
                                    };
                                })
                                .slice(0, 60)
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

                providers_on_page = _providers(html)
                classified_forms = []
                for raw_form in extracted.get("forms", []):
                    form = dict(raw_form)
                    form["purpose"] = classify_form(form)
                    classified_forms.append(form)

                audit = PageAudit(
                    url=page.url,
                    title=str(extracted.get("title", "")),
                    forms=tuple(classified_forms),
                    whatsapp_links=whatsapp,
                    phone_links=phone,
                    email_links=email,
                    download_links=downloads,
                    internal_links=internal,
                    gtm_ids=tuple(sorted(set(_GTM_RE.findall(html.upper())))),
                    ga4_ids=tuple(sorted(set(_GA4_RE.findall(html.upper())))),
                    ads_ids=tuple(sorted(set(_ADS_RE.findall(html.upper())))),
                    form_providers=providers_on_page,
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
        form_candidates: list[dict] = []
        for item in pages:
            provider = item.form_providers[0] if len(item.form_providers) == 1 else None
            for form in item.forms:
                form_candidates.append(
                    {
                        "page_url": item.url,
                        "form_id": form.get("id"),
                        "form_name": form.get("name"),
                        "purpose": form.get("purpose", "other"),
                        "provider": provider,
                    }
                )
        purposes = {
            purpose: sum(1 for form in form_candidates if form["purpose"] == purpose)
            for purpose in ("lead", "newsletter", "signup", "login", "search", "other")
        }

        return {
            "start_url": start_url,
            "pages_scanned": len(pages),
            "tracking": {"gtm_ids": all_gtm, "ga4_ids": all_ga4, "ads_ids": all_ads},
            "opportunities": {
                "forms": len(form_candidates),
                "lead_forms": purposes["lead"],
                "newsletter_forms": purposes["newsletter"],
                "signup_forms": purposes["signup"],
                "login_forms": purposes["login"],
                "search_forms": purposes["search"],
                "other_forms": purposes["other"],
                "form_candidates": form_candidates,
                "whatsapp_links": sum(len(item.whatsapp_links) for item in pages),
                "phone_links": sum(len(item.phone_links) for item in pages),
                "email_links": sum(len(item.email_links) for item in pages),
                "download_links": sum(len(item.download_links) for item in pages),
                "form_providers": providers,
            },
            "pages": [item.to_dict() for item in pages],
        }
