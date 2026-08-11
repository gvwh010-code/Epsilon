from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


_VALID_VERDICTS = {
    "supported",
    "partially_supported",
    "unsupported",
    "attributed_opinion",
}

_CITATION_RE = re.compile(
    r"\[(S[1-9][0-9]*)\]"
)

_SOURCES_HEADING_RE = re.compile(
    r"(?im)^"
    r"\s*(?:#{1,6}\s*)?"
    r"(?:\*\*)?"
    r"(?:fuentes|sources)"
    r"(?:\*\*)?"
    r"\s*:?\s*$"
)


@dataclass(frozen=True)
class GroundingClaim:
    claim: str
    citations: tuple[str, ...]
    verdict: str
    reason: str


@dataclass(frozen=True)
class GroundingReport:
    claims: tuple[GroundingClaim, ...]
    needs_repair: bool

    @property
    def problematic_claims(
        self,
    ) -> tuple[GroundingClaim, ...]:
        return tuple(
            claim
            for claim in self.claims
            if claim.verdict in {
                "partially_supported",
                "unsupported",
            }
        )

    def verdict_counts(
        self,
    ) -> dict[str, int]:
        counts = {
            verdict: 0
            for verdict in _VALID_VERDICTS
        }

        for claim in self.claims:
            counts[claim.verdict] += 1

        return counts


def answer_body(answer: str) -> str:
    match = _SOURCES_HEADING_RE.search(
        answer
    )

    if match is None:
        return answer.strip()

    return answer[:match.start()].strip()


def extract_citation_ids(
    text: str,
) -> tuple[str, ...]:
    found: list[str] = []

    for source_id in _CITATION_RE.findall(
        text
    ):
        if source_id not in found:
            found.append(source_id)

    return tuple(found)


def citation_diagnostics(
    answer: str,
    available_source_ids: Iterable[str],
) -> dict[str, tuple[str, ...]]:
    available = tuple(
        dict.fromkeys(
            available_source_ids
        )
    )

    body_ids = extract_citation_ids(
        answer_body(answer)
    )

    all_ids = extract_citation_ids(
        answer
    )

    unknown = tuple(
        source_id
        for source_id in all_ids
        if source_id not in available
    )

    uncited = tuple(
        source_id
        for source_id in available
        if source_id not in body_ids
    )

    return {
        "body_citations": body_ids,
        "all_citations": all_ids,
        "unknown_citations": unknown,
        "uncited_sources": uncited,
    }


def _normalize_source_id(
    value: Any,
) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()

    if normalized.startswith("["):
        normalized = normalized.lstrip("[")

    if normalized.endswith("]"):
        normalized = normalized.rstrip("]")

    if not re.fullmatch(
        r"S[1-9][0-9]*",
        normalized,
    ):
        return None

    return normalized


def parse_grounding_report(
    payload: dict[str, Any],
) -> GroundingReport:
    claims_raw = payload.get("claims")
    needs_repair = payload.get(
        "needs_repair"
    )

    if not isinstance(claims_raw, list):
        raise ValueError(
            "claims debe ser una lista."
        )

    if not isinstance(
        needs_repair,
        bool,
    ):
        raise ValueError(
            "needs_repair debe ser booleano."
        )

    claims: list[GroundingClaim] = []

    for item in claims_raw:
        if not isinstance(item, dict):
            raise ValueError(
                "Cada claim debe ser un objeto."
            )

        claim = item.get("claim")
        citations_raw = item.get(
            "citations"
        )
        verdict = item.get("verdict")
        reason = item.get("reason")

        if (
            not isinstance(claim, str)
            or not claim.strip()
        ):
            raise ValueError(
                "claim inválido."
            )

        if verdict not in _VALID_VERDICTS:
            raise ValueError(
                "verdict inválido."
            )

        if not isinstance(reason, str):
            raise ValueError(
                "reason inválido."
            )

        if not isinstance(
            citations_raw,
            list,
        ):
            raise ValueError(
                "citations debe ser lista."
            )

        citations: list[str] = []

        for value in citations_raw:
            source_id = (
                _normalize_source_id(
                    value
                )
            )

            if source_id is None:
                raise ValueError(
                    "source_id inválido."
                )

            if source_id not in citations:
                citations.append(source_id)

        claims.append(
            GroundingClaim(
                claim=claim.strip(),
                citations=tuple(citations),
                verdict=verdict,
                reason=reason.strip(),
            )
        )

    derived_needs_repair = any(
        claim.verdict in {
            "partially_supported",
            "unsupported",
        }
        for claim in claims
    )

    return GroundingReport(
        claims=tuple(claims),
        needs_repair=derived_needs_repair,
    )
