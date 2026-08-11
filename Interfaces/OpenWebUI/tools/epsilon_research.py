"""
title: Epsilon Research
description: Herramienta OpenWebUI para investigar y verificar información mediante Epsilon Research.
version: 0.3.0
"""

from __future__ import annotations

from typing import Any

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
        __request__: Any = None,
        __metadata__: Any = None,
    ) -> str:
        """
        Realiza una investigación web completa mediante Epsilon Research.

        Una llamada ya incluye planificación, múltiples búsquedas,
        selección y lectura de fuentes, verificación y síntesis.
        Normalmente debes llamar esta herramienta una sola vez por
        pregunta de investigación.

        Dentro de un mismo turno de OpenWebUI solamente la primera
        invocación ejecuta una investigación real. Las llamadas
        posteriores del mismo request se bloquean y deben reutilizar
        la evidencia obtenida en la primera llamada.

        Pasa una pregunta completa y neutral basada en la solicitud
        real del usuario. No introduzcas como hechos o hipótesis de
        búsqueda datos procedentes únicamente de tu memoria interna.

        Después de obtener el resultado, úsalo como frontera factual
        para la respuesta final. No añadas hechos externos no
        respaldados por la investigación.

        :param question: Pregunta completa y neutral que debe investigarse.
        :return: Investigación sintetizada con citas y fuentes.
        """

        question = question.strip()

        metadata = (
            __metadata__
            if isinstance(
                __metadata__,
                dict,
            )
            else {}
        )

        user_prompt = metadata.get(
            "user_prompt"
        )

        if (
            isinstance(user_prompt, str)
            and user_prompt.strip()
        ):
            research_question = (
                user_prompt.strip()
            )
        else:
            research_question = question

        if not research_question:
            return (
                "No se proporcionó una pregunta "
                "de investigación válida."
            )

        request_state = (
            getattr(
                __request__,
                "state",
                None,
            )
            if __request__ is not None
            else None
        )

        state_key = (
            "_epsilon_research_turn_result"
        )

        failure_key = (
            "_epsilon_research_turn_failure"
        )

        attempts_key = (
            "_epsilon_research_turn_attempts"
        )

        max_attempts = 2

        cached_result = (
            getattr(
                request_state,
                state_key,
                None,
            )
            if request_state is not None
            else None
        )

        if isinstance(cached_result, dict):
            cached_answer = cached_result.get(
                "answer"
            )

            if (
                isinstance(cached_answer, str)
                and cached_answer.strip()
            ):
                return (
                    "Epsilon Research ya se completó "
                    "en este turno. No se ejecutó una "
                    "nueva investigación. Usa la "
                    "evidencia obtenida en la llamada "
                    "anterior y continúa con la "
                    "respuesta final."
                )

        attempts = (
            getattr(
                request_state,
                attempts_key,
                0,
            )
            if request_state is not None
            else 0
        )

        if not isinstance(attempts, int):
            attempts = 0

        if (
            request_state is not None
            and attempts >= max_attempts
        ):
            previous_failure = getattr(
                request_state,
                failure_key,
                None,
            )

            if (
                isinstance(previous_failure, str)
                and previous_failure.strip()
            ):
                return previous_failure

            return (
                "Epsilon Research no pudo completar "
                "la investigación después de los "
                "intentos permitidos."
            )

        if request_state is not None:
            setattr(
                request_state,
                attempts_key,
                attempts + 1,
            )

        try:
            async with httpx.AsyncClient(
                timeout=self.valves.TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    self.valves.RESEARCH_URL,
                    json={
                        "question": research_question,
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

        sources = payload.get(
            "sources"
        )

        has_evidence = (
            bool(sources)
            if isinstance(sources, list)
            else True
        )

        if not has_evidence:
            if request_state is not None:
                setattr(
                    request_state,
                    failure_key,
                    answer,
                )

            return answer

        if request_state is not None:
            setattr(
                request_state,
                state_key,
                {
                    "question": research_question,
                    "answer": answer,
                },
            )

            if hasattr(
                request_state,
                failure_key,
            ):
                delattr(
                    request_state,
                    failure_key,
                )

        return answer
