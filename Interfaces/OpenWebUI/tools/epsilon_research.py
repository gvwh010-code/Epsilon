"""
title: Epsilon Research
description: Herramienta OpenWebUI para investigar y verificar información mediante Epsilon Research.
version: 0.1.0
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field


class Tools:
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

    async def research(
        self,
        question: str,
    ) -> str:
        """
        Investiga una pregunta concreta mediante Epsilon Research.

        Usa esta herramienta cuando necesites verificar hechos,
        consultar información externa o actual, o responder con
        evidencia web. No la uses cuando la respuesta pueda
        resolverse únicamente con el contexto ya disponible.

        :param question: Pregunta concreta que debe investigarse.
        :return: Respuesta sintetizada con citas y fuentes.
        """

        question = question.strip()

        if not question:
            return (
                "No se proporcionó una pregunta "
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
