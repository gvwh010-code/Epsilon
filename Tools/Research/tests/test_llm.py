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


class ValidPlanClient(
    LlamaCppClient
):
    def __init__(self):
        super().__init__(
            "http://example.invalid",
            "test-model",
        )
        self.calls = []

    def _chat(
        self,
        *args,
        **kwargs,
    ):
        self.calls.append(kwargs)

        return (
            '{"queries":['
            '"query one",'
            '"query two",'
            '"query three"],'
            '"verification_targets":['
            '"target one"]}'
        )


class RetryPlanClient(
    LlamaCppClient
):
    def __init__(self):
        super().__init__(
            "http://example.invalid",
            "test-model",
        )
        self.calls = 0

    def _chat(
        self,
        *args,
        **kwargs,
    ):
        self.calls += 1

        if self.calls == 1:
            return (
                '{"queries":['
                '"query one",'
                '"query two"],'
                '"verification_targets":[]}'
            )

        return (
            '{"queries":['
            '"query one",'
            '"query two",'
            '"query three"],'
            '"verification_targets":['
            '"target one"]}'
        )


class LLMValidationTests(unittest.TestCase):
    def test_plan_uses_nested_json_schema(
        self,
    ):
        client = ValidPlanClient()

        plan = client.plan(
            "Pregunta de prueba"
        )

        self.assertEqual(
            len(plan.queries),
            3,
        )

        self.assertEqual(
            len(client.calls),
            1,
        )

        response_format = (
            client.calls[0][
                "response_format"
            ]
        )

        self.assertEqual(
            response_format["type"],
            "json_schema",
        )

        json_schema = response_format[
            "json_schema"
        ]

        self.assertEqual(
            json_schema["name"],
            "research_plan",
        )

        self.assertTrue(
            json_schema["strict"]
        )

        self.assertEqual(
            json_schema[
                "schema"
            ][
                "properties"
            ][
                "queries"
            ][
                "minItems"
            ],
            3,
        )

        self.assertEqual(
            json_schema[
                "schema"
            ][
                "properties"
            ][
                "queries"
            ][
                "maxItems"
            ],
            3,
        )

    def test_plan_retries_when_query_count_is_invalid(
        self,
    ):
        client = RetryPlanClient()

        plan = client.plan(
            "Pregunta de prueba"
        )

        self.assertEqual(
            client.calls,
            2,
        )

        self.assertEqual(
            plan.queries,
            (
                "query one",
                "query two",
                "query three",
            ),
        )

        self.assertEqual(
            plan.verification_targets,
            (
                "target one",
            ),
        )

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
