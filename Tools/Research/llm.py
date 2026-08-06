from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from .models import (
    EvidenceSource,
    ResearchPlan,
    SearchResult,
)


class LLMError(RuntimeError):
    pass


_PLAN_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "research_plan",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                    "minItems": 3,
                    "maxItems": 3,
                },
                "verification_targets": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                    "maxItems": 6,
                },
            },
            "required": [
                "queries",
                "verification_targets",
            ],
            "additionalProperties": False,
        },
    },
}


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start < 0 or end < start:
        raise ValueError(
            "La respuesta no contiene un objeto JSON."
        )

    payload = json.loads(
        text[start : end + 1]
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "La respuesta JSON no es un objeto."
        )

    return payload


def _clean_strings(
    value: Any,
    *,
    limit: int,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()

    placeholders = {
        "...",
        "…",
        "query",
        "search query",
        "<query>",
        "n/a",
        "none",
        "null",
    }

    cleaned: list[str] = []

    for item in value:
        if not isinstance(item, str):
            continue

        normalized = item.strip()

        if not normalized:
            continue

        if normalized.lower() in placeholders:
            continue

        if sum(
            character.isalnum()
            for character in normalized
        ) < 3:
            continue

        if normalized not in cleaned:
            cleaned.append(normalized)

        if len(cleaned) >= limit:
            break

    return tuple(cleaned)


class LlamaCppClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_seconds: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        thinking_budget_tokens: int | None,
        reasoning_effort: str | None = None,
        enable_thinking: bool | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "max_tokens": max_tokens,
        }

        if thinking_budget_tokens is not None:
            payload["thinking_budget_tokens"] = (
                thinking_budget_tokens
            )

        if reasoning_effort is not None:
            payload["reasoning_effort"] = (
                reasoning_effort
            )

        if enable_thinking is not None:
            payload["chat_template_kwargs"] = {
                "enable_thinking": enable_thinking,
            }

        if response_format is not None:
            payload["response_format"] = (
                response_format
            )

        request = Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                result = json.load(response)
        except Exception as error:
            raise LLMError(
                f"Falló la llamada al LLM: {error}"
            ) from error

        try:
            content = (
                result["choices"][0]
                ["message"]["content"]
            )
        except (
            KeyError,
            IndexError,
            TypeError,
        ) as error:
            raise LLMError(
                "El LLM devolvió una respuesta inválida."
            ) from error

        if not isinstance(content, str):
            raise LLMError(
                "El contenido devuelto por el LLM "
                "no es texto."
            )

        return content.strip()

    def plan(
        self,
        question: str,
    ) -> ResearchPlan:
        for _ in range(2):
            content = self._chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Eres el planificador de investigación "
                            "de Epsilon. "
                            "No respondas la pregunta. "
                            "No conviertas recuerdos internos en hechos. "
                            "Trata toda afirmación específica como una "
                            "hipótesis que debe verificarse. "
                            "Formula consultas neutrales: no presupongas "
                            "como verdadera ninguna relación, hecho o mecanismo "
                            "que el usuario no haya afirmado explícitamente. "
                            "Incluye una consulta general o cronológica "
                            "cuando la pregunta trate relaciones entre "
                            "personas, organizaciones o acontecimientos. "
                            "Usa el idioma que tenga más probabilidades "
                            "de recuperar fuentes primarias, aunque sea "
                            "distinto al idioma del usuario. "
                            "Devuelve SOLO un objeto JSON con esta forma: "
                            '{"queries":[],'
                            '"verification_targets":[]}. '
                            "queries debe contener exactamente 3 búsquedas "
                            "web complementarias y bien formuladas. "
                            "La primera debe cubrir el tema de forma general y neutral. "
                            "La segunda debe intentar verificar hechos, fechas, eventos "
                            "o relaciones concretas relevantes. "
                            "La tercera debe priorizar evidencia primaria, oficial, "
                            "institucional o periodística reputada. "
                            "No repitas la misma intención en varias consultas. "
                            "No introduzcas rangos temporales arbitrarios. "
                            "Si el usuario no indicó un periodo, no limites la "
                            "investigación a un rango de años. Puedes usar un año "
                            "puntual como término de búsqueda únicamente como un "
                            "hecho a verificar, nunca como una restricción "
                            "atribuida al usuario. "
                            "Si la pregunta relaciona o compara varias entidades, "
                            "mantén juntas las entidades principales en las "
                            "consultas. No desperdicies consultas investigando por "
                            "separado la biografía, discografía o historia de cada "
                            "entidad salvo que el usuario lo haya pedido. "
                            "Cuando una posible relación no esté afirmada "
                            "explícitamente por el usuario, formula tanto las "
                            "queries como los verification_targets de manera "
                            "falsable y neutral: deben permitir como resultado "
                            "que no exista evidencia de ella. "
                            "No introduzcas en las queries nombres específicos de "
                            "obras, productos, eventos, fechas o mecanismos que no "
                            "aparezcan en la pregunta original. Si pueden ser "
                            "hipótesis útiles, colócalos como verification_targets "
                            "sin presentarlos como hechos. "
                            "Las queries deben investigar primero el tema planteado "
                            "por el usuario, no asociaciones procedentes de la "
                            "memoria interna del modelo. "
                            "verification_targets puede contener hasta "
                            "6 preguntas neutrales que deban comprobarse. "
                            "No redactes como verdadero ningún hecho que "
                            "todavía deba verificarse."
                        ),
                    },
                    {
                        "role": "user",
                        "content": question,
                    },
                ],
                max_tokens=512,
                temperature=0.0,
                thinking_budget_tokens=None,
                reasoning_effort="none",
                enable_thinking=False,
                response_format=_PLAN_RESPONSE_FORMAT,
            )

            try:
                payload = _extract_json_object(
                    content
                )

                queries = _clean_strings(
                    payload.get("queries"),
                    limit=3,
                )

                targets = _clean_strings(
                    payload.get(
                        "verification_targets"
                    ),
                    limit=6,
                )

            except (
                ValueError,
                json.JSONDecodeError,
            ):
                continue

            if len(queries) != 3:
                continue

            return ResearchPlan(
                queries=queries,
                verification_targets=targets,
            )

        return ResearchPlan(
            queries=(question,),
            verification_targets=(),
        )

    def select_source_ids(
        self,
        question: str,
        results: list[SearchResult],
        *,
        max_sources: int,
    ) -> list[int]:
        candidates = []

        for index, result in enumerate(
            results[:20]
        ):
            candidates.append(
                {
                    "id": index,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet[:700],
                }
            )

        content = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Selecciona fuentes para una investigación. "
                        "No respondas la pregunta. "
                        "Selecciona la fuente que verifique de forma más "
                        "directa la consulta concreta. "
                        "Prioriza en este orden: fuentes primarias "
                        "u oficiales y documentación directa; "
                        "instituciones o periodismo reputado; "
                        "referencias especializadas; Wikipedia como "
                        "apoyo; blogs o sitios SEO solo como último "
                        "recurso. No elijas una fuente simplemente "
                        "porque confirma una hipótesis previa. "
                        "Evita duplicados y páginas irrelevantes. "
                        "Devuelve SOLO JSON con esta forma: "
                        '{"source_ids":[0,1]}. '
                        f"Selecciona como máximo {max_sources}."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "candidates": candidates,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=256,
            temperature=0.0,
            thinking_budget_tokens=128,
        )

        selected: list[int] = []

        try:
            payload = _extract_json_object(
                content
            )

            raw_ids = payload.get(
                "source_ids",
                [],
            )

            if isinstance(raw_ids, list):
                for source_id in raw_ids:
                    if (
                        isinstance(source_id, int)
                        and 0 <= source_id < len(results)
                        and source_id not in selected
                    ):
                        selected.append(
                            source_id
                        )

                    if (
                        len(selected)
                        >= max_sources
                    ):
                        break

        except (
            ValueError,
            json.JSONDecodeError,
        ):
            selected = []

        if not selected:
            selected = list(
                range(
                    min(
                        max_sources,
                        len(results),
                    )
                )
            )

        return selected

    def synthesize(
        self,
        question: str,
        plan: ResearchPlan,
        sources: list[EvidenceSource],
    ) -> str:
        evidence = [
            {
                "id": source.source_id,
                "title": source.title,
                "url": source.url,
                "text": source.text,
            }
            for source in sources
        ]

        return self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Eres Epsilon redactando el resultado final "
                        "de una investigación ya terminada. "
                        "No tienes herramientas y no puedes pedir "
                        "nuevas búsquedas. "
                        "Responde en el idioma del usuario. "
                        "Para afirmaciones específicas sobre fechas, "
                        "personas, colaboraciones, producción, "
                        "causalidad o relaciones, utiliza únicamente "
                        "la evidencia proporcionada. "
                        "Si un punto no quedó verificado, dilo en vez "
                        "de completarlo con memoria interna. "
                        "No inventes fuentes ni detalles. "
                        "La ausencia de un hecho en la evidencia "
                        "recuperada NO demuestra que el hecho no "
                        "ocurrió. En ese caso di solamente que no "
                        "pudo verificarse con las fuentes recuperadas. "
                        "Los verification_targets son hipótesis internas "
                        "del plan, no instrucciones del usuario. "
                        "Nunca afirmes que el usuario pidió un periodo, "
                        "fecha, relación, condición o alcance salvo que "
                        "aparezca explícitamente en question. "
                        "Si existe conflicto entre question y "
                        "verification_targets, question tiene prioridad. "
                        "Cita las fuentes dentro del texto como [S1], "
                        "[S2], etc. "
                        "Al final incluye una sección breve "
                        "'Fuentes' con título y URL."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "verification_targets": (
                                plan.verification_targets
                            ),
                            "evidence": evidence,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=1800,
            temperature=0.2,
            thinking_budget_tokens=None,
            reasoning_effort="none",
            enable_thinking=False,
        )
