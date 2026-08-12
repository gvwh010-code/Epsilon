from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ResearchPlan:
    queries: tuple[str, ...]
    verification_targets: tuple[str, ...]
    source_mode: str = "factual"


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    query: str
    published_date: str | None = None


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    title: str
    url: str
    text: str
    published_date: str | None = None


@dataclass(frozen=True)
class ResearchResult:
    answer: str
    plan: ResearchPlan
    sources: tuple[EvidenceSource, ...]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
