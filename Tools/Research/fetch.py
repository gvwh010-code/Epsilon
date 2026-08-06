from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.request import Request, urlopen


class FetchError(RuntimeError):
    pass


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {
            "script",
            "style",
            "noscript",
            "svg",
        }:
            self._ignored_depth += 1

    def handle_endtag(self, tag):
        if (
            tag.lower()
            in {"script", "style", "noscript", "svg"}
            and self._ignored_depth > 0
        ):
            self._ignored_depth -= 1

    def handle_data(self, data):
        if self._ignored_depth == 0:
            text = data.strip()

            if text:
                self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class WebFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_bytes: int = 512_000,
        max_chars: int = 8_000,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.max_chars = max_chars

    def fetch(self, url: str) -> str:
        request = Request(
            url,
            headers={
                "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
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

                raw = response.read(self.max_bytes + 1)

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

        if content_type == "text/plain":
            text = _normalize_whitespace(decoded)

        elif (
            content_type == "text/html"
            or "<html" in decoded[:1000].lower()
        ):
            parser = _HTMLTextExtractor()

            try:
                parser.feed(decoded)
            except Exception as error:
                raise FetchError(
                    f"No fue posible analizar HTML de {url}: {error}"
                ) from error

            text = _normalize_whitespace(
                parser.text()
            )

        else:
            raise FetchError(
                f"Tipo de contenido no soportado en V1: "
                f"{content_type or 'desconocido'}"
            )

        if not text:
            raise FetchError(
                f"La fuente {url} no produjo texto utilizable."
            )

        return text[: self.max_chars]
