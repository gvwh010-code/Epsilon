"""
title: Epsilon Router
description: Enruta Research explícito directamente a Epsilon Research y conserva Qwen para el resto de Epsilon.
version: 0.7.0
"""

from __future__ import annotations

from typing import Any


import httpx
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        BASE_MODEL_ID: str = Field(
            default="qwen3.6-35b-a3b-test",
            description=(
                "Modelo local usado por Epsilon "
                "para conversación normal."
            ),
        )

        RESEARCH_URL: str = Field(
            default=(
                "http://epsilon-research:8080"
                "/v1/research"
            ),
            description=(
                "Endpoint interno de Epsilon Research."
            ),
        )

        TIMEOUT_SECONDS: float = Field(
            default=180.0,
            ge=1.0,
            le=600.0,
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

            if item.get("type") not in (
                "text",
                "input_text",
            ):
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

            text = cls._content_to_text(
                message.get("content")
            )

            if text:
                return text

        return ""

    @classmethod
    def _research_context(
        cls,
        body: dict,
    ) -> list[dict[str, str]]:
        """
        Devuelve los turnos recientes anteriores
        a la pregunta actual.

        Este contexto sirve únicamente para resolver
        referencias conversacionales en Research.
        """

        messages = body.get("messages")

        if not isinstance(messages, list):
            return []

        usable: list[dict[str, str]] = []

        for message in messages:
            if not isinstance(message, dict):
                continue

            role = message.get("role")

            if role not in {
                "user",
                "assistant",
            }:
                continue

            content = cls._content_to_text(
                message.get("content")
            )

            if not content:
                continue

            usable.append(
                {
                    "role": role,
                    "content": content[:4000],
                }
            )

        # El último mensaje del usuario es la
        # pregunta actual y se envía por separado.
        if (
            usable
            and usable[-1]["role"] == "user"
        ):
            usable.pop()

        return usable[-6:]


    @classmethod
    def _previous_assistant_was_research(
        cls,
        body: dict,
    ) -> bool:
        messages = body.get("messages")

        if not isinstance(messages, list):
            return False

        seen_current_user = False

        for message in reversed(messages):
            if not isinstance(message, dict):
                continue

            role = message.get("role")

            if role == "user" and not seen_current_user:
                seen_current_user = True
                continue

            if seen_current_user and role == "assistant":
                text = cls._content_to_text(
                    message.get("content")
                )

                return (
                    "[S1]" in text
                    and "Fuentes" in text
                )

        return False

    @staticmethod
    def _exits_research_mode(
        question: str,
    ) -> bool:
        normalized = " ".join(
            question.lower().split()
        )

        exits = (
            "sin investigar",
            "no investigues",
            "sin web",
            "respuesta normal",
            "gracias",
            "muchas gracias",
            "ok",
            "okay",
            "listo",
            "perfecto",
            "chao",
        )

        return normalized in exits or any(
            normalized.startswith(x + ",")
            for x in exits[:4]
        )

    @staticmethod
    def _is_explicit_research(
        question: str,
    ) -> bool:
        normalized = " ".join(
            question.lower().split()
        )

        # Evita convertir búsquedas claramente
        # locales en investigación web.
        local_hints = (
            "mis archivos",
            "archivo adjunto",
            "documento adjunto",
            "knowledge",
            "en este archivo",
            "en este documento",
        )

        external_hints = (
            "internet",
            "la web",
            "online",
            "extern",
        )

        if (
            any(
                hint in normalized
                for hint in local_hints
            )
            and not any(
                hint in normalized
                for hint in external_hints
            )
        ):
            return False

        research_hints = (
            "investiga",
            "investigar",
            "investigación",
            "investigacion",
            "busca en internet",
            "buscar en internet",
            "busca en la web",
            "buscar en la web",
            "verifica en internet",
            "verificar en internet",
            "comprueba en internet",
            "comprobar en internet",
            "search the web",
            "search online",
            "look up online",
            "research this",
            "do research",
        )

        return any(
            hint in normalized
            for hint in research_hints
        )

    async def _should_auto_research(
        self,
        question: str,
        __request__: Any,
        __user__: Any,
    ) -> bool:
        """Decide si conviene verificar externamente."""

        if (
            __request__ is None
            or not isinstance(__user__, dict)
        ):
            return False

        from open_webui.models.users import Users
        from open_webui.utils.chat import (
            generate_chat_completion,
        )

        user_id = __user__.get("id")

        if not user_id:
            return False

        user = await Users.get_user_by_id(
            user_id
        )

        if user is None:
            return False

        payload = {
            "model": self.valves.BASE_MODEL_ID,
            "stream": False,
            "temperature": 0,
            "max_tokens": 8,
            "reasoning_effort": "none",
            "chat_template_kwargs": {
                "enable_thinking": False,
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Clasifica la solicitud del usuario. "
                        "Responde exclusivamente RESEARCH o QWEN. "
                        "Usa RESEARCH cuando responder correctamente "
                        "dependa de verificar hechos específicos del "
                        "mundo real: personas, organizaciones, obras, "
                        "discografías, catálogos, fechas, sucesos, "
                        "productos, versiones, disponibilidad, datos "
                        "actuales o afirmaciones concretas cuya certeza "
                        "no deba asumirse de memoria. "
                        "Usa QWEN para conversación, creatividad, "
                        "razonamiento, explicación conceptual estable, "
                        "matemática, programación o redacción que no "
                        "requiera comprobar hechos externos. "
                        "Ante duda factual razonable, usa RESEARCH."
                    ),
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
        }

        try:
            result = await generate_chat_completion(
                __request__,
                payload,
                user,
                bypass_system_prompt=True,
            )

            content = (
                result["choices"][0]
                ["message"]["content"]
            )

            return (
                isinstance(content, str)
                and content.strip().upper()
                == "RESEARCH"
            )
        except Exception as error:
            print(
                "[epsilon-router] "
                f"auto-route fallback: {error}"
            )
            return False

    async def _research(
        self,
        question: str,
        body: dict,
    ) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self.valves.TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    self.valves.RESEARCH_URL,
                    json={
                        "question": question,
                        "context": (
                            self._research_context(
                                body
                            )
                        ),
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
                f"Epsilon Research: {error}"
            )

        except ValueError:
            return (
                "Epsilon Research devolvió "
                "una respuesta JSON inválida."
            )

        if not isinstance(payload, dict):
            return (
                "Epsilon Research devolvió "
                "una respuesta inesperada."
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
                "Epsilon Research devolvió "
                "una respuesta vacía."
            )

        return answer

    @staticmethod
    def _without_tooling(
        body: dict,
    ) -> dict:
        """Copia el request sin herramientas heredadas."""

        tool_keys = {
            "tools",
            "tool_ids",
            "tool_choice",
            "parallel_tool_calls",
            "functions",
            "function_call",
        }

        forwarded = {
            key: value
            for key, value in body.items()
            if key not in tool_keys
        }

        metadata = forwarded.get("metadata")

        if isinstance(metadata, dict):
            forwarded["metadata"] = {
                key: value
                for key, value in metadata.items()
                if key not in tool_keys
            }

        return forwarded

    async def _forward_to_base_model(
        self,
        body: dict,
        __request__: Any,
        __user__: Any,
    ):
        from open_webui.models.users import Users
        from open_webui.utils.chat import (
            generate_chat_completion,
        )

        if not isinstance(__user__, dict):
            raise RuntimeError(
                "No se recibió un usuario válido."
            )

        user_id = __user__.get("id")

        if not user_id:
            raise RuntimeError(
                "No se recibió el ID del usuario."
            )

        user = await Users.get_user_by_id(
            user_id
        )

        if user is None:
            raise RuntimeError(
                "No pude resolver el usuario."
            )

        forwarded = self._without_tooling(
            body
        )

        forwarded["model"] = (
            self.valves.BASE_MODEL_ID
        )

        return await generate_chat_completion(
            __request__,
            forwarded,
            user,
        )

    async def pipe(
        self,
        body: dict,
        __user__: Any = None,
        __request__: Any = None,
        __metadata__: Any = None,
        __task__: Any = None,
        __event_emitter__: Any = None,
    ):
        # Las tareas internas de OpenWebUI no son
        # solicitudes Research del usuario.
        if __task__ is not None:
            return await self._forward_to_base_model(
                body,
                __request__,
                __user__,
            )

        metadata = (
            __metadata__
            if isinstance(__metadata__, dict)
            else {}
        )

        original_prompt = metadata.get(
            "user_prompt"
        )

        if (
            isinstance(original_prompt, str)
            and original_prompt.strip()
        ):
            question = original_prompt.strip()
        else:
            question = self._latest_user_question(
                body
            )

        continue_research = (
            question
            and self._previous_assistant_was_research(
                body
            )
            and not self._exits_research_mode(
                question
            )
        )

        explicit_research = (
            question
            and self._is_explicit_research(
                question
            )
        )

        auto_research = False

        if (
            question
            and not explicit_research
            and not continue_research
            and not self._exits_research_mode(
                question
            )
        ):
            auto_research = (
                await self._should_auto_research(
                    question,
                    __request__,
                    __user__,
                )
            )

        if (
            question
            and (
                explicit_research
                or continue_research
                or auto_research
            )
        ):
            if callable(__event_emitter__):
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": (
                                "Investigando con "
                                "Epsilon Research"
                            ),
                            "done": False,
                        },
                    }
                )

            answer = await self._research(
                question,
                body,
            )

            if callable(__event_emitter__):
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": (
                                "Investigación terminada"
                            ),
                            "done": True,
                        },
                    }
                )

            print(
                "[epsilon-router] "
                "route=research"
            )

            return answer

        print(
            "[epsilon-router] "
            "route=qwen"
        )

        return await self._forward_to_base_model(
            body,
            __request__,
            __user__,
        )
