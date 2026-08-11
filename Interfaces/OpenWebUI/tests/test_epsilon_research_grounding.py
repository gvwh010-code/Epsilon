from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import unittest

from functions.epsilon_research_grounding import (
    Filter,
)


class EpsilonResearchGroundingTests(
    unittest.IsolatedAsyncioTestCase
):
    async def test_without_research_does_nothing(
        self,
    ):
        filter_instance = Filter()

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": "pregunta",
                },
                {
                    "role": "assistant",
                    "content": "respuesta modelo",
                },
            ]
        }

        original = deepcopy(body)

        request = SimpleNamespace(
            state=SimpleNamespace()
        )

        result = await filter_instance.outlet(
            body,
            __request__=request,
        )

        self.assertEqual(
            result,
            original,
        )

    async def test_research_replaces_last_assistant(
        self,
    ):
        filter_instance = Filter()

        request = SimpleNamespace(
            state=SimpleNamespace(
                _epsilon_research_turn_result={
                    "question": "pregunta",
                    "answer": (
                        "respuesta grounded [S1]"
                    ),
                }
            )
        )

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": "pregunta",
                },
                {
                    "role": "assistant",
                    "content": "respuesta anterior",
                },
                {
                    "role": "user",
                    "content": "segunda pregunta",
                },
                {
                    "role": "assistant",
                    "content": (
                        "respuesta extrapolada"
                    ),
                    "output": [
                        {
                            "type": "reasoning",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": (
                                        "razonamiento interno"
                                    ),
                                },
                            ],
                        },
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": (
                                        "respuesta extrapolada"
                                    ),
                                },
                            ],
                        },
                    ],
                },
            ]
        }

        result = await filter_instance.outlet(
            body,
            __request__=request,
        )

        self.assertEqual(
            result["messages"][1]["content"],
            "respuesta anterior",
        )

        self.assertEqual(
            result["messages"][3]["content"],
            "respuesta grounded [S1]",
        )

        output = result["messages"][3][
            "output"
        ]

        self.assertEqual(
            len(output),
            2,
        )

        self.assertEqual(
            output[0]["type"],
            "reasoning",
        )

        self.assertEqual(
            output[0]["content"][0]["text"],
            "razonamiento interno",
        )

        self.assertEqual(
            output[1],
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": (
                            "respuesta grounded [S1]"
                        ),
                    },
                ],
            },
        )

    async def test_empty_answer_does_nothing(
        self,
    ):
        filter_instance = Filter()

        request = SimpleNamespace(
            state=SimpleNamespace(
                _epsilon_research_turn_result={
                    "question": "pregunta",
                    "answer": "   ",
                }
            )
        )

        body = {
            "messages": [
                {
                    "role": "assistant",
                    "content": "respuesta modelo",
                },
            ]
        }

        result = await filter_instance.outlet(
            body,
            __request__=request,
        )

        self.assertEqual(
            result["messages"][0]["content"],
            "respuesta modelo",
        )

    async def test_failure_is_grounded_too(
        self,
    ):
        filter_instance = Filter()

        request = SimpleNamespace(
            state=SimpleNamespace(
                _epsilon_research_turn_failure=(
                    "No pude obtener evidencia."
                )
            )
        )

        body = {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "respuesta inventada"
                    ),
                },
            ]
        }

        result = await filter_instance.outlet(
            body,
            __request__=request,
        )

        self.assertEqual(
            result["messages"][0]["content"],
            "No pude obtener evidencia.",
        )


if __name__ == "__main__":
    unittest.main()
