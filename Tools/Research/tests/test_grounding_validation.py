from __future__ import annotations

import json
import unittest

from Tools.Research.grounding import (
    parse_grounding_report,
)
from Tools.Research.llm import (
    LLMError,
    LlamaCppClient,
)
from Tools.Research.models import (
    EvidenceSource,
    ResearchPlan,
)


class InvalidCitationClient(
    LlamaCppClient
):
    def __init__(self):
        self.calls = 0

    def _chat(
        self,
        messages,
        **kwargs,
    ):
        self.calls += 1

        return json.dumps(
            {
                "claims": [
                    {
                        "claim": "Alpha.",
                        "citations": ["S9"],
                        "verdict": "supported",
                        "reason": "Test.",
                    }
                ],
                "needs_repair": False,
            }
        )


class GroundingValidationTests(
    unittest.TestCase
):
    def test_needs_repair_is_derived(
        self,
    ):
        report = parse_grounding_report(
            {
                "claims": [
                    {
                        "claim": (
                            "Fue decisivo."
                        ),
                        "citations": [
                            "S1"
                        ],
                        "verdict": (
                            "unsupported"
                        ),
                        "reason": (
                            "No respaldado."
                        ),
                    }
                ],
                "needs_repair": False,
            }
        )

        self.assertTrue(
            report.needs_repair
        )

    def test_unknown_source_id_is_rejected(
        self,
    ):
        client = InvalidCitationClient()

        plan = ResearchPlan(
            queries=("alpha",),
            verification_targets=(),
            source_mode="factual",
        )

        sources = [
            EvidenceSource(
                source_id="S1",
                title="Example",
                url=(
                    "https://example.com"
                ),
                text="Alpha.",
            )
        ]

        with self.assertRaises(
            LLMError
        ):
            client.verify_grounding(
                "Alpha?",
                plan,
                "Alpha [S1].",
                sources,
            )

        self.assertEqual(
            client.calls,
            2,
        )


if __name__ == "__main__":
    unittest.main()
