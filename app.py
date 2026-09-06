from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import streamlit as st

from market_intel.config import get_settings
from market_intel.costs import estimate_run_cost
from market_intel.demo import build_demo
from market_intel.pipeline import build_pipeline

st.set_page_config(page_title="Market Intelligence Orchestrator", page_icon="🔎", layout="wide")
st.title("Market Intelligence Orchestrator")
st.caption("Fresh, cited competitor intelligence for product and strategy decisions")
st.page_link("pages/How_It_Works.py", label="See how the agents and LangGraph workflow operate", icon="🧭")

with st.sidebar:
    st.header("Research scope")
    company = st.text_input("Target company", "NVIDIA")
    category = st.text_input("Market/category", "AI Chips")
    top_n = st.slider("Competitors", 1, 5, 3)
    geography = st.text_input("Geography", "United States")
    freshness_label = st.selectbox(
        "Data freshness",
        options=["Past day", "Past week", "Past month", "Past three months", "Past year"],
        index=2,
        help="Limits competitor research searches to the selected time window.",
    )
    audience = st.selectbox(
        "Primary audience",
        ["Product management", "Strategy", "CEO", "VP", "Founder", "Consulting"],
    )
    questions = st.text_area(
        "Optional focus questions",
        "Where is NVIDIA differentiated?\nWhich competitor moves should the product team monitor?",
    )
    load_demo = st.button(
        "Load project-review demo",
        use_container_width=True,
        help="Loads a prepared NVIDIA AI chips briefing without making API calls.",
    )
    today = datetime.now(UTC).date()
    freshness = {
        "Past day": "day",
        "Past week": "week",
        "Past month": "month",
        "Past three months": f"{today - timedelta(days=90)}to{today}",
        "Past year": "year",
    }[freshness_label]
    run_settings = get_settings().model_copy(update={"search_freshness": freshness})
    estimate = estimate_run_cost(top_n, run_settings)
    st.divider()
    st.subheader("Estimated run cost")
    st.metric("Estimated total", f"${estimate.total_cost_usd:.3f}")
    st.caption(
        f"You.com: ${estimate.ydc_cost_usd:.3f} ({estimate.ydc_calls} calls) · "
        f"LLM: ${estimate.llm_cost_usd:.3f} ({estimate.llm_calls} calls)"
    )
    approve_cost = st.checkbox(
        f"Proceed with an estimated ${estimate.total_cost_usd:.3f} run",
        help="This is an estimate. Retries and token volume can change the actual charge.",
    )
    run = st.button(
        "Run research",
        type="primary",
        use_container_width=True,
        disabled=not approve_cost,
    )

if load_demo:
    demo_briefing, demo_markdown = build_demo()
    st.session_state["briefing"] = demo_briefing
    st.session_state["markdown"] = demo_markdown

if run:
    try:
        settings = run_settings
        pipeline = build_pipeline(settings)
        request = {
            "target_company": company,
            "category": category,
            "top_n": top_n,
            "geography": geography,
            "audience": audience,
            "focus_questions": [line.strip() for line in questions.splitlines() if line.strip()],
        }
        thread_id = str(uuid.uuid4())
        graph_config = {
            "configurable": {"thread_id": thread_id},
            "max_concurrency": settings.max_concurrency,
        }
        total_steps = top_n + 3  # discovery + each competitor + review + synthesis
        completed_steps = 0
        with st.status("Starting the research team…", expanded=True) as status:
            progress = st.progress(0, text="0% complete · Preparing the research scope")
            for update in pipeline.stream(
                {"request": request, "analyses": [], "events": []},
                graph_config,
                stream_mode="updates",
            ):
                for node_name, node_output in update.items():
                    completed_steps += 1
                    percent = min(100, round(completed_steps / total_steps * 100))
                    if node_name == "discover":
                        names = [item["name"] for item in node_output.get("competitors", [])]
                        message = (
                            f"Competitors selected: {', '.join(names)}. "
                            "Starting their research in parallel."
                        )
                    elif node_name == "research_competitor":
                        events = node_output.get("events", [])
                        name = events[0].partition(":")[2] if events else "a competitor"
                        message = f"Finished gathering and validating evidence for {name}."
                    elif node_name == "quality_review":
                        message = "Evidence quality checked for coverage, freshness, and source diversity."
                    elif node_name == "synthesize":
                        message = f"Decision-ready briefing tailored for {audience} is complete."
                    else:
                        message = "Research advanced to the next stage."
                    progress.progress(percent, text=f"{percent}% complete · {message}")
                    st.write(f"**{percent}%** — {message}")
            result = pipeline.get_state(graph_config).values
            progress.progress(100, text="100% complete · Your briefing is ready")
            status.update(label="Research complete — briefing ready", state="complete")
        st.session_state["briefing"] = result["briefing"]
        st.session_state["markdown"] = result["briefing_markdown"]
    except Exception as exc:  # noqa: BLE001 - the UI must report provider/graph failures cleanly
        st.error(f"Research failed: {exc}")

if "briefing" in st.session_state:
    briefing = st.session_state["briefing"]
    markdown = st.session_state["markdown"]
    if briefing.get("demo"):
        st.success("Project-review demo · Prepared sample · No API calls made")
    score = briefing.get("quality_score", 0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Competitors analyzed", len(briefing.get("competitors", [])))
    c2.metric("Quality score", f"{score:.0%}")
    c3.metric("Evidence sources", briefing.get("source_count", 0))
    c4.metric("Actual cost", f"${briefing.get('cost', {}).get('total_cost_usd', 0):.3f}")
    cost = briefing.get("cost", {})
    with st.expander("Run cost details"):
        st.write(
            f"You.com: **${cost.get('ydc_cost_usd', 0):.4f}** "
            f"across {cost.get('ydc_calls', 0)} calls"
        )
        st.write(
            f"LLM: **${cost.get('llm_cost_usd', 0):.4f}** across "
            f"{cost.get('llm_calls', 0)} calls — {cost.get('input_tokens', 0):,} input, "
            f"{cost.get('cached_input_tokens', 0):,} cached input, and "
            f"{cost.get('output_tokens', 0):,} output tokens"
        )
    st.markdown(markdown)
    left, right = st.columns(2)
    left.download_button("Download Markdown", markdown, "competitor-briefing.md", "text/markdown")
    right.download_button(
        "Download JSON",
        json.dumps(briefing, indent=2),
        "competitor-briefing.json",
        "application/json",
    )
