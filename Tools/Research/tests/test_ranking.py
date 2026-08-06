from __future__ import annotations

import unittest

from Tools.Research.models import SearchResult
from Tools.Research.ranking import rank_results


class RankingTests(unittest.TestCase):
    def test_low_quality_source_is_penalized(
        self,
    ):
        results = [
            SearchResult(
                title="Reddit result",
                url=(
                    "https://www.reddit.com/"
                    "r/example/test"
                ),
                snippet="",
                query="test",
            ),
            SearchResult(
                title="News result",
                url=(
                    "https://www.nme.com/"
                    "news/example"
                ),
                snippet="",
                query="test",
            ),
        ]

        ranked = rank_results(results)

        self.assertEqual(
            ranked[0].title,
            "News result",
        )


if __name__ == "__main__":
    unittest.main()