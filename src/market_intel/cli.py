import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from market_intel.config import get_settings
from market_intel.costs import estimate_run_cost
from market_intel.pipeline import build_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a competitor-intelligence briefing")
    parser.add_argument("--company", default="Yardi Systems")
    parser.add_argument("--category", default="Facility Management software")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--geography", default="United States")
    parser.add_argument(
        "--audience",
        choices=["Product management", "Strategy", "CEO", "VP", "Founder", "Consulting"],
        default="Product management",
    )
    parser.add_argument("--yes", action="store_true", help="Approve the displayed cost estimate")
    args = parser.parse_args()
    settings = get_settings()
    estimate = estimate_run_cost(args.top_n, settings)
    print(
        f"Estimated cost: ${estimate.total_cost_usd:.4f} "
        f"(You.com ${estimate.ydc_cost_usd:.4f}; LLM ${estimate.llm_cost_usd:.4f})"
    )
    if not args.yes and input("Proceed? [y/N] ").strip().casefold() not in {"y", "yes"}:
        print("Cancelled before any provider calls.")
        return
    graph = build_pipeline(settings)
    result = graph.invoke({"request": {"target_company": args.company, "category": args.category,
                                        "top_n": args.top_n, "geography": args.geography,
                                        "audience": args.audience},
                           "analyses": [], "events": []},
                          {"configurable": {"thread_id": str(uuid.uuid4())},
                           "max_concurrency": settings.max_concurrency})
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    (output_dir / f"briefing-{stamp}.md").write_text(result["briefing_markdown"], encoding="utf-8")
    (output_dir / f"briefing-{stamp}.json").write_text(json.dumps(result["briefing"], indent=2), encoding="utf-8")
    print(result["briefing_markdown"])


if __name__ == "__main__":
    main()
