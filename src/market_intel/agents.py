from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import chain

from market_intel.models import (
    BriefingDraft,
    Competitor,
    CompetitorAnalysis,
    CompetitorAnalysisDraft,
    DiscoveryOutput,
    QualityReview,
    ResearchBundle,
    ResearchPlan,
    ResearchRequest,
    SearchResult,
)
from market_intel.providers import SearchProvider, StructuredLLM


def source_text(sources: list[SearchResult], max_chars: int = 45_000) -> str:
    records = [
        {"id": s.id, "type": s.result_type, "title": s.title, "url": str(s.url),
         "published_at": s.published_at.isoformat() if s.published_at else None,
         "description": s.description, "snippets": s.snippets}
        for s in sources
    ]
    return json.dumps(records, ensure_ascii=False)[:max_chars]


class DiscoveryAgent:
    def __init__(self, search: SearchProvider, llm: StructuredLLM, result_count: int) -> None:
        self.search, self.llm, self.result_count = search, llm, result_count

    def run(self, request: ResearchRequest) -> list[Competitor]:
        queries = [
            f'"{request.target_company}" competitors {request.category} {request.geography}',
            f'best {request.category} software alternatives to "{request.target_company}"',
            f'{request.category} market vendors comparison "{request.target_company}"',
        ]
        by_url: dict[str, SearchResult] = {}
        for query in queries:
            for result in self.search.search(query, count=self.result_count):
                by_url.setdefault(str(result.url).rstrip("/"), result)
        output = self.llm.generate(
            DiscoveryOutput,
            system="Select direct product competitors only, using supplied evidence. Exclude partners, adjacent tools, and the target.",
            prompt=(f"Target: {request.target_company}\nCategory: {request.category}\nGeography: {request.geography}\n"
                    f"Return exactly {request.top_n} competitors ranked by overlap and relevance. Evidence:\n"
                    f"{source_text(list(by_url.values()))}"),
        )
        competitors = [c for c in output.competitors if c.name.casefold() != request.target_company.casefold()]
        unique = list({c.name.casefold(): c for c in competitors}.values())
        if len(unique) < request.top_n:
            raise ValueError("Discovery did not return enough distinct direct competitors")
        return unique[:request.top_n]


class ResearchPlannerAgent:
    def run(self, competitor: Competitor, request: ResearchRequest) -> ResearchPlan:
        name, category = competitor.name, request.category
        queries = [
            f'"{name}" {category} official features', f'"{name}" pricing plans cost {category}',
            f'"{name}" customers market positioning {category}',
            f'"{name}" vs "{request.target_company}" {category}',
            f'"{name}" news product launch acquisition partnership',
            f'site:{competitor.website} {category} features' if competitor.website else f'"{name}" product documentation {category}',
        ]
        return ResearchPlan(competitor=competitor, queries=queries)


class FreshResearchAgent:
    def __init__(self, search: SearchProvider, result_count: int, freshness: str) -> None:
        self.search, self.result_count, self.freshness = search, result_count, freshness

    def run(self, plan: ResearchPlan) -> ResearchBundle:
        by_url: dict[str, SearchResult] = {}
        for query in plan.queries:
            for result in self.search.search(
                query, count=self.result_count, freshness=self.freshness
            ):
                by_url.setdefault(str(result.url).rstrip("/"), result)
        return ResearchBundle(competitor=plan.competitor, sources=list(by_url.values()))


class ExtractionAgent:
    def __init__(self, llm: StructuredLLM) -> None:
        self.llm = llm

    def run(self, bundle: ResearchBundle) -> CompetitorAnalysis:
        draft = self.llm.generate(
            CompetitorAnalysisDraft,
            system=("Extract only supported claims. Every material claim must cite exact supplied source IDs. "
                    "Never infer prices; use 'Not publicly disclosed' when needed. News must be a dated event."),
            prompt=(f"Analyze {bundle.competitor.name}. "
                    "Extract pricing, features, positioning, differentiators, customers, news, and unknowns. "
                    "Be concise and cite only supplied source IDs. Do not return raw source records. "
                    f"Sources:\n{source_text(bundle.sources, max_chars=30_000)}"),
        )
        valid_ids = {source.id for source in bundle.sources}
        removed = 0

        def supported(claims):
            nonlocal removed
            cleaned = []
            for claim in claims:
                source_ids = [source_id for source_id in claim.source_ids if source_id in valid_ids]
                if not source_ids:
                    removed += 1
                    continue
                cleaned.append(claim.model_copy(update={"source_ids": source_ids}))
            return cleaned

        updates = {
            "competitor": bundle.competitor,
            "sources": bundle.sources,
            "pricing": draft.pricing.model_copy(
                update={"claims": supported(draft.pricing.claims)}
            ),
            "core_features": supported(draft.core_features),
            "market_positioning": supported(draft.market_positioning),
            "differentiators": supported(draft.differentiators),
            "target_customers": supported(draft.target_customers),
            "recent_news": supported(draft.recent_news),
            "risks_and_unknowns": draft.risks_and_unknowns,
        }
        if removed:
            updates["risks_and_unknowns"] = [
                *draft.risks_and_unknowns,
                f"{removed} unsupported claim(s) were removed during evidence validation.",
            ]
        return CompetitorAnalysis.model_validate(updates)


class QualityReviewAgent:
    def run(self, analyses: list[CompetitorAnalysis]) -> QualityReview:
        if not analyses:
            return QualityReview(score=0, coverage_score=0, freshness_score=0,
                                 source_diversity_score=0, warnings=["No analyses produced"])
        warnings: list[str] = []
        now, present, fresh, dated, total = datetime.now(UTC), 0, 0, 0, 0
        domains: set[str] = set()
        for analysis in analyses:
            sections = [analysis.pricing.claims, analysis.core_features,
                        analysis.market_positioning, analysis.recent_news]
            present += sum(bool(section) for section in sections)
            if not analysis.pricing.claims:
                warnings.append(f"{analysis.competitor.name}: public pricing not verified")
            if not analysis.recent_news:
                warnings.append(f"{analysis.competitor.name}: no recent dated news verified")
            valid_ids = {s.id for s in analysis.sources}
            all_claims = chain.from_iterable(
                sections[1:] + [analysis.differentiators, analysis.target_customers]
            )
            if any(not set(c.source_ids).issubset(valid_ids) for c in all_claims):
                warnings.append(f"{analysis.competitor.name}: claim references an unknown source ID")
            for source in analysis.sources:
                total += 1
                domains.add(source.source_domain)
                if source.published_at:
                    dated += 1
                    fresh += int((now - source.published_at).days <= 365)
        coverage = present / (len(analyses) * 4)
        freshness = fresh / dated if dated else 0.35
        diversity = min(1.0, len(domains) / max(1, len(analyses) * 4))
        if total < len(analyses) * 5:
            warnings.append("Low evidence volume; validate before external sharing")
        return QualityReview(score=round(.5 * coverage + .3 * freshness + .2 * diversity, 3),
                             coverage_score=round(coverage, 3), freshness_score=round(freshness, 3),
                             source_diversity_score=round(diversity, 3), warnings=sorted(set(warnings)))


class SynthesisAgent:
    def __init__(self, llm: StructuredLLM) -> None:
        self.llm = llm

    def run(self, request: ResearchRequest, analyses: list[CompetitorAnalysis], quality: QualityReview) -> BriefingDraft:
        audience_guidance = {
            "ceo": "Lead with enterprise value, growth, retention, strategic risk, capital allocation, and the decision required.",
            "vp": "Lead with portfolio priorities, tradeoffs, cross-functional dependencies, and executable 30/60/90-day moves.",
            "product management": "Lead with customer problems, product gaps, roadmap hypotheses, experiments, and measurable product outcomes.",
            "strategy": "Lead with market structure, competitor moves, scenarios, strategic options, and signposts to monitor.",
            "founder": "Lead with differentiation wedge, go-to-market leverage, resource constraints, and highest-value near-term bets.",
            "consulting": "Lead with the answer, quantified implications, evidence, recommendation, and implementation sequence.",
        }.get(request.audience.casefold(), "Lead with the decision, business impact, evidence, and accountable next steps.")
        compact = [
            {
                "competitor": a.competitor.name,
                "pricing": a.pricing.model,
                "features": [c.model_dump() for c in a.core_features],
                "positioning": [c.model_dump() for c in a.market_positioning],
                "differentiators": [c.model_dump() for c in a.differentiators],
                "news": [c.model_dump() for c in a.recent_news],
                "unknowns": a.risks_and_unknowns,
            }
            for a in analyses
        ]
        draft = self.llm.generate(
            BriefingDraft,
            system=(
                "Create a concise, audience-specific competitive intelligence briefing using HERO: Headline, "
                "Effect, Rationale, Operations. Lead with the answer. Separate evidence from implications. "
                "Every rationale and operation must cite supplied source IDs. Operations must name an accountable "
                "role, timeframe, priority, and measurable success criterion. Introduce no new facts."
            ),
            prompt=(f"Audience: {request.audience}\nTarget: {request.target_company}\nCategory: {request.category}\n"
                    f"Audience guidance: {audience_guidance}\nFocus: {request.focus_questions}\n"
                    f"Warnings: {quality.warnings}\nAnalyses: {json.dumps(compact)}"),
        )
        valid_ids = {source.id for analysis in analyses for source in analysis.sources}

        def valid_source_ids(source_ids: list[str]) -> list[str]:
            return list(dict.fromkeys(source_id for source_id in source_ids if source_id in valid_ids))

        rationale = [
            item.model_copy(update={"source_ids": valid_source_ids(item.source_ids)})
            for item in draft.rationale
            if valid_source_ids(item.source_ids)
        ]
        operations = [
            item.model_copy(update={"source_ids": valid_source_ids(item.source_ids)})
            for item in draft.operations
            if valid_source_ids(item.source_ids)
        ]
        if not rationale or not operations:
            raise ValueError("Synthesis did not provide evidence-linked rationale and operations")
        return draft.model_copy(update={"rationale": rationale, "operations": operations})
