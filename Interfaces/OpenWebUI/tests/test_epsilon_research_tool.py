from __future__ import annotations

from types import (
    ModuleType,
    SimpleNamespace,
)
import sys
import unittest
from unittest.mock import patch


fake_httpx = ModuleType("httpx")


class FakeHTTPError(Exception):
    pass


class FakeHTTPStatusError(
    FakeHTTPError
):
    def __init__(
        self,
        status_code=500,
    ):
        self.response = SimpleNamespace(
            status_code=status_code
        )


fake_httpx.HTTPError = FakeHTTPError
fake_httpx.HTTPStatusError = (
    FakeHTTPStatusError
)
fake_httpx.AsyncClient = object

sys.modules.setdefault(
    "httpx",
    fake_httpx,
)

from tools.epsilon_research import Tools


class FakeResponse:
    def __init__(
        self,
        answer: str,
        sources=None,
    ):
        self.answer = answer

        self.sources = (
            [{"url": "https://example.test"}]
            if sources is None
            else sources
        )

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "answer": self.answer,
            "sources": self.sources,
        }


class FakeAsyncClient:
    post_calls = []
    queued_responses = []

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    async def post(
        self,
        url,
        *,
        json,
    ):
        self.__class__.post_calls.append(
            {
                "url": url,
                "json": json,
            }
        )

        if self.__class__.queued_responses:
            return (
                self.__class__
                .queued_responses
                .pop(0)
            )

        return FakeResponse(
            "respuesta para: "
            + json["question"]
        )


class EpsilonResearchToolTests(
    unittest.IsolatedAsyncioTestCase
):
    def setUp(self):
        FakeAsyncClient.post_calls.clear()
        FakeAsyncClient.queued_responses.clear()

    async def test_user_prompt_is_canonical_scope(
        self,
    ):
        tools = Tools()

        request = SimpleNamespace(
            state=SimpleNamespace()
        )

        metadata = {
            "user_prompt": (
                "Sonic Youth y Nirvana"
            )
        }

        with patch(
            "tools.epsilon_research."
            "httpx.AsyncClient",
            FakeAsyncClient,
        ):
            await tools.research(
                (
                    "Sonic Youth produjo "
                    "Nevermind y DGC"
                ),
                __request__=request,
                __metadata__=metadata,
            )

        self.assertEqual(
            FakeAsyncClient.post_calls[0][
                "json"
            ],
            {
                "question": (
                    "Sonic Youth y Nirvana"
                ),
            },
        )

    async def test_success_blocks_second_post(
        self,
    ):
        tools = Tools()

        request = SimpleNamespace(
            state=SimpleNamespace()
        )

        with patch(
            "tools.epsilon_research."
            "httpx.AsyncClient",
            FakeAsyncClient,
        ):
            first = await tools.research(
                "pregunta inicial",
                __request__=request,
            )

            second = await tools.research(
                "hipótesis nueva",
                __request__=request,
            )

        self.assertEqual(
            len(FakeAsyncClient.post_calls),
            1,
        )

        self.assertEqual(
            first,
            "respuesta para: pregunta inicial",
        )

        self.assertIn(
            "ya se completó",
            second,
        )

    async def test_failure_allows_one_retry(
        self,
    ):
        tools = Tools()

        request = SimpleNamespace(
            state=SimpleNamespace()
        )

        FakeAsyncClient.queued_responses.extend(
            [
                FakeResponse(
                    "sin evidencia uno",
                    sources=[],
                ),
                FakeResponse(
                    "respuesta recuperada",
                    sources=[
                        {
                            "url": (
                                "https://example.test"
                            )
                        }
                    ],
                ),
            ]
        )

        with patch(
            "tools.epsilon_research."
            "httpx.AsyncClient",
            FakeAsyncClient,
        ):
            first = await tools.research(
                "pregunta",
                __request__=request,
            )

            second = await tools.research(
                "pregunta",
                __request__=request,
            )

            third = await tools.research(
                "otra cosa",
                __request__=request,
            )

        self.assertEqual(
            len(FakeAsyncClient.post_calls),
            2,
        )

        self.assertEqual(
            first,
            "sin evidencia uno",
        )

        self.assertEqual(
            second,
            "respuesta recuperada",
        )

        self.assertIn(
            "ya se completó",
            third,
        )

    async def test_two_failures_stop_more_posts(
        self,
    ):
        tools = Tools()

        request = SimpleNamespace(
            state=SimpleNamespace()
        )

        FakeAsyncClient.queued_responses.extend(
            [
                FakeResponse(
                    "fallo uno",
                    sources=[],
                ),
                FakeResponse(
                    "fallo dos",
                    sources=[],
                ),
            ]
        )

        with patch(
            "tools.epsilon_research."
            "httpx.AsyncClient",
            FakeAsyncClient,
        ):
            await tools.research(
                "pregunta",
                __request__=request,
            )

            second = await tools.research(
                "pregunta",
                __request__=request,
            )

            third = await tools.research(
                "pregunta",
                __request__=request,
            )

        self.assertEqual(
            len(FakeAsyncClient.post_calls),
            2,
        )

        self.assertEqual(
            second,
            "fallo dos",
        )

        self.assertEqual(
            third,
            "fallo dos",
        )

        self.assertFalse(
            hasattr(
                request.state,
                "_epsilon_research_turn_result",
            )
        )

    async def test_different_request_can_research(
        self,
    ):
        tools = Tools()

        request_a = SimpleNamespace(
            state=SimpleNamespace()
        )

        request_b = SimpleNamespace(
            state=SimpleNamespace()
        )

        with patch(
            "tools.epsilon_research."
            "httpx.AsyncClient",
            FakeAsyncClient,
        ):
            await tools.research(
                "pregunta A",
                __request__=request_a,
            )

            await tools.research(
                "pregunta B",
                __request__=request_b,
            )

        self.assertEqual(
            len(FakeAsyncClient.post_calls),
            2,
        )


if __name__ == "__main__":
    unittest.main()
