"""
title: Epsilon Research
description: Adaptador OpenWebUI para el servicio local Epsilon Research.
version: 0.1.0
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        RESEARCH_URL: str = Field(
            default=(
                "http://epsilon-research:8080"
                "/v1/research"
            ),
            description=(
                "Endpoint interno del servicio "
                "Epsilon Research."
            ),
        )

        TIMEOUT_SECONDS: float = Field(
            default=180.0,
            ge=1.0,
            le=600.0,
            description=(
                "Tiempo máximo de una investigación."
            ),
        )

    def __init__(self):
        self.valves = self.Valves()

    @staticmethod
    def _content_to_text(
        content: Any,
    ) -> str:
        if isinstance(content, str):
            return content.strip()

        if not isinstance(content, list):
            return ""

        parts: list[str] = []

        for item in content:
            if not isinstance(item, dict):
                continue

            if item.get("type") != "text":
                continue

            text = item.get("text")

            if isinstance(text, str):
                text = text.strip()

                if text:
                    parts.append(text)

        return "\n".join(parts)

    @classmethod
    def _latest_user_question(
        cls,
        body: dict,
    ) -> str:
        messages = body.get("messages")

        if not isinstance(messages, list):
            return ""

        for message in reversed(messages):
            if not isinstance(message, dict):
                continue

            if message.get("role") != "user":
                continue

            question = cls._content_to_text(
                message.get("content")
            )

            if question:
                return question

        return ""

    async def pipe(
        self,
        body: dict,
    ) -> str:
        question = self._latest_user_question(
            body
        )

        if not question:
            return (
                "No pude identificar una pregunta "
                "de investigación válida."
            )

        try:
            async with httpx.AsyncClient(
                timeout=self.valves.TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    self.valves.RESEARCH_URL,
                    json={
                        "question": question,
                    },
                )

                response.raise_for_status()

                payload = response.json()

        except httpx.HTTPStatusError as error:
            return (
                "Epsilon Research respondió con "
                f"HTTP {error.response.status_code}."
            )

        except httpx.HTTPError as error:
            return (
                "No pude comunicarme con "
                "Epsilon Research: "
                f"{error}"
            )

        except ValueError:
            return (
                "Epsilon Research devolvió una "
                "respuesta JSON inválida."
            )

        if not isinstance(payload, dict):
            return (
                "Epsilon Research devolvió una "
                "respuesta inesperada."
            )

        answer = payload.get("answer")

        if not isinstance(answer, str):
            return (
                "Epsilon Research no devolvió "
                "una respuesta textual."
            )

        answer = answer.strip()

        if not answer:
            return (
                "Epsilon Research devolvió una "
                "respuesta vacía."
            )

        return answer
