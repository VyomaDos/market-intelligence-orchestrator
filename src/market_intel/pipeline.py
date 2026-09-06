from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from market_intel.agents import (
    DiscoveryAgent,
    ExtractionAgent,
    FreshResearchAgent,
    QualityReviewAgent,
    ResearchPlannerAgent,
    SynthesisAgent,
)
from market_intel.config import Settings
from market_intel.costs import calculate_run_cost, usage_snapshot
from market_intel.models import (
    Briefing,
    Competitor,
    CompetitorAnalysis,
    QualityReview,
    ResearchRequest,
)
from market_intel.providers import (
    OpenAIStructuredLLM,
    SearchProvider,
    StructuredLLM,
    YouSearchClient,
)
from market_intel.render import render_markdown


class PipelineState(TypedDict, total=False):
    request: dict[str, Any]
    competitors: list[dict[str, Any]]
    analyses: Annotated[list[dict[str, Any]], operator.add]
    quality: dict[str, Any]
    briefing: dict[str, Any]
    briefing_markdown: str
    events: Annotated[list[str], operator.add]


class WorkerState(TypedDict):
    request: dict[str, Any]
    competitor: dict[str, Any]


def build_pipeline(settings: Settings, *, search: SearchProvider | None = None,
                   llm: StructuredLLM | None = None):
    if search is None or llm is None:
        settings.validate_live_keys()
    search = search or YouSearchClient(settings.ydc_api_key, settings.request_timeout_seconds)
    llm = llm or OpenAIStructuredLLM(
        settings.openai_api_key,
        settings.openai_model,
        settings.request_timeout_seconds,
    )
    discovery = DiscoveryAgent(search, llm, settings.search_results_per_query)
    planner = ResearchPlannerAgent()
    researcher = FreshResearchAgent(search, settings.search_results_per_query, settings.search_freshness)
    extractor, reviewer, synthesizer = ExtractionAgent(llm), QualityReviewAgent(), SynthesisAgent(llm)

    def discover_node(state: PipelineState) -> dict[str, Any]:
        request = ResearchRequest.model_validate(state["request"])
        return {"request": request.model_dump(mode="json"),
                "competitors": [c.model_dump(mode="json") for c in discovery.run(request)],
                "events": ["discovery_complete"]}

    def fan_out(state: PipelineState) -> list[Send]:
        return [Send("research_competitor", {"request": state["request"], "competitor": c})
                for c in state["competitors"]]

    def research_node(state: WorkerState) -> dict[str, Any]:
        request = ResearchRequest.model_validate(state["request"])
        competitor = Competitor.model_validate(state["competitor"])
        bundle = researcher.run(planner.run(competitor, request))
        analysis = extractor.run(bundle)
        return {"analyses": [analysis.model_dump(mode="json")],
                "events": [f"researched:{competitor.name}"]}

    def review_node(state: PipelineState) -> dict[str, Any]:
        analyses = [CompetitorAnalysis.model_validate(item) for item in state["analyses"]]
        quality = reviewer.run(analyses)
        return {"quality": quality.model_dump(mode="json"), "events": ["quality_review_complete"]}

    def synthesize_node(state: PipelineState) -> dict[str, Any]:
        request = ResearchRequest.model_validate(state["request"])
        analyses = sorted(
            [CompetitorAnalysis.model_validate(item) for item in state["analyses"]],
            key=lambda a: a.competitor.name.casefold(),
        )
        quality = QualityReview.model_validate(state["quality"])
        draft = synthesizer.run(request, analyses, quality)
        source_count = len({str(s.url) for a in analyses for s in a.sources})
        cost = calculate_run_cost(
            settings,
            usage_snapshot(search),
            usage_snapshot(llm),
        )
        briefing = Briefing(request=request, competitors=analyses, quality=quality,
                            quality_score=quality.score, source_count=source_count,
                            cost=cost,
                            **draft.model_dump())
        return {"briefing": briefing.model_dump(mode="json"),
                "briefing_markdown": render_markdown(briefing), "events": ["synthesis_complete"]}

    graph = StateGraph(PipelineState)
    graph.add_node("discover", discover_node)
    graph.add_node("research_competitor", research_node)
    graph.add_node("quality_review", review_node, defer=True)
    graph.add_node("synthesize", synthesize_node)
    graph.add_edge(START, "discover")
    graph.add_conditional_edges("discover", fan_out, ["research_competitor"])
    graph.add_edge("research_competitor", "quality_review")
    graph.add_edge("quality_review", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile(checkpointer=InMemorySaver())
