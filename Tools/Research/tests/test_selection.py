from __future__ import annotations

import unittest

from Tools.Research.models import SearchResult
from Tools.Research.selection import (
    select_candidates,
)


def result(
    query: str,
    title: str,
    url: str,
) -> SearchResult:
    return SearchResult(
        query=query,
        title=title,
        url=url,
        snippet="",
    )


class SelectionTests(unittest.TestCase):
    def test_does_not_force_query_diversity(self):
        results = [
            result(
                "q1",
                "Best source",
                "https://a.test/1",
            ),
            result(
                "q1",
                "Second source",
                "https://b.test/1",
            ),
            result(
                "q2",
                "Weak source",
                "https://c.test/1",
            ),
        ]

        selected = select_candidates(
            results,
            ["q1", "q2"],
            max_candidates=2,
        )

        self.assertEqual(
            [item.title for item in selected],
            [
                "Best source",
                "Second source",
            ],
        )

    def test_prefers_domain_diversity(self):
        results = [
            result(
                "q1",
                "A1",
                "https://a.test/1",
            ),
            result(
                "q1",
                "A2",
                "https://a.test/2",
            ),
            result(
                "q1",
                "B1",
                "https://b.test/1",
            ),
        ]

        selected = select_candidates(
            results,
            ["q1"],
            max_candidates=2,
        )

        self.assertEqual(
            [item.title for item in selected],
            ["A1", "B1"],
        )

    def test_repeats_domain_only_as_fallback(self):
        results = [
            result(
                "q1",
                "A1",
                "https://a.test/1",
            ),
            result(
                "q1",
                "A2",
                "https://a.test/2",
            ),
        ]

        selected = select_candidates(
            results,
            ["q1"],
            max_candidates=2,
        )

        self.assertEqual(
            len(selected),
            2,
        )


if __name__ == "__main__":
    unittest.main()
