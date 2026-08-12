from __future__ import annotations

import json
import sys
import unittest
from types import ModuleType
from unittest.mock import AsyncMock, patch

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


    async def test_auto_research_uses_context_for_factual_cause(
        self,
    ):
        pipe = Pipe()

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": "¿En qué año terminaron Shakira y Piqué?",
                },
                {
                    "role": "assistant",
                    "content": "La separación fue anunciada en 2022.",
                },
                {
                    "role": "user",
                    "content": "¿y por qué fue?",
                },
            ]
        }

        user = object()
        generate = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": "RESEARCH"
                        }
                    }
                ]
            }
        )

        users = ModuleType("open_webui.models.users")
        users.Users = type(
            "Users",
            (),
            {
                "get_user_by_id": AsyncMock(
                    return_value=user
                )
            },
        )

        chat = ModuleType("open_webui.utils.chat")
        chat.generate_chat_completion = generate

        fake_modules = {
            "open_webui": ModuleType("open_webui"),
            "open_webui.models": ModuleType(
                "open_webui.models"
            ),
            "open_webui.models.users": users,
            "open_webui.utils": ModuleType(
                "open_webui.utils"
            ),
            "open_webui.utils.chat": chat,
        }

        with patch.dict(
            sys.modules,
            fake_modules,
        ):
            result = await pipe._should_auto_research(
                "¿y por qué fue?",
                body,
                object(),
                {"id": "user-1"},
            )

        self.assertTrue(result)

        payload = generate.await_args.args[1]
        classifier = payload["messages"][0]["content"]

        self.assertIn(
            "causas o motivos de acontecimientos reales concretos",
            classifier,
        )

        request = json.loads(
            payload["messages"][1]["content"]
        )

        self.assertEqual(
            request["current_question"],
            "¿y por qué fue?",
        )
        self.assertEqual(
            request["context"],
            [
                {
                    "role": "user",
                    "content": (
                        "¿En qué año terminaron "
                        "Shakira y Piqué?"
                    ),
                },
            ],
        )

    async def test_research_followup_can_return_to_qwen(
        self,
    ):
        pipe = Pipe()

        pipe._should_auto_research = AsyncMock(
            return_value=False
        )
        pipe._research = AsyncMock(
            return_value="research"
        )
        pipe._forward_to_base_model = AsyncMock(
            return_value="qwen"
        )

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": "¿Tiene una canción en español?",
                },
                {
                    "role": "assistant",
                    "content": "Sí. [S1]\nFuentes",
                },
                {
                    "role": "user",
                    "content": (
                        "dejando eso de lado, "
                        "¿qué opinas de su música?"
                    ),
                },
            ]
        }

        question = (
            "dejando eso de lado, "
            "¿qué opinas de su música?"
        )

        result = await pipe.pipe(
            body,
            __metadata__={"user_prompt": question},
        )

        self.assertEqual(result, "qwen")
        pipe._research.assert_not_awaited()
        pipe._forward_to_base_model.assert_awaited_once()
        pipe._should_auto_research.assert_awaited_once_with(
            question,
            body,
            None,
            None,
        )

    async def test_research_followup_can_continue_research(
        self,
    ):
        pipe = Pipe()

        pipe._should_auto_research = AsyncMock(
            return_value=True
        )
        pipe._research = AsyncMock(
            return_value="research"
        )
        pipe._forward_to_base_model = AsyncMock(
            return_value="qwen"
        )

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": "¿Tiene una canción en español?",
                },
                {
                    "role": "assistant",
                    "content": "Sí. [S1]\nFuentes",
                },
                {
                    "role": "user",
                    "content": "¿y cuándo fue publicada?",
                },
            ]
        }

        question = "¿y cuándo fue publicada?"

        result = await pipe.pipe(
            body,
            __metadata__={"user_prompt": question},
        )

        self.assertEqual(result, "research")
        pipe._research.assert_awaited_once()
        pipe._forward_to_base_model.assert_not_awaited()
        pipe._should_auto_research.assert_awaited_once_with(
            question,
            body,
            None,
            None,
        )


if __name__ == "__main__":
    unittest.main()
