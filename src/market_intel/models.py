from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ResearchRequest(BaseModel):
    target_company: str = "Yardi Systems"
    category: str = "Facility Management software"
    top_n: int = Field(default=3, ge=1, le=5)
    geography: str = "United States"
    audience: str = "Product management"
    focus_questions: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    id: str
    query: str
    result_type: Literal["web", "news"]
    title: str
    # Keep this a plain string: OpenAI Structured Outputs rejects the JSON Schema
    # `format: uri` emitted by Pydantic's HttpUrl inside nested response models.
    url: str
    description: str = ""
    snippets: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    source_domain: str = ""

    @field_validator("published_at")
    @classmethod
    def normalize_published_at(cls, value: datetime | None) -> datetime | None:
        """Normalize provider and model timestamps to timezone-aware UTC."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Competitor(BaseModel):
    name: str
    website: str | None = None
    rationale: str
    evidence_urls: list[str] = Field(default_factory=list)


class DiscoveryOutput(BaseModel):
    competitors: list[Competitor]


class ResearchPlan(BaseModel):
    competitor: Competitor
    queries: list[str] = Field(min_length=4, max_length=10)


class ResearchBundle(BaseModel):
    competitor: Competitor
    sources: list[SearchResult]
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvidenceClaim(BaseModel):
    claim: str = Field(max_length=1_000)
    source_ids: list[str] = Field(min_length=1, max_length=3)
    confidence: float = Field(ge=0, le=1)


class PricingInsight(BaseModel):
    model: str = Field(default="Not publicly disclosed", max_length=200)
    details: str = Field(default="No reliable public pricing found.", max_length=1_200)
    claims: list[EvidenceClaim] = Field(default_factory=list, max_length=3)


class CompetitorAnalysisDraft(BaseModel):
    """Bounded LLM output; deterministic metadata and raw sources are injected afterward."""

    pricing: PricingInsight
    core_features: list[EvidenceClaim] = Field(max_length=6)
    market_positioning: list[EvidenceClaim] = Field(max_length=4)
    differentiators: list[EvidenceClaim] = Field(max_length=4)
    target_customers: list[EvidenceClaim] = Field(max_length=4)
    recent_news: list[EvidenceClaim] = Field(max_length=4)
    risks_and_unknowns: list[str] = Field(max_length=6)


class CompetitorAnalysis(BaseModel):
    competitor: Competitor
    pricing: PricingInsight
    core_features: list[EvidenceClaim]
    market_positioning: list[EvidenceClaim]
    differentiators: list[EvidenceClaim]
    target_customers: list[EvidenceClaim]
    recent_news: list[EvidenceClaim]
    risks_and_unknowns: list[str]
    sources: list[SearchResult]


class QualityReview(BaseModel):
    score: float = Field(ge=0, le=1)
    coverage_score: float = Field(ge=0, le=1)
    freshness_score: float = Field(ge=0, le=1)
    source_diversity_score: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class CostEstimate(BaseModel):
    ydc_calls: int
    ydc_cost_usd: float
    llm_calls: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    llm_cost_usd: float
    total_cost_usd: float
    assumptions: list[str]


class RunCost(BaseModel):
    ydc_calls: int
    ydc_cost_usd: float
    llm_calls: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    llm_cost_usd: float
    total_cost_usd: float


class HeroRationale(BaseModel):
    finding: str = Field(max_length=500)
    why_it_matters: str = Field(max_length=500)
    source_ids: list[str] = Field(min_length=1, max_length=3)


class OperationalAction(BaseModel):
    action: str = Field(max_length=500)
    owner: str = Field(max_length=100)
    timeframe: str = Field(max_length=100)
    priority: Literal["Now", "Next", "Later"]
    success_metric: str = Field(max_length=300)
    source_ids: list[str] = Field(min_length=1, max_length=3)


class BriefingDraft(BaseModel):
    title: str = Field(max_length=200)
    headline: str = Field(max_length=300)
    audience_takeaway: str = Field(max_length=500)
    effect: list[str] = Field(min_length=1, max_length=3)
    rationale: list[HeroRationale] = Field(min_length=1, max_length=5)
    operations: list[OperationalAction] = Field(min_length=1, max_length=5)
    executive_summary: str = Field(max_length=2_000)
    comparative_takeaways: list[str] = Field(max_length=6)
    strategic_implications: list[str] = Field(max_length=6)
    recommended_actions: list[str] = Field(max_length=6)
    watchlist: list[str] = Field(max_length=6)


class Briefing(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request: ResearchRequest
    title: str
    headline: str
    audience_takeaway: str
    effect: list[str]
    rationale: list[HeroRationale]
    operations: list[OperationalAction]
    executive_summary: str
    competitors: list[CompetitorAnalysis]
    comparative_takeaways: list[str]
    strategic_implications: list[str]
    recommended_actions: list[str]
    watchlist: list[str]
    quality: QualityReview
    quality_score: float
    source_count: int
    cost: RunCost
