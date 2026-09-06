from market_intel.models import Briefing


def render_markdown(briefing: Briefing) -> str:
    source_map = {source.id: source for item in briefing.competitors for source in item.sources}

    def citations(source_ids: list[str]) -> str:
        return " ".join(
            f"[[{source_id}]]({source_map[source_id].url})"
            for source_id in source_ids if source_id in source_map
        )

    lines = [
        f"# {briefing.title}", "", f"**Prepared for:** {briefing.request.audience}", "",
        f"*Generated {briefing.generated_at:%Y-%m-%d %H:%M UTC} · Quality {briefing.quality_score:.0%} · {briefing.source_count} sources*",
        "", f"> ## {briefing.headline}", f"> {briefing.audience_takeaway}", "",
        "## Executive brief", "", "### Effect", "",
        *[f"- {effect}" for effect in briefing.effect], "", "### Rationale", "",
    ]
    for rationale in briefing.rationale:
        lines.append(f"- **{rationale.finding}** — {rationale.why_it_matters} {citations(rationale.source_ids)}")

    lines += ["", "### Operations", "",
              "| Priority | Owner | Action | Timeframe | Success measure |",
              "|---|---|---|---|---|"]
    for operation in briefing.operations:
        action = f"{operation.action} {citations(operation.source_ids)}".strip()
        lines.append(f"| {operation.priority} | {operation.owner} | {action} | {operation.timeframe} | {operation.success_metric} |")

    lines += ["", "## Executive context", "", briefing.executive_summary, "",
              "## Competitive snapshot", "",
              "| Competitor | Pricing | Positioning | Recent signal |", "|---|---|---|---|"]
    for item in briefing.competitors:
        positioning = item.market_positioning[0].claim if item.market_positioning else "Not verified"
        news = item.recent_news[0].claim if item.recent_news else "No dated signal verified"
        lines.append(f"| {item.competitor.name} | {item.pricing.model} | {positioning} | {news} |")

    lines += ["", "# Evidence appendix"]
    for item in briefing.competitors:
        lines += ["", f"## {item.competitor.name}", "", f"**Why it competes:** {item.competitor.rationale}", "",
                  f"**Pricing:** {item.pricing.model} — {item.pricing.details}"]
        sections = [("Core features", item.core_features), ("Market positioning", item.market_positioning),
                    ("Differentiators", item.differentiators), ("Target customers", item.target_customers),
                    ("Recent news", item.recent_news)]
        for heading, claims in sections:
            lines += ["", f"### {heading}", ""]
            if not claims:
                lines.append("- Not verified from available public evidence.")
            lines += [f"- {claim.claim} {citations(claim.source_ids)}" for claim in claims]
        if item.risks_and_unknowns:
            lines += ["", "### Risks and unknowns", ""] + [f"- {value}" for value in item.risks_and_unknowns]

    for heading, values in [("Comparative takeaways", briefing.comparative_takeaways),
                            ("Strategic implications", briefing.strategic_implications),
                            ("Additional recommendations", briefing.recommended_actions),
                            ("Watchlist", briefing.watchlist)]:
        lines += ["", f"## {heading}", ""] + [f"- {value}" for value in values]

    lines += ["", "## Research quality", "", f"- Coverage: {briefing.quality.coverage_score:.0%}",
              f"- Freshness: {briefing.quality.freshness_score:.0%}",
              f"- Source diversity: {briefing.quality.source_diversity_score:.0%}"]
    lines += [f"- Warning: {warning}" for warning in briefing.quality.warnings]
    lines += ["", "## Run cost", "",
              f"- You.com Search: ${briefing.cost.ydc_cost_usd:.4f} ({briefing.cost.ydc_calls} calls)",
              f"- LLM: ${briefing.cost.llm_cost_usd:.4f} ({briefing.cost.llm_calls} calls; {briefing.cost.input_tokens:,} input, {briefing.cost.cached_input_tokens:,} cached input, {briefing.cost.output_tokens:,} output tokens)",
              f"- Total calculated API cost: ${briefing.cost.total_cost_usd:.4f}", "", "## Methodology", "",
              "Competitors were discovered and researched with You.com Web Search. Claims were extracted into typed records, checked for source-ID validity, and synthesized by an LLM. Public-web evidence can be incomplete; validate commercial decisions with vendor or customer interviews."]
    return "\n".join(lines)
