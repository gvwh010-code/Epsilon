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
    def __init__(self):
        self.selection_calls = []

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
        self.selection_calls.append(
            {
                "question": question,
                "urls": [
                    result.url
                    for result in results
                ],
                "max_sources": max_sources,
            }
        )

        # Elegimos deliberadamente el tercer
        # resultado primero para verificar que
        # el controller respeta al selector.
        return [2, 0, 1, 3]

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

        llm = FakeLLM()

        controller = ResearchController(
            llm=llm,
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
            len(llm.selection_calls),
            1,
        )

        self.assertEqual(
            fetcher.calls[0],
            "https://example.com/3",
        )

        self.assertTrue(
            result.diagnostics[
                "source_selector_used"
            ],
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
