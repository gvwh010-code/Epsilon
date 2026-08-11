from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from Tools.Research.models import SearchResult

from Tools.Research.search import (
    ExaClient,
    FallbackSearchClient,
    SearchError,
    SearXNGClient,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        self.close()


def response(payload):
    return FakeResponse(
        json.dumps(payload).encode("utf-8")
    )


class SearXNGClientTests(unittest.TestCase):
    def test_unresponsive_engines_with_no_results_is_error(
        self,
    ):
        client = SearXNGClient(
            "http://searxng",
        )

        payload = {
            "results": [],
            "unresponsive_engines": [
                ["brave", "too many requests"],
            ],
        }

        with patch(
            "Tools.Research.search.urlopen",
            return_value=response(payload),
        ):
            with self.assertRaises(
                SearchError
            ) as caught:
                client.search("example")

        self.assertIn(
            "brave: too many requests",
            str(caught.exception),
        )

    def test_results_are_kept_if_another_engine_failed(
        self,
    ):
        client = SearXNGClient(
            "http://searxng",
        )

        payload = {
            "results": [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "content": "Useful result",
                },
            ],
            "unresponsive_engines": [
                ["brave", "too many requests"],
            ],
        }

        with patch(
            "Tools.Research.search.urlopen",
            return_value=response(payload),
        ):
            results = client.search(
                "example"
            )

        self.assertEqual(
            len(results),
            1,
        )
        self.assertEqual(
            results[0].url,
            "https://example.com",
        )


class StubSearchClient:
    def __init__(
        self,
        name,
        *,
        results=None,
        error=None,
    ):
        self.name = name
        self.results = results or []
        self.error = error

    def search(self, query):
        if self.error is not None:
            raise self.error

        return self.results


class ExaAndFallbackTests(unittest.TestCase):
    def test_exa_uses_highlights_as_snippet(
        self,
    ):
        client = ExaClient("secret")

        payload = {
            "results": [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "highlights": [
                        "Relevant",
                        "evidence",
                    ],
                },
            ],
        }

        with patch(
            "Tools.Research.search.urlopen",
            return_value=response(payload),
        ):
            results = client.search("example")

        self.assertEqual(
            results[0].snippet,
            "Relevant evidence",
        )

    def test_primary_success_is_reported(
        self,
    ):
        result = SearchResult(
            title="Primary",
            url="https://primary.example",
            snippet="",
            query="query",
        )

        client = FallbackSearchClient(
            StubSearchClient(
                "exa",
                results=[result],
            ),
            StubSearchClient("searxng"),
        )

        client.search("query")

        self.assertEqual(
            client.last_diagnostics["provider"],
            "exa",
        )
        self.assertFalse(
            client.last_diagnostics[
                "fallback_used"
            ]
        )

    def test_fallback_usage_is_reported(
        self,
    ):
        result = SearchResult(
            title="Fallback",
            url="https://fallback.example",
            snippet="",
            query="query",
        )

        primary_error = SearchError(
            "credits exhausted",
            provider="exa",
            reason="credits_exhausted",
        )

        client = FallbackSearchClient(
            StubSearchClient(
                "exa",
                error=primary_error,
            ),
            StubSearchClient(
                "searxng",
                results=[result],
            ),
        )

        client.search("query")

        diagnostics = (
            client.last_diagnostics
        )

        self.assertEqual(
            diagnostics["provider"],
            "searxng",
        )
        self.assertTrue(
            diagnostics["fallback_used"]
        )
        self.assertEqual(
            diagnostics[
                "provider_errors"
            ][0]["reason"],
            "credits_exhausted",
        )

    def test_exa_http_402_is_credits_exhausted(
        self,
    ):
        from urllib.error import HTTPError

        client = ExaClient("secret")

        error = HTTPError(
            "https://api.exa.ai/search",
            402,
            "Payment Required",
            {},
            None,
        )

        with patch(
            "Tools.Research.search.urlopen",
            side_effect=error,
        ):
            with self.assertRaises(
                SearchError
            ) as caught:
                client.search("example")

        self.assertEqual(
            caught.exception.provider,
            "exa",
        )
        self.assertEqual(
            caught.exception.reason,
            "credits_exhausted",
        )


if __name__ == "__main__":
    unittest.main()
