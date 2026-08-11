from __future__ import annotations

import unittest

from Tools.Research.fetch import PageLink
from Tools.Research.models import SearchResult
from Tools.Research.provenance import (
    provenance_candidates,
    should_replace_source,
)


class ProvenanceTests(unittest.TestCase):
    def test_prefers_external_direct_source(self):
        parent = SearchResult(
            title="Generic news article",
            url="https://news.test/story",
            snippet="",
            query="Sonic Youth Nirvana",
        )

        links = (
            PageLink(
                url=(
                    "https://news.test/"
                    "another-story"
                ),
                text="Related article",
            ),
            PageLink(
                url=(
                    "https://archive.test/"
                    "interviews/1993"
                ),
                text=(
                    "Full Kurt Cobain "
                    "interview transcript"
                ),
            ),
        )

        selected = provenance_candidates(
            parent,
            links,
            "Sonic Youth Nirvana Kurt Cobain",
            max_candidates=2,
        )

        self.assertEqual(
            len(selected),
            1,
        )

        self.assertEqual(
            selected[0].url,
            (
                "https://archive.test/"
                "interviews/1993"
            ),
        )

    def test_direct_source_can_replace_article(self):
        parent = SearchResult(
            title="Generic article",
            url="https://news.test/story",
            snippet="",
            query="query",
        )

        original = SearchResult(
            title="Interview transcript",
            url=(
                "https://archive.test/"
                "interviews/1993"
            ),
            snippet="",
            query="query",
        )

        self.assertTrue(
            should_replace_source(
                parent,
                original,
            )
        )


if __name__ == "__main__":
    unittest.main()
