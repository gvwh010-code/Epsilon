from __future__ import annotations

import unittest

from Tools.Research.grounding import (
    answer_body,
    citation_diagnostics,
    parse_grounding_report,
)


class GroundingTests(unittest.TestCase):
    def test_answer_body_excludes_sources_section(
        self,
    ):
        answer = (
            "Hecho respaldado [S1].\n\n"
            "## Fuentes\n"
            "[S1] Example https://example.com"
        )

        self.assertEqual(
            answer_body(answer),
            "Hecho respaldado [S1].",
        )

    def test_citations_in_sources_do_not_count_as_body(
        self,
    ):
        answer = (
            "Hecho respaldado [S1].\n\n"
            "Fuentes\n"
            "[S1] Uno\n"
            "[S2] Dos"
        )

        diagnostics = citation_diagnostics(
            answer,
            ("S1", "S2"),
        )

        self.assertEqual(
            diagnostics[
                "body_citations"
            ],
            ("S1",),
        )

        self.assertEqual(
            diagnostics[
                "uncited_sources"
            ],
            ("S2",),
        )

    def test_unknown_citation_is_detected(
        self,
    ):
        diagnostics = citation_diagnostics(
            "Alpha [S1]. Beta [S9].",
            ("S1", "S2"),
        )

        self.assertEqual(
            diagnostics[
                "unknown_citations"
            ],
            ("S9",),
        )

    def test_parses_claim_level_report(
        self,
    ):
        report = parse_grounding_report(
            {
                "claims": [
                    {
                        "claim": (
                            "Kim Gordon "
                            "recomendó DGC."
                        ),
                        "citations": [
                            "S4",
                        ],
                        "verdict": (
                            "supported"
                        ),
                        "reason": (
                            "La fuente lo "
                            "indica."
                        ),
                    },
                    {
                        "claim": (
                            "Fue decisivo."
                        ),
                        "citations": [
                            "[S4]",
                        ],
                        "verdict": (
                            "unsupported"
                        ),
                        "reason": (
                            "La fuente no "
                            "establece eso."
                        ),
                    },
                ],
                "needs_repair": True,
            }
        )

        self.assertEqual(
            len(report.claims),
            2,
        )

        self.assertEqual(
            len(
                report.problematic_claims
            ),
            1,
        )

        self.assertTrue(
            report.needs_repair
        )

        self.assertEqual(
            report.problematic_claims[
                0
            ].citations,
            ("S4",),
        )


if __name__ == "__main__":
    unittest.main()
