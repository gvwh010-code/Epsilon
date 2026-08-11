from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from functions.epsilon_router import Pipe


class EpsilonRouterTests(
    unittest.IsolatedAsyncioTestCase
):
    def test_detects_explicit_research(
        self,
    ):
        pipe = Pipe()

        self.assertTrue(
            pipe._is_explicit_research(
                "Investiga bien Sonic Youth y Nirvana"
            )
        )

    def test_local_file_search_is_not_web_research(
        self,
    ):
        pipe = Pipe()

        self.assertFalse(
            pipe._is_explicit_research(
                "Busca en mis archivos este dato"
            )
        )

    async def test_research_bypasses_qwen(
        self,
    ):
        pipe = Pipe()

        pipe._research = AsyncMock(
            return_value="respuesta research"
        )

        pipe._forward_to_base_model = (
            AsyncMock(
                return_value="respuesta qwen"
            )
        )

        result = await pipe.pipe(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Investiga bien este tema"
                        ),
                    }
                ]
            },
            __metadata__={
                "user_prompt": (
                    "Investiga bien este tema"
                )
            },
        )

        self.assertEqual(
            result,
            "respuesta research",
        )

        pipe._research.assert_awaited_once()
        pipe._forward_to_base_model.assert_not_awaited()

    async def test_normal_turn_goes_to_qwen(
        self,
    ):
        pipe = Pipe()

        pipe._research = AsyncMock(
            return_value="respuesta research"
        )

        pipe._forward_to_base_model = (
            AsyncMock(
                return_value="respuesta qwen"
            )
        )

        result = await pipe.pipe(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Hola Epsilon",
                    }
                ]
            },
            __metadata__={
                "user_prompt": "Hola Epsilon"
            },
        )

        self.assertEqual(
            result,
            "respuesta qwen",
        )

        pipe._research.assert_not_awaited()
        pipe._forward_to_base_model.assert_awaited_once()

    def test_qwen_forwarding_removes_tooling(
        self,
    ):
        pipe = Pipe()

        body = {
            "model": "epsilon",
            "messages": [
                {
                    "role": "user",
                    "content": "Hola",
                }
            ],
            "stream": True,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "research",
                    },
                }
            ],
            "tool_ids": [
                "epsilon_research",
            ],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "functions": [
                {
                    "name": "research",
                }
            ],
            "function_call": "auto",
            "metadata": {
                "user_prompt": "Hola",
                "tool_ids": [
                    "epsilon_research",
                ],
            },
        }

        result = pipe._without_tooling(
            body
        )

        self.assertEqual(
            result["messages"],
            body["messages"],
        )
        self.assertTrue(
            result["stream"]
        )
        self.assertEqual(
            result["metadata"]["user_prompt"],
            "Hola",
        )

        forbidden = {
            "tools",
            "tool_ids",
            "tool_choice",
            "parallel_tool_calls",
            "functions",
            "function_call",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                result.keys()
            )
        )

        self.assertTrue(
            forbidden.isdisjoint(
                result["metadata"].keys()
            )
        )

        # No debe mutar el request original.
        self.assertIn(
            "tools",
            body,
        )
        self.assertIn(
            "tool_ids",
            body["metadata"],
        )

    def test_research_context_keeps_prior_turns(
        self,
    ):
        pipe = Pipe()

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "¿Tiene Sixpence None The Richer "
                        "canciones en español?"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        'Sí. Existe "Puedo Escribir".'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Investiga sobre ella "
                        "y dime más detalles"
                    ),
                },
            ]
        }

        self.assertEqual(
            pipe._research_context(body),
            [
                {
                    "role": "user",
                    "content": (
                        "¿Tiene Sixpence None The Richer "
                        "canciones en español?"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        'Sí. Existe "Puedo Escribir".'
                    ),
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
