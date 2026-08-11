from __future__ import annotations

import unittest

from Tools.Research.models import SearchResult
from Tools.Research.ranking import (
    rank_results,
    source_quality_score,
)


def result(
    title: str,
    url: str,
    snippet: str = "",
    query: str = "test query",
) -> SearchResult:
    return SearchResult(
        query=query,
        title=title,
        url=url,
        snippet=snippet,
    )


class RankingTests(unittest.TestCase):
    def test_low_quality_is_penalized(self):
        ranked = rank_results(
            [
                result(
                    "Reddit",
                    "https://reddit.com/test",
                ),
                result(
                    "Original interview",
                    "https://example.com/interview",
                    "Full interview with the artist",
                ),
            ]
        )

        self.assertEqual(
            ranked[0].title,
            "Original interview",
        )

    def test_direct_source_beats_position(self):
        ranked = rank_results(
            [
                result(
                    "Generic news article",
                    "https://example.com/news/story",
                ),
                result(
                    "1993 interview transcript",
                    "https://archive.example/interviews/1993",
                    "Complete interview transcript",
                ),
            ]
        )

        self.assertEqual(
            ranked[0].title,
            "1993 interview transcript",
        )

    def test_government_source_gets_priority(self):
        ranked = rank_results(
            [
                result(
                    "Generic",
                    "https://example.com/page",
                ),
                result(
                    "Government report",
                    "https://agency.gov/report",
                ),
            ]
        )

        self.assertEqual(
            ranked[0].title,
            "Government report",
        )

    def test_multiple_direct_signals_add_confidence(
        self,
    ):
        direct = result(
            "Official interview transcript",
            "https://example.org/interview",
            "Full interview transcript",
        )

        generic = result(
            "Article",
            "https://example.net/article",
        )

        self.assertGreater(
            source_quality_score(direct),
            source_quality_score(generic),
        )


class MusicCatalogRankingTests(
    unittest.TestCase
):
    def result(
        self,
        *,
        title,
        url,
        query,
        snippet="",
    ):
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet,
            query=query,
        )

    def test_catalog_track_beats_artist_landing_page(
        self,
    ):
        query = (
            '"Sixpence None The Richer" '
            'Spanish songs'
        )

        track = self.result(
            title=(
                "Puedo Escribir - song and lyrics "
                "by Sixpence None The Richer"
            ),
            url=(
                "https://open.spotify.com/"
                "track/example"
            ),
            query=query,
        )

        artist = self.result(
            title="Sixpence None The Richer",
            url=(
                "https://open.spotify.com/"
                "artist/example"
            ),
            query=query,
        )

        self.assertGreater(
            source_quality_score(
                track,
                position=0,
                source_mode="factual",
            ),
            source_quality_score(
                artist,
                position=0,
                source_mode="factual",
            ),
        )

    def test_catalog_track_beats_tiktok_in_factual_mode(
        self,
    ):
        query = (
            '"Sixpence None The Richer" '
            'Spanish songs'
        )

        tiktok = self.result(
            title=(
                "Sixpence None The Richer "
                "Kiss Me en Español"
            ),
            url=(
                "https://www.tiktok.com/"
                "@example/video/123"
            ),
            snippet=(
                "Spanish translation "
                "Sixpence None The Richer"
            ),
            query=query,
        )

        track = self.result(
            title=(
                "Puedo Escribir - song and lyrics "
                "by Sixpence None The Richer"
            ),
            url=(
                "https://open.spotify.com/"
                "track/example"
            ),
            snippet=(
                "Sixpence None The Richer"
            ),
            query=query,
        )

        ranked = rank_results(
            [tiktok, track],
            query,
            source_mode="factual",
        )

        self.assertEqual(
            ranked[0].url,
            track.url,
        )

    def test_catalog_boost_is_contextual(
        self,
    ):
        catalog = self.result(
            title="Example Track",
            url=(
                "https://open.spotify.com/"
                "track/example"
            ),
            query='"Example Band" Spanish songs',
        )

        generic = self.result(
            title="Example Track",
            url=(
                "https://open.spotify.com/"
                "track/example"
            ),
            query=(
                "Example Band influence "
                "on another band"
            ),
        )

        self.assertGreater(
            source_quality_score(
                catalog,
                position=0,
                source_mode="factual",
            ),
            source_quality_score(
                generic,
                position=0,
                source_mode="factual",
            ),
        )


if __name__ == "__main__":
    unittest.main()


class RelevanceRankingTests(unittest.TestCase):
    def test_relevant_article_beats_official_merch(
        self,
    ):
        question = (
            "Háblame de Sonic Youth y "
            "su relación con Nirvana"
        )

        ranked = rank_results(
            [
                result(
                    "Sonic Youth Official Merch",
                    (
                        "https://shop.example/"
                        "sonic-youth"
                    ),
                ),
                result(
                    (
                        "Sonic Youth and Nirvana "
                        "1991 tour"
                    ),
                    "https://music.example/article",
                    (
                        "Sonic Youth toured with "
                        "Nirvana in 1991."
                    ),
                ),
            ],
            question,
        )

        self.assertEqual(
            ranked[0].title,
            (
                "Sonic Youth and Nirvana "
                "1991 tour"
            ),
        )

    def test_direct_relevant_interview_wins(
        self,
    ):
        question = (
            "Sonic Youth Nirvana "
            "Kurt Cobain"
        )

        ranked = rank_results(
            [
                result(
                    "Nirvana tribute article",
                    "https://news.example/tribute",
                ),
                result(
                    (
                        "Kurt Cobain interview "
                        "transcript"
                    ),
                    (
                        "https://archive.example/"
                        "interviews/cobain"
                    ),
                    (
                        "Interview discussing "
                        "Sonic Youth and Nirvana."
                    ),
                ),
            ],
            question,
        )

        self.assertIn(
            "interview transcript",
            ranked[0].title.lower(),
        )


class StructuralQualityTests(unittest.TestCase):
    def test_commerce_is_strongly_penalized(self):
        article = result(
            "Sonic Youth and Nirvana",
            "https://music.example/article",
        )

        merch = result(
            "Sonic Youth Official Merch",
            (
                "https://shop.example/"
                "products/sonic-youth"
            ),
        )

        self.assertGreater(
            source_quality_score(
                article,
                position=0,
            ),
            source_quality_score(
                merch,
                position=0,
            ),
        )

    def test_wikipedia_does_not_receive_org_bonus(
        self,
    ):
        wiki = result(
            "Linux GNU",
            "https://en.wikipedia.org/wiki/Linux",
        )

        project = result(
            "Linux GNU",
            "https://www.debian.org/doc",
        )

        self.assertGreater(
            source_quality_score(
                project,
                position=0,
            ),
            source_quality_score(
                wiki,
                position=0,
            ),
        )



class RankingCalibrationTests(unittest.TestCase):
    def test_archive_path_is_not_direct_evidence(
        self,
    ):
        from Tools.Research.models import (
            SearchResult,
        )
        from Tools.Research.ranking import (
            direct_source_hits,
        )

        item = SearchResult(
            title="Generic archived page",
            url=(
                "https://example.com/"
                "archives/item"
            ),
            snippet="Generic information",
            query="Alpha Beta",
        )

        self.assertEqual(
            direct_source_hits(item),
            0,
        )

    def test_org_tld_is_not_authority_by_itself(
        self,
    ):
        from Tools.Research.models import (
            SearchResult,
        )
        from Tools.Research.ranking import (
            source_quality_score,
        )

        common = dict(
            title="Alpha Beta",
            snippet="Alpha Beta",
            query="Alpha Beta",
        )

        org = SearchResult(
            url="https://example.org/page",
            **common,
        )

        com = SearchResult(
            url="https://example.com/page",
            **common,
        )

        self.assertEqual(
            source_quality_score(
                org,
                position=0,
            ),
            source_quality_score(
                com,
                position=0,
            ),
        )

    def test_search_position_resets_per_query(
        self,
    ):
        from Tools.Research.models import (
            SearchResult,
        )
        from Tools.Research.ranking import (
            rank_results,
        )

        results = []

        for index in range(20):
            results.append(
                SearchResult(
                    title="Alpha Beta",
                    url=(
                        "https://example.com/"
                        f"alpha-{index}"
                    ),
                    snippet="Alpha Beta",
                    query="Alpha Beta",
                )
            )

        specific = SearchResult(
            title="Gamma Delta history",
            url=(
                "https://specific.example/"
                "history"
            ),
            snippet="Gamma Delta history",
            query="Gamma Delta history",
        )

        results.append(
            specific
        )

        ranked = rank_results(
            results,
            "unused fallback",
        )

        self.assertEqual(
            ranked[0].url,
            specific.url,
        )



class EvidenceModeRankingTests(unittest.TestCase):
    def test_factual_prefers_editorial_over_reddit(self):
        editorial = result(
            "Alpha Beta discussion",
            "https://news.example/article",
            "Alpha Beta discussion",
        )
        reddit = result(
            "Alpha Beta discussion",
            "https://reddit.com/r/test/item",
            "Alpha Beta discussion",
        )

        ranked = rank_results(
            [reddit, editorial],
            "Alpha Beta",
            source_mode="factual",
        )

        self.assertEqual(
            ranked[0].url,
            editorial.url,
        )

    def test_community_prefers_reddit(self):
        editorial = result(
            "Alpha Beta discussion",
            "https://news.example/article",
            "Alpha Beta discussion",
        )
        reddit = result(
            "Alpha Beta discussion",
            "https://reddit.com/r/test/item",
            "Alpha Beta discussion",
        )

        ranked = rank_results(
            [editorial, reddit],
            "Alpha Beta",
            source_mode="community",
        )

        self.assertEqual(
            ranked[0].url,
            reddit.url,
        )

    def test_community_score_changes_by_mode(self):
        reddit = result(
            "Alpha Beta",
            "https://reddit.com/r/test/item",
            "Alpha Beta",
        )

        factual = source_quality_score(
            reddit,
            source_mode="factual",
        )
        mixed = source_quality_score(
            reddit,
            source_mode="mixed",
        )
        community = source_quality_score(
            reddit,
            source_mode="community",
        )

        self.assertGreater(
            mixed,
            factual,
        )
        self.assertGreater(
            community,
            mixed,
        )

    def test_direct_social_source_is_not_forbidden(self):
        generic = result(
            "Alpha Beta",
            "https://news.example/article",
            "Alpha Beta",
        )
        direct = result(
            "Official interview transcript",
            "https://facebook.com/example/posts/1",
            (
                "Full interview transcript and "
                "official statement about Alpha Beta"
            ),
        )

        self.assertGreater(
            source_quality_score(
                direct,
                source_mode="factual",
            ),
            source_quality_score(
                generic,
                source_mode="factual",
            ),
        )
