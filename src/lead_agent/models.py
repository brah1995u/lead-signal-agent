from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ICP(BaseModel):
    """Ideal customer profile: what you sell and who should buy it."""

    product: str = Field(description="What you sell, in one or two sentences")
    customers: str = Field(description="Who buys it: company type, size, role")
    buying_signals: list[str] = Field(
        default_factory=list, description="Phrases or situations that show intent"
    )
    exclude: list[str] = Field(
        default_factory=list, description="Who is not a fit (competitors, students, ...)"
    )
    min_score: int = Field(
        default=60, ge=0, le=100, description="Fit score from which a signal counts as a lead"
    )
    days: int = Field(default=30, ge=1, le=365, description="How far back to search")


class Signal(BaseModel):
    """A public post or comment. Only what is needed to judge it and to link to it."""

    id: str  # "<source>:<native id>"
    source: str
    url: str
    title: str = ""
    text: str = ""
    author: str = ""  # public handle shown on the post, never a profile scrape
    created_at: datetime | None = None
    points: int | None = None
    query: str = ""


class Intent(StrEnum):
    BUYING = "buying"
    RECOMMENDATION = "asking_for_recommendation"
    PROBLEM = "describing_a_problem"
    COMPETITOR_PAIN = "unhappy_with_competitor"
    HIRING = "hiring"
    NOT_RELEVANT = "not_relevant"


class Qualification(BaseModel):
    id: str = Field(description="The id of the signal being judged, copied exactly")
    intent: Intent
    fit_score: int = Field(ge=0, le=100, description="0 = no fit, 100 = perfect fit with clear intent")
    reasons: list[str] = Field(description="Up to three short reasons")
    summary: str = Field(description="One sentence: what this person or company needs")
    suggested_opener: str = Field(
        description="First sentence of a helpful public reply, no hard sell; empty if not relevant"
    )


class QualificationBatch(BaseModel):
    results: list[Qualification]


class QueryPlan(BaseModel):
    queries: list[str] = Field(
        description="3 to 6 short keyword queries (2-5 words each) that find buying intent"
    )


class Lead(BaseModel):
    signal: Signal
    qualification: Qualification

    @property
    def score(self) -> int:
        return self.qualification.fit_score
