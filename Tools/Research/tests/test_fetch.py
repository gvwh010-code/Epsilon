from __future__ import annotations

import unittest
from unittest.mock import patch

from Tools.Research.fetch import WebFetcher


class FakeHeaders:
    def __init__(
        self,
        content_type: str,
        charset: str = "utf-8",
    ):
        self.content_type = content_type
        self.charset = charset

    def get_content_type(self):
        return self.content_type

    def get_content_charset(self):
        return self.charset


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        content_type: str,
    ):
        self.body = body
        self.headers = FakeHeaders(
            content_type
        )

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False

    def read(self, size=-1):
        if size < 0:
            return self.body

        return self.body[:size]


class WebFetcherTests(unittest.TestCase):
    def test_markdown_content_type_is_accepted(
        self,
    ):
        captured = {}

        def fake_urlopen(
            request,
            timeout,
        ):
            captured["accept"] = (
                request.get_header(
                    "Accept"
                )
            )

            return FakeResponse(
                (
                    "# Open WebUI\n\n"
                    "A **self-hosted** AI platform."
                ).encode("utf-8"),
                "text/markdown",
            )

        with patch(
            "Tools.Research.fetch.urlopen",
            side_effect=fake_urlopen,
        ):
            text = WebFetcher().fetch(
                "https://example.test/index.md"
            )

        self.assertIn(
            "text/markdown",
            captured["accept"],
        )

        self.assertEqual(
            text,
            (
                "# Open WebUI "
                "A **self-hosted** AI platform."
            ),
        )


if __name__ == "__main__":
    unittest.main()


class WebFetcherLinksTests(unittest.TestCase):
    def test_html_extracts_title_and_links(self):
        html = b"""
        <html>
          <head>
            <title>Original Interview</title>
          </head>
          <body>
            <p>Evidence text</p>
            <a href="/interviews/1993">
              Full interview transcript
            </a>
          </body>
        </html>
        """

        with patch(
            "Tools.Research.fetch.urlopen",
            return_value=FakeResponse(
                html,
                "text/html",
            ),
        ):
            page = WebFetcher().fetch_page(
                "https://archive.test/article"
            )

        self.assertEqual(
            page.title,
            "Original Interview",
        )

        self.assertEqual(
            page.links[0].url,
            "https://archive.test/interviews/1993",
        )

        self.assertEqual(
            page.links[0].text,
            "Full interview transcript",
        )
