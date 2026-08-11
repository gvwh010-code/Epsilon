from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import (
    urldefrag,
    urljoin,
    urlsplit,
)
from urllib.request import Request, urlopen


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class PageLink:
    url: str
    text: str


@dataclass(frozen=True)
class FetchedPage:
    title: str
    text: str
    links: tuple[PageLink, ...]


class _HTMLDocumentExtractor(HTMLParser):
    def __init__(self):
        super().__init__()

        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.raw_links: list[
            tuple[str, str]
        ] = []

        self._ignored_depth = 0
        self._title_depth = 0
        self._active_href: str | None = None
        self._active_link_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag in {
            "script",
            "style",
            "noscript",
            "svg",
        }:
            self._ignored_depth += 1
            return

        if self._ignored_depth > 0:
            return

        if tag == "title":
            self._title_depth += 1

        if tag == "a":
            attributes = dict(attrs)
            href = attributes.get("href")

            if isinstance(href, str) and href.strip():
                self._active_href = href.strip()
                self._active_link_parts = []

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in {
            "script",
            "style",
            "noscript",
            "svg",
        }:
            if self._ignored_depth > 0:
                self._ignored_depth -= 1

            return

        if self._ignored_depth > 0:
            return

        if tag == "title" and self._title_depth > 0:
            self._title_depth -= 1

        if tag == "a" and self._active_href:
            anchor = _normalize_whitespace(
                " ".join(
                    self._active_link_parts
                )
            )

            self.raw_links.append(
                (
                    self._active_href,
                    anchor,
                )
            )

            self._active_href = None
            self._active_link_parts = []

    def handle_data(self, data):
        if self._ignored_depth > 0:
            return

        text = data.strip()

        if not text:
            return

        self.parts.append(text)

        if self._title_depth > 0:
            self.title_parts.append(text)

        if self._active_href:
            self._active_link_parts.append(text)

    def text(self) -> str:
        return _normalize_whitespace(
            " ".join(self.parts)
        )

    def title(self) -> str:
        return _normalize_whitespace(
            " ".join(self.title_parts)
        )

    def links(
        self,
        base_url: str,
    ) -> tuple[PageLink, ...]:
        links: list[PageLink] = []
        seen: set[str] = set()

        for href, anchor in self.raw_links:
            absolute = urljoin(
                base_url,
                href,
            )

            absolute, _ = urldefrag(
                absolute
            )

            parts = urlsplit(absolute)

            if parts.scheme not in {
                "http",
                "https",
            }:
                continue

            if not parts.netloc:
                continue

            if absolute in seen:
                continue

            seen.add(absolute)

            links.append(
                PageLink(
                    url=absolute,
                    text=anchor,
                )
            )

            if len(links) >= 200:
                break

        return tuple(links)


def _normalize_whitespace(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


class WebFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_bytes: int = 512_000,
        max_chars: int = 24_000,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.max_chars = max_chars

    def fetch_page(
        self,
        url: str,
    ) -> FetchedPage:
        request = Request(
            url,
            headers={
                "Accept": (
                    "text/html,"
                    "text/markdown;q=0.95,"
                    "text/plain;q=0.9,"
                    "*/*;q=0.1"
                ),
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; EpsilonResearch/0.1)"
                ),
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                content_type = (
                    response.headers.get_content_type()
                    or ""
                ).lower()

                charset = (
                    response.headers.get_content_charset()
                    or "utf-8"
                )

                raw = response.read(
                    self.max_bytes + 1
                )

        except Exception as error:
            raise FetchError(
                f"No fue posible obtener {url}: {error}"
            ) from error

        raw = raw[: self.max_bytes]

        try:
            decoded = raw.decode(
                charset,
                errors="replace",
            )
        except LookupError:
            decoded = raw.decode(
                "utf-8",
                errors="replace",
            )

        title = ""
        links: tuple[PageLink, ...] = ()

        if content_type in {
            "text/plain",
            "text/markdown",
        }:
            text = _normalize_whitespace(
                decoded
            )

        elif (
            content_type == "text/html"
            or "<html" in decoded[:1000].lower()
        ):
            parser = _HTMLDocumentExtractor()

            try:
                parser.feed(decoded)
            except Exception as error:
                raise FetchError(
                    f"No fue posible analizar HTML "
                    f"de {url}: {error}"
                ) from error

            text = parser.text()
            title = parser.title()
            links = parser.links(url)

        else:
            raise FetchError(
                "Tipo de contenido no soportado "
                "en V1: "
                f"{content_type or 'desconocido'}"
            )

        if not text:
            raise FetchError(
                f"La fuente {url} no produjo "
                "texto utilizable."
            )

        return FetchedPage(
            title=title,
            text=text[: self.max_chars],
            links=links,
        )

    def fetch(self, url: str) -> str:
        return self.fetch_page(url).text
