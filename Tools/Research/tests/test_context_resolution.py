from __future__ import annotations

import json
import unittest

from Tools.Research.llm import (
    LlamaCppClient,
)


class StubClient(LlamaCppClient):
    def __init__(self, response: str):
        super().__init__(
            "http://unused",
            "unused",
        )
        self.response = response
        self.calls = []

    def _chat(self, messages, **kwargs):
        self.calls.append(
            (messages, kwargs)
        )
        return self.response


class ContextResolutionTests(
    unittest.TestCase
):
    def test_resolves_followup_using_chat_context(
        self,
    ):
        client = StubClient(
            json.dumps(
                {
                    "question": (
                        "Investiga en la web más "
                        "detalles sobre la canción "
                        '"Puedo Escribir" de '
                        "Sixpence None The Richer."
                    )
                }
            )
        )

        result = (
            client.resolve_research_question(
                (
                    "investiga sobre ella "
                    "y dime más detalles"
                ),
                [
                    {
                        "role": "user",
                        "content": (
                            "¿Tiene Sixpence None "
                            "The Richer canciones "
                            "en español?"
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": (
                            "Sí, tiene una canción "
                            'titulada "Puedo Escribir".'
                        ),
                    },
                ],
            )
        )

        self.assertIn(
            "Puedo Escribir",
            result,
        )

        self.assertIn(
            "Sixpence None The Richer",
            result,
        )

    def test_invalid_resolution_falls_back(
        self,
    ):
        client = StubClient(
            "not-json"
        )

        question = (
            "Investiga la historia de systemd"
        )

        result = (
            client.resolve_research_question(
                question,
                [
                    {
                        "role": "user",
                        "content": "Hola",
                    }
                ],
            )
        )

        self.assertEqual(
            result,
            question,
        )


if __name__ == "__main__":
    unittest.main()
