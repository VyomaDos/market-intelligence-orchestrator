import streamlit as st

st.set_page_config(page_title="How It Works", page_icon="🧭", layout="wide")
st.title("How the research system works")
st.caption("A visual guide to the actual agents, handoffs, tools, and LangGraph orchestration used by this app.")

st.subheader("End-to-end flow")
st.graphviz_chart(
    """
    digraph MarketIntel {
      graph [rankdir=LR, bgcolor="transparent", pad="0.3", nodesep="0.45", ranksep="0.7"];
      node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11,
            color="#476582", fillcolor="#EEF5FF", margin="0.16,0.10"];
      edge [color="#718096", fontname="Arial", fontsize=9, arrowsize=0.7];

      input [label="Research request\ncompany · market · freshness · audience", fillcolor="#FFF4DE"];
      discover [label="1  Discovery Agent\n3 You.com searches + LLM ranking"];
      fanout [label="LangGraph Send()\nparallel fan-out", shape=diamond, fillcolor="#E8E1FF"];
      worker1 [label="Competitor worker A\nPlan → Search → Extract"];
      worker2 [label="Competitor worker B\nPlan → Search → Extract"];
      worker3 [label="Competitor worker C\nPlan → Search → Extract"];
      reducer [label="Reducer-backed state\nmerges analyses + events", fillcolor="#E8E1FF"];
      review [label="2  Quality Review Agent\ncoverage · freshness · diversity"];
      synthesis [label="3  Synthesis Agent\naudience-tailored decision brief"];
      output [label="Markdown + JSON\ncitations · actions · actual cost", fillcolor="#E3F7EA"];

      input -> discover -> fanout;
      fanout -> worker1 [label="competitor 1"];
      fanout -> worker2 [label="competitor 2"];
      fanout -> worker3 [label="competitor 3"];
      worker1 -> reducer;
      worker2 -> reducer;
      worker3 -> reducer;
      reducer -> review -> synthesis -> output;
    }
    """,
    width="stretch",
)

st.info(
    "The number of competitor workers is dynamic. Selecting five competitors creates five parallel "
    "branches; the diagram shows three as the default example."
)

st.subheader("What each agent actually does")
cards = [
    ("Discovery Agent", "Finds and ranks direct competitors", "Runs three You.com queries, deduplicates results, then asks the LLM for exactly the requested number of direct competitors. It rejects the target company and duplicate vendors."),
    ("Research Planner", "Builds a competitor-specific search plan", "Creates six queries covering official features, pricing, customers and positioning, comparisons, recent company news, and official product documentation."),
    ("Fresh Research Agent", "Collects current web evidence", "Executes the plan through You.com with the selected freshness window and removes duplicate URLs before extraction."),
    ("Extraction Agent", "Turns sources into cited intelligence", "Uses a typed LLM response for pricing, features, positioning, differentiators, customers, and dated news. Claims with missing or invented source IDs are removed."),
    ("Quality Review Agent", "Scores evidence without another LLM call", "Calculates coverage, freshness, and domain diversity; flags missing pricing, missing dated news, low evidence volume, and invalid citations."),
    ("Synthesis Agent", "Creates the decision-ready briefing", "Adjusts emphasis for PM, CEO, VP, Strategy, Founder, or Consulting audiences and produces cited rationale plus prioritized actions with owners, timing, and success measures."),
]
for row_start in range(0, len(cards), 3):
    columns = st.columns(3)
    for column, (name, role, detail) in zip(columns, cards[row_start:row_start + 3], strict=False):
        with column, st.container(border=True):
            st.markdown(f"#### {name}")
            st.markdown(f"**{role}**")
            st.write(detail)

st.subheader("Where LangGraph is used")
left, right = st.columns(2)
with left, st.container(border=True):
    st.markdown("#### Orchestration")
    st.markdown(
        "- `StateGraph` defines the discover, research, quality-review, and synthesis nodes.\n"
        "- `Send()` dynamically fans out one worker for every competitor.\n"
        "- `defer=True` makes quality review wait for all parallel workers.\n"
        "- `START` and `END` define the graph boundaries."
    )
with right, st.container(border=True):
    st.markdown("#### State and reliability")
    st.markdown(
        "- `Annotated[list, operator.add]` safely merges parallel analyses and events.\n"
        "- `InMemorySaver` checkpoints state under a unique thread ID.\n"
        "- Pydantic models validate every agent boundary and structured LLM response.\n"
        "- Provider interfaces are injectable, so tests run without API charges."
    )

st.subheader("Tools and model calls")
st.markdown(
    "| Stage | Tool | Calls for 3 competitors | Purpose |\n"
    "|---|---:|---:|---|\n"
    "| Discovery | You.com Search API | 3 | Find candidate competitors |\n"
    "| Discovery | OpenAI structured response | 1 | Rank direct competitors |\n"
    "| Research | You.com Search API | 18 | Six focused searches per competitor |\n"
    "| Extraction | OpenAI structured response | 3 | Build one cited analysis per competitor |\n"
    "| Quality review | Deterministic Python | 0 | Score evidence and identify gaps |\n"
    "| Synthesis | OpenAI structured response | 1 | Produce the audience-specific briefing |"
)
st.caption("Default total: 21 You.com calls and 5 LLM calls. The app estimates this cost before asking permission to proceed.")

with st.expander("View the core LangGraph pattern"):
    st.code(
        '''graph = StateGraph(PipelineState)
graph.add_node("discover", discover_node)
graph.add_node("research_competitor", research_node)
graph.add_node("quality_review", review_node, defer=True)
graph.add_node("synthesize", synthesize_node)

graph.add_edge(START, "discover")
graph.add_conditional_edges("discover", fan_out, ["research_competitor"])
graph.add_edge("research_competitor", "quality_review")
graph.add_edge("quality_review", "synthesize")
graph.add_edge("synthesize", END)''',
        language="python",
    )

st.warning(
    "This project uses LangGraph for orchestration and state management. It intentionally uses the "
    "official OpenAI SDK for structured model calls instead of the LangChain OpenAI wrapper, avoiding "
    "the version-coupling issue that previously caused `langchain.verbose` failures."
)
