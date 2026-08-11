from __future__ import annotations

import json
import unittest

from Tools.Research.llm import (
    LlamaCppClient,
)
from Tools.Research.models import (
    EvidenceSource,
    ResearchPlan,
)


class StubGroundingClient(
    LlamaCppClient
):
    def __init__(self):
        self.calls = []

    def _chat(
        self,
        messages,
        **kwargs,
    ):
        self.calls.append(
            {
                "messages": messages,
                "kwargs": kwargs,
            }
        )

        return json.dumps(
            {
                "claims": [
                    {
                        "claim": (
                            "Kim Gordon "
                            "recomendó DGC."
                        ),
                        "citations": [
                            "S1",
                        ],
                        "verdict": (
                            "supported"
                        ),
                        "reason": (
                            "La evidencia "
                            "lo indica."
                        ),
                    },
                    {
                        "claim": (
                            "La recomendación "
                            "fue decisiva."
                        ),
                        "citations": [
                            "S1",
                        ],
                        "verdict": (
                            "unsupported"
                        ),
                        "reason": (
                            "La evidencia no "
                            "establece que "
                            "fuera decisiva."
                        ),
                    },
                ],
                "needs_repair": True,
            }
        )


class LLMGroundingTests(
    unittest.TestCase
):
    def _verify(self):
        client = StubGroundingClient()

        plan = ResearchPlan(
            queries=("alpha",),
            verification_targets=(),
            source_mode="factual",
        )

        sources = [
            EvidenceSource(
                source_id="S1",
                title="Example",
                url="https://example.com",
                text=(
                    "Kim Gordon recommended "
                    "that Nirvana consider DGC."
                ),
            )
        ]

        report = client.verify_grounding(
            "What happened?",
            plan,
            (
                "Kim Gordon recomendó DGC [S1]. "
                "Fue decisivo [S1].\n\n"
                "## Fuentes\n"
                "[S1] Example"
            ),
            sources,
        )

        return client, report

    def test_returns_claim_level_report(
        self,
    ):
        _, report = self._verify()

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

    def test_uses_strict_json_schema(
        self,
    ):
        client, _ = self._verify()

        response_format = (
            client.calls[0]["kwargs"][
                "response_format"
            ]
        )

        self.assertEqual(
            response_format[
                "json_schema"
            ]["name"],
            "grounding_report",
        )

        self.assertTrue(
            response_format[
                "json_schema"
            ]["strict"],
        )

    def test_sends_body_without_sources_section(
        self,
    ):
        client, _ = self._verify()

        user_message = (
            client.calls[0][
                "messages"
            ][1]["content"]
        )

        payload = json.loads(
            user_message
        )

        self.assertEqual(
            payload["source_mode"],
            "factual",
        )

        self.assertNotIn(
            "## Fuentes",
            payload["answer_body"],
        )

        self.assertEqual(
            payload["evidence"][0][
                "id"
            ],
            "S1",
        )


if __name__ == "__main__":
    unittest.main()
