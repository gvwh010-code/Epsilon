from __future__ import annotations

import unittest

from Tools.Research.models import SearchResult


def diversify(
    candidates,
    queries,
):
    diversified = []
    used_queries = set()

    for query in queries:
        for candidate in candidates:
            if (
                candidate.query == query
                and candidate.query
                not in used_queries
            ):
                diversified.append(candidate)
                used_queries.add(candidate.query)
                break

    for candidate in candidates:
        if candidate not in diversified:
            diversified.append(candidate)

    return diversified


class QueryDiversityTests(unittest.TestCase):
    def test_first_sources_cover_distinct_queries(
        self,
    ):
        queries = [
            "general",
            "interviews",
            "primary sources",
        ]

        candidates = [
            SearchResult(
                query="general",
                title="General A",
                url="https://a.test",
                snippet="",
            ),
            SearchResult(
                query="general",
                title="General B",
                url="https://b.test",
                snippet="",
            ),
            SearchResult(
                query="primary sources",
                title="Primary",
                url="https://c.test",
                snippet="",
            ),
            SearchResult(
                query="interviews",
                title="Interview",
                url="https://d.test",
                snippet="",
            ),
        ]

        result = diversify(
            candidates,
            queries,
        )

        self.assertEqual(
            [
                item.query
                for item in result[:3]
            ],
            [
                "general",
                "interviews",
                "primary sources",
            ],
        )


if __name__ == "__main__":
    unittest.main()
