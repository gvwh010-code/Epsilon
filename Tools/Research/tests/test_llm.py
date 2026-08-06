from __future__ import annotations

import unittest

from Tools.Research.llm import (
    LlamaCppClient,
    _clean_strings,
)


class PlaceholderPlanClient(
    LlamaCppClient
):
    def _chat(
        self,
        *args,
        **kwargs,
    ):
        return (
            '{"queries":["..."],'
            '"verification_targets":["..."]}'
        )


class LLMValidationTests(unittest.TestCase):
    def test_placeholders_are_rejected(self):
        result = _clean_strings(
            [
                "...",
                "…",
                "<query>",
                "query",
                "Sonic Youth Nirvana history",
            ],
            limit=3,
        )

        self.assertEqual(
            result,
            (
                "Sonic Youth Nirvana history",
            ),
        )

    def test_invalid_plan_falls_back_to_question(
        self,
    ):
        client = PlaceholderPlanClient(
            "http://example.invalid",
            "test-model",
        )

        question = (
            "Sonic Youth and Nirvana relationship"
        )

        plan = client.plan(question)

        self.assertEqual(
            plan.queries,
            (question,),
        )

        self.assertEqual(
            plan.verification_targets,
            (),
        )


if __name__ == "__main__":
    unittest.main()
