from __future__ import annotations

import unittest

from Tools.Research.passages import (
    select_relevant_passages,
)


class PassageTests(unittest.TestCase):
    def test_prefers_relevant_chunk(self):
        text = (
            ("contenido irrelevante " * 100)
            + (
                "Sonic Youth Nirvana "
                "Thurston Moore " * 30
            )
            + ("otro contenido " * 100)
        )

        result = select_relevant_passages(
            "Sonic Youth y Nirvana",
            text,
            chunk_chars=500,
            overlap_chars=50,
            max_passages=1,
        )

        self.assertIn("Sonic Youth", result)
        self.assertIn("Nirvana", result)

    def test_limits_passages(self):
        result = select_relevant_passages(
            "alpha beta",
            "alpha beta " * 1000,
            chunk_chars=200,
            overlap_chars=0,
            max_passages=2,
        )

        self.assertLessEqual(
            len(result),
            402,
        )



class PassageAccentRegressionTests(
    unittest.TestCase
):
    def test_unaccented_query_matches_accented_source(
        self,
    ):
        from Tools.Research.passages import (
            select_relevant_passages,
        )

        first = "Shakira ".ljust(
            80,
            "x",
        )
        second = (
            "Shakira y Gerard Piqué terminó "
            "en junio de 2022."
        ).ljust(
            80,
            "x",
        )

        selected = select_relevant_passages(
            "en que año termino shakira con pique?",
            first + second,
            chunk_chars=80,
            overlap_chars=0,
            max_passages=1,
        )

        self.assertIn(
            "junio de 2022",
            selected,
        )


if __name__ == "__main__":
    unittest.main()
