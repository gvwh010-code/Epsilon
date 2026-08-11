from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from .grounding import (
    GroundingReport,
    answer_body,
    parse_grounding_report,
)

from .models import (
    EvidenceSource,
    ResearchPlan,
    SearchResult,
)


class LLMError(RuntimeError):
    pass


_CONTEXT_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "resolved_research_question",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                },
            },
            "required": [
                "question",
            ],
            "additionalProperties": False,
        },
    },
}


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



_GROUNDING_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "grounding_report",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "claim": {
                                "type": "string",
                            },
                            "citations": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                            "verdict": {
                                "type": "string",
                                "enum": [
                                    "supported",
                                    "partially_supported",
                                    "unsupported",
                                    "attributed_opinion",
                                ],
                            },
                            "reason": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "claim",
                            "citations",
                            "verdict",
                            "reason",
                        ],
                        "additionalProperties": False,
                    },
                    "maxItems": 40,
                },
                "needs_repair": {
                    "type": "boolean",
                },
            },
            "required": [
                "claims",
                "needs_repair",
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

    def resolve_research_question(
        self,
        question: str,
        context: list[dict[str, str]],
    ) -> str:
        """
        Convierte un follow-up en una pregunta
        autocontenida usando solo el contexto del chat.

        El contexto sirve para resolver referencias,
        nunca como evidencia factual.
        """

        question = question.strip()

        if not question or not context:
            return question

        cleaned_context = [
            {
                "role": item.get("role", ""),
                "content": item.get(
                    "content",
                    "",
                )[:4000],
            }
            for item in context[-6:]
            if (
                isinstance(item, dict)
                and item.get("role")
                in {"user", "assistant"}
                and isinstance(
                    item.get("content"),
                    str,
                )
                and item.get(
                    "content",
                    "",
                ).strip()
            )
        ]

        if not cleaned_context:
            return question

        try:
            content = self._chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Resuelves referencias "
                            "conversacionales para Epsilon "
                            "Research. No respondas la "
                            "pregunta y no investigues. "
                            "Usa el contexto únicamente "
                            "para convertir la solicitud "
                            "actual en una pregunta de "
                            "investigación autocontenida. "
                            "Resuelve pronombres, elipsis "
                            "y expresiones como 'ella', "
                            "'eso', 'la anterior', "
                            "'ese tema' o 'dime más'. "
                            "Conserva nombres, títulos y "
                            "entidades exactamente cuando "
                            "aparezcan en el contexto. "
                            "No añadas hechos, nombres ni "
                            "hipótesis que no estén en la "
                            "solicitud actual o el contexto. "
                            "Si la solicitud ya es "
                            "autocontenida, devuélvela sin "
                            "cambiar su significado. "
                            "Conserva el idioma de la "
                            "solicitud actual. "
                            "El contexto NO es evidencia "
                            "factual para la investigación. "
                            "Devuelve solo el JSON pedido."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "context": cleaned_context,
                                "current_question": question,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                max_tokens=256,
                temperature=0.0,
                thinking_budget_tokens=None,
                reasoning_effort="none",
                enable_thinking=False,
                response_format=(
                    _CONTEXT_RESPONSE_FORMAT
                ),
            )

            payload = _extract_json_object(
                content
            )

            resolved = payload.get(
                "question"
            )

            if (
                isinstance(resolved, str)
                and resolved.strip()
            ):
                return resolved.strip()

        except (
            LLMError,
            ValueError,
            json.JSONDecodeError,
        ):
            pass

        return question

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
                        "Si existe una publicación original y otra "
                    "página que solo la resume o republica, elige "
                    "la original. Prefiere fuentes independientes "
                    "entre sí para corroborar afirmaciones. "
                    "No llenes el cupo con fuentes débiles solo "
                    "para alcanzar el máximo. "
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
                        "Responde en el idioma del usuario y de forma "
                        "concisa, priorizando lo que responde directamente "
                        "a la pregunta. Usa únicamente la evidencia "
                        "proporcionada para afirmaciones verificables. "
                        "No inventes hechos, fuentes, nombres, títulos, "
                        "fechas, relaciones, mecanismos ni explicaciones. "
                        "Si algo no pudo verificarse, dilo; ausencia de "
                        "evidencia no demuestra que sea falso. "
                        "Conserva exactamente nombres propios y títulos. "
                        "Si las fuentes discrepan, indica el conflicto. "
                        "Para afirmaciones fuertes, exige evidencia directa "
                        "o corroboración independiente; si dependen de una "
                        "sola fuente secundaria, atribúyelas. "
                        "source_mode=factual: presenta como hechos solo "
                        "afirmaciones respaldadas. "
                        "source_mode=community: describe únicamente las "
                        "opiniones observadas en las fuentes y no las "
                        "generalices como consenso, mayoría o tendencia. "
                        "source_mode=mixed: separa hechos verificados de "
                        "opiniones. Los verification_targets son hipótesis "
                        "internas, no instrucciones del usuario; question "
                        "siempre tiene prioridad. "
                        "Cita cada afirmación relevante con [S1], [S2], etc. "
                        "Termina con una sección breve 'Fuentes', usando "
                        "cada identificador citado seguido de título y URL. "
                        "Evita introducciones, repeticiones y contexto que "
                        "no ayude directamente a responder la pregunta."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "source_mode": plan.source_mode,
                            "verification_targets": (
                                plan.verification_targets
                            ),
                            "evidence": evidence,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=900,
            temperature=0.2,
            thinking_budget_tokens=None,
            reasoning_effort="none",
            enable_thinking=False,
        )

    def verify_grounding(
        self,
        question: str,
        plan: ResearchPlan,
        answer: str,
        sources: list[EvidenceSource],
    ) -> GroundingReport:
        evidence = [
            {
                "id": source.source_id,
                "title": source.title,
                "text": source.text,
            }
            for source in sources
        ]

        body = answer_body(answer)

        for _ in range(2):
            content = self._chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Eres el verificador de grounding de Epsilon. "
                            "No redactes una nueva respuesta. "
                            "Analiza únicamente las afirmaciones verificables "
                            "del cuerpo de la respuesta y compáralas solo con "
                            "la evidencia proporcionada. "
                            "Descompón afirmaciones compuestas en claims "
                            "atómicos cuando puedan tener distinto soporte. "
                            "No evalúes títulos, formato, transiciones ni la "
                            "sección bibliográfica. "
                            "Para cada claim conserva únicamente los IDs de "
                            "fuente que realmente aparecen citados junto a "
                            "esa afirmación. "
                            "Usa supported solo cuando la evidencia citada "
                            "respalde directamente el claim completo. "
                            "Usa partially_supported cuando la evidencia "
                            "respalde una versión más débil o solo una parte. "
                            "Usa unsupported cuando requiera inferencia, "
                            "causalidad, importancia, mentoría, consenso u "
                            "otro detalle que la evidencia no establezca. "
                            "Usa attributed_opinion cuando la evidencia "
                            "demuestre que una persona, usuario, foro o fuente "
                            "expresó esa opinión, sin validar por ello como "
                            "hecho el contenido de la opinión. "
                            "En modo factual exige soporte factual directo. "
                            "En modo community acepta attributed_opinion "
                            "cuando la respuesta mantenga claramente la "
                            "atribución y no generalice la muestra. "
                            "En modo mixed aplica ambas reglas según el claim. "
                            "Un claim verificable sin cita debe considerarse "
                            "unsupported. "
                            "needs_repair debe ser true si existe al menos "
                            "un claim partially_supported o unsupported. "
                            "Devuelve únicamente el JSON solicitado."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": question,
                                "source_mode": (
                                    plan.source_mode
                                ),
                                "answer_body": body,
                                "evidence": evidence,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                max_tokens=1600,
                temperature=0.0,
                thinking_budget_tokens=None,
                reasoning_effort="none",
                enable_thinking=False,
                response_format=(
                    _GROUNDING_RESPONSE_FORMAT
                ),
            )

            try:
                payload = _extract_json_object(
                    content
                )

                report = parse_grounding_report(
                    payload
                )

                available_source_ids = {
                    source.source_id
                    for source in sources
                }

                if any(
                    citation
                    not in available_source_ids
                    for claim in report.claims
                    for citation in claim.citations
                ):
                    raise ValueError(
                        "El verificador citó una "
                        "fuente inexistente."
                    )

                return report
            except (
                ValueError,
                json.JSONDecodeError,
            ):
                continue

        raise LLMError(
            "El verificador de grounding devolvió "
            "una respuesta inválida."
        )
