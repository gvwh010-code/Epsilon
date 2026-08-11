from __future__ import annotations

import unittest

from Tools.Research.controller import ResearchController
from Tools.Research.models import (
    ResearchPlan,
    SearchResult,
)


class FakeLLM:
    def plan(self, question):
        return ResearchPlan(
            queries=(
                "query one",
                "query two",
                "query three",
            ),
            verification_targets=(),
        )

    def synthesize(
        self,
        question,
        plan,
        sources,
    ):
        return "respuesta final"


class MultiResultSearcher:
    def search(self, query):
        slug = query.replace(" ", "-")

        return [
            SearchResult(
                title=f"{query} A",
                url=(
                    f"https://{slug}-a.example/"
                    "source"
                ),
                snippet="A",
                query=query,
            ),
            SearchResult(
                title=f"{query} B",
                url=(
                    f"https://{slug}-b.example/"
                    "source"
                ),
                snippet="B",
                query=query,
            ),
        ]

class FailingFetcher:
    def __init__(self):
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)

        if len(self.calls) <= 2:
            raise RuntimeError("403 de prueba")

        return f"contenido de {url}"


class FetchFallbackTests(unittest.TestCase):
    def test_failed_fetches_are_replaced(self):
        fetcher = FailingFetcher()

        controller = ResearchController(
            llm=FakeLLM(),
            searcher=MultiResultSearcher(),
            fetcher=fetcher,
            max_searches=3,
            max_fetches=3,
            max_fetch_attempts=5,
        )

        result = controller.run(
            (
            "Investiga Alpha Beta: historia, "
            "aportes y diferencias"
        )
        )

        self.assertEqual(
            len(fetcher.calls),
            5,
        )

        self.assertEqual(
            result.diagnostics[
                "fetch_attempts_used"
            ],
            5,
        )

        self.assertEqual(
            result.diagnostics[
                "fetches_used"
            ],
            3,
        )

        self.assertEqual(
            result.diagnostics[
                "sources_fetched"
            ],
            3,
        )

        self.assertEqual(
            len(result.sources),
            3,
        )


if __name__ == "__main__":
    unittest.main()
