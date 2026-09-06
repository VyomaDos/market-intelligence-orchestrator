from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel

from market_intel.agents import QualityReviewAgent
from market_intel.config import Settings
from market_intel.costs import estimate_run_cost
from market_intel.models import (
    BriefingDraft,
    Competitor,
    CompetitorAnalysis,
    CompetitorAnalysisDraft,
    DiscoveryOutput,
    EvidenceClaim,
    PricingInsight,
    SearchResult,
)
from market_intel.pipeline import build_pipeline

T = TypeVar("T", bound=BaseModel)


class FakeSearch:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, *, count: int, freshness: str | None = None) -> list[SearchResult]:
        self.calls += 1
        slug = str(abs(hash(query)))
        return [SearchResult(id="source0001", query=query,
                             result_type="news" if "news" in query else "web",
                             title=f"Evidence for {query[:30]}", url=f"https://example.com/{slug}",
                             published_at=datetime.now(UTC), source_domain="example.com")]

    def usage_snapshot(self) -> dict[str, int]:
        return {"calls": self.calls}


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, schema: type[T], *, system: str, prompt: str) -> T:
        self.calls += 1
        if schema is DiscoveryOutput:
            return schema(competitors=[
                Competitor(name="Alpha FM", website="alpha.example", rationale="Direct FM suite"),
                Competitor(name="Beta Works", website="beta.example", rationale="Enterprise overlap"),
                Competitor(name="Gamma Ops", website="gamma.example", rationale="Comparable workflows")])
        if schema is CompetitorAnalysisDraft:
            name = "Alpha FM" if "Alpha FM" in prompt else "Beta Works" if "Beta Works" in prompt else "Gamma Ops"
            source = SearchResult(id="source0001", query="test", result_type="news",
                                  title="Fresh evidence", url=f"https://{name.split()[0].lower()}.example/news",
                                  published_at=datetime.now(UTC),
                                  source_domain=f"{name.split()[0].lower()}.example")
            claim = EvidenceClaim(claim="Evidence-backed capability", source_ids=[source.id], confidence=.9)
            return schema(pricing=PricingInsight(model="Quote-based", details="Contact sales", claims=[claim]),
                          core_features=[claim], market_positioning=[claim], differentiators=[claim],
                          target_customers=[claim], recent_news=[claim], risks_and_unknowns=[])
        if schema is BriefingDraft:
            return schema(title="Facility Management Competitive Briefing",
                          headline="Competitors are converging on enterprise workflow depth.",
                          audience_takeaway="Prioritize proof of differentiation before roadmap commitment.",
                          effect=["Win/loss risk rises where workflows overlap."],
                          rationale=[{"finding": "Feature overlap is material.",
                                      "why_it_matters": "Buyers may see the products as interchangeable.",
                                      "source_ids": ["source0001"]}],
                          operations=[{"action": "Run five win/loss interviews.",
                                       "owner": "VP Product", "timeframe": "30 days",
                                       "priority": "Now", "success_metric": "Five interviews completed",
                                       "source_ids": ["source0001"]}],
                          executive_summary="Three competitors show meaningful overlap.",
                          comparative_takeaways=["Positioning differs by segment."],
                          strategic_implications=["Validate workflow depth."],
                          recommended_actions=["Run win/loss interviews."], watchlist=["Pricing changes"])
        raise AssertionError(f"Unexpected schema: {schema}")

    def usage_snapshot(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "input_tokens": self.calls * 100,
            "cached_input_tokens": self.calls * 10,
            "output_tokens": self.calls * 50,
        }


def test_pipeline_builds_a_cited_briefing() -> None:
    graph = build_pipeline(Settings(), search=FakeSearch(), llm=FakeLLM())
    result = graph.invoke({"request": {"target_company": "Yardi Systems",
                                        "category": "Facility Management software", "top_n": 3},
                           "analyses": [], "events": []},
                          {"configurable": {"thread_id": "test-thread"}, "max_concurrency": 3})
    assert len(result["briefing"]["competitors"]) == 3
    assert result["briefing"]["quality_score"] > .7
    assert "Competitive snapshot" in result["briefing_markdown"]
    assert "Executive brief" in result["briefing_markdown"]
    assert "HERO" not in result["briefing_markdown"]
    assert "Prepared for:** Product management" in result["briefing_markdown"]
    assert "| Now | VP Product |" in result["briefing_markdown"]
    assert result["events"].count("synthesis_complete") == 1
    assert result["briefing"]["cost"]["ydc_calls"] == 21
    assert result["briefing"]["cost"]["llm_calls"] == 5
    assert result["briefing"]["cost"]["total_cost_usd"] > 0.105


def test_pipeline_streams_progress_updates_and_checkpoints_result() -> None:
    graph = build_pipeline(Settings(), search=FakeSearch(), llm=FakeLLM())
    config = {"configurable": {"thread_id": "stream-test"}, "max_concurrency": 3}
    updates = list(
        graph.stream(
            {"request": {"target_company": "Yardi Systems",
                         "category": "Facility Management software", "top_n": 3},
             "analyses": [], "events": []},
            config,
            stream_mode="updates",
        )
    )
    nodes = [node for update in updates for node in update]
    assert nodes.count("discover") == 1
    assert nodes.count("research_competitor") == 3
    assert nodes.count("quality_review") == 1
    assert nodes.count("synthesize") == 1
    assert graph.get_state(config).values["briefing"]["source_count"] == 18


def test_you_search_uses_current_post_endpoint() -> None:
    from market_intel.providers import YouSearchClient
    assert YouSearchClient.endpoint == "https://ydc-index.io/v1/search"


def test_naive_source_timestamp_is_normalized_before_quality_review() -> None:
    source = SearchResult(
        id="source0001",
        query="test",
        result_type="news",
        title="Evidence",
        url="https://example.com/news",
        published_at=datetime(2026, 8, 1),  # noqa: DTZ001 - regression input is intentionally naive
        source_domain="example.com",
    )
    assert source.published_at is not None
    assert source.published_at.utcoffset() is not None

    claim = EvidenceClaim(claim="Supported claim", source_ids=[source.id], confidence=.9)
    analysis = CompetitorAnalysis(
        competitor=Competitor(name="Alpha FM", rationale="Direct competitor"),
        pricing=PricingInsight(model="Quote-based", details="Contact sales", claims=[claim]),
        core_features=[claim],
        market_positioning=[claim],
        differentiators=[claim],
        target_customers=[claim],
        recent_news=[claim],
        risks_and_unknowns=[],
        sources=[source],
    )
    assert QualityReviewAgent().run([analysis]).freshness_score == 1


def test_cost_estimate_is_available_before_provider_calls() -> None:
    estimate = estimate_run_cost(3, Settings(_env_file=None))
    assert estimate.ydc_calls == 21
    assert estimate.llm_calls == 5
    assert estimate.ydc_cost_usd == 0.105
    assert estimate.total_cost_usd > estimate.ydc_cost_usd
