"""
title: Epsilon Research Grounding
description: Usa el resultado de Epsilon Research como respuesta factual final cuando Research fue utilizado.
version: 0.3.0
"""

from __future__ import annotations

from typing import Any


class Filter:
    async def outlet(
        self,
        body: dict,
        __request__: Any = None,
    ) -> dict:
        """
        Sustituye la respuesta final del modelo por la
        respuesta grounded de Epsilon Research cuando
        Research fue utilizado durante este mismo request.
        """

        if __request__ is None:
            return body

        request_state = getattr(
            __request__,
            "state",
            None,
        )

        if request_state is None:
            return body

        cached_result = getattr(
            request_state,
            "_epsilon_research_turn_result",
            None,
        )

        answer = None

        if isinstance(
            cached_result,
            dict,
        ):
            answer = cached_result.get(
                "answer"
            )

        if not (
            isinstance(answer, str)
            and answer.strip()
        ):
            answer = getattr(
                request_state,
                "_epsilon_research_turn_failure",
                None,
            )

        if not isinstance(
            answer,
            str,
        ):
            return body

        answer = answer.strip()

        if not answer:
            return body

        messages = body.get(
            "messages"
        )

        if not isinstance(
            messages,
            list,
        ):
            return body

        for message in reversed(messages):
            if not isinstance(
                message,
                dict,
            ):
                continue

            if message.get("role") != "assistant":
                continue

            # OpenWebUI v0.11 mantiene dos
            # representaciones de la respuesta:
            #
            # - content: compatibilidad/persistencia;
            # - output: representación estructurada
            #   que utiliza la interfaz para renderizar.
            #
            # Debemos actualizar ambas.
            message["content"] = answer

            output = message.get(
                "output"
            )

            if isinstance(output, list):
                preserved_output = [
                    item
                    for item in output
                    if not (
                        isinstance(item, dict)
                        and item.get("type")
                        == "message"
                    )
                ]

                preserved_output.append(
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": answer,
                            },
                        ],
                    }
                )

                message["output"] = (
                    preserved_output
                )

            print(
                "[epsilon-research-grounding] "
                "grounded response applied"
            )

            break

        return body
