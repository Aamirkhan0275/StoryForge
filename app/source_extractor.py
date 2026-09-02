"""Safe, lightweight text extraction from public web pages."""

import ipaddress
import socket
import ssl
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener


MAX_EXTRACTED_CHARACTERS = 30_000


class PageTextParser(HTMLParser):
    """Collect visible text while ignoring markup and non-content tags."""

    ignored_tags = {"script", "style", "noscript", "svg", "nav", "footer"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.ignored_tags:
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.ignored_tags and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            clean_text = " ".join(data.split())
            if clean_text:
                self.parts.append(clean_text)

    def get_text(self) -> str:
        return "\n".join(self.parts)[:MAX_EXTRACTED_CHARACTERS]


def _validate_public_url(url: str) -> None:
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("Only valid public http or https links can be extracted.")

    try:
        resolved_addresses = socket.getaddrinfo(parsed_url.hostname, None)
    except socket.gaierror as error:
        raise ValueError("The source website could not be found.") from error

    for address in resolved_addresses:
        ip_address = ipaddress.ip_address(address[4][0])
        if not ip_address.is_global:
            raise ValueError("Private or local network links are not allowed.")


def _trusted_ssl_context() -> ssl.SSLContext:
    """Use Windows' trusted root certificates without disabling verification."""
    context = ssl.create_default_context()
    if sys.platform == "win32":
        for certificate, encoding, trust in ssl.enum_certificates("ROOT"):
            if encoding == "x509_asn":
                try:
                    context.load_verify_locations(cadata=certificate)
                except ssl.SSLError:
                    # Ignore a malformed certificate and continue using valid roots.
                    continue
    return context


def extract_page_text(url: str) -> str:
    """Download a public HTML page and return a compact text-only version."""
    _validate_public_url(url)
    request = Request(url, headers={"User-Agent": "StoryForgeResearch/0.1"})
    # StoryForge is a local app. Use the computer's direct connection rather than
    # inheriting a development-only proxy that may point at a closed local port.
    opener = build_opener(
        ProxyHandler({}),
        HTTPSHandler(context=_trusted_ssl_context()),
    )
    try:
        with opener.open(request, timeout=20) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ValueError("This source is not a standard web page.")
            html = response.read(2_000_000).decode("utf-8", errors="replace")
    except ValueError:
        raise
    except OSError as error:
        raise ValueError("StoryForge could not read this source right now.") from error

    parser = PageTextParser()
    parser.feed(html)
    extracted_text = parser.get_text()
    if len(extracted_text) < 100:
        raise ValueError("The page did not contain enough readable text.")
    return extracted_text
