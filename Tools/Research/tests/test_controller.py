from __future__ import annotations

import unittest

from Tools.Research.controller import (
    ResearchController,
)
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
                "query four",
            ),
            verification_targets=(
                "target",
            ),
        )

    def select_source_ids(
        self,
        question,
        results,
        *,
        max_sources,
    ):
        return [0, 1, 2, 3]

    def synthesize(
        self,
        question,
        plan,
        sources,
    ):
        return "respuesta final"


class FakeSearcher:
    def __init__(self):
        self.calls = []

    def search(self, query):
        self.calls.append(query)

        index = len(self.calls)

        return [
            SearchResult(
                title=f"Source {index}",
                url=(
                    f"https://example.com/"
                    f"{index}"
                ),
                snippet="snippet",
                query=query,
            )
        ]


class FakeFetcher:
    def __init__(self):
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        return f"contenido de {url}"


class ResearchControllerTests(
    unittest.TestCase
):
    def test_hard_budgets_are_enforced(self):
        searcher = FakeSearcher()
        fetcher = FakeFetcher()

        controller = ResearchController(
            llm=FakeLLM(),
            searcher=searcher,
            fetcher=fetcher,
            max_searches=3,
            max_fetches=3,
        )

        result = controller.run(
            "Pregunta de prueba"
        )

        self.assertEqual(
            len(searcher.calls),
            3,
        )

        self.assertEqual(
            len(fetcher.calls),
            3,
        )

        self.assertEqual(
            result.diagnostics[
                "searches_used"
            ],
            3,
        )

        self.assertEqual(
            result.diagnostics[
                "fetches_used"
            ],
            3,
        )

        self.assertEqual(
            result.answer,
            "respuesta final",
        )


if __name__ == "__main__":
    unittest.main()
