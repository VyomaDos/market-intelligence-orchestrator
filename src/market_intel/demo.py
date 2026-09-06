from datetime import UTC, datetime


def build_demo() -> tuple[dict, str]:
    """Return a deterministic, no-cost sample that exercises the report experience."""
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    briefing = {
        "title": "NVIDIA AI Chips Competitive Intelligence Briefing",
        "demo": True,
        "quality_score": 0.87,
        "source_count": 12,
        "competitors": [
            {"competitor": {"name": "AMD"}},
            {"competitor": {"name": "Intel"}},
            {"competitor": {"name": "Google Cloud TPU"}},
        ],
        "cost": {
            "total_cost_usd": 0.0,
            "ydc_cost_usd": 0.0,
            "ydc_calls": 0,
            "llm_cost_usd": 0.0,
            "llm_calls": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
        },
    }
    markdown = f"""# NVIDIA AI Chips Competitive Intelligence Briefing

> **PROJECT-REVIEW DEMO** — Prepared sample; no API calls were made. Run live research to refresh or validate these illustrative findings.

**Prepared for:** Product management

*Generated {generated_at} · Demonstration quality 87% · 12 representative sources*

> ## NVIDIA’s software ecosystem remains its strongest defense, while custom accelerators and lower-cost alternatives increase pressure on workload-specific buying decisions.
> Protect CUDA-led developer preference while proving measurable total-cost-of-ownership advantages for inference workloads.

## Executive brief

### Effect

- AI infrastructure buyers have more credible alternatives across training, inference, and cloud-native workloads.
- Competitive differentiation is shifting from peak chip performance toward software maturity, availability, energy efficiency, and total cost of ownership.
- Hyperscaler-designed accelerators can reduce the addressable market for general-purpose GPUs inside their own clouds.

### Rationale

- **AMD is the closest merchant-silicon challenger.** Its Instinct portfolio and ROCm software create a credible alternative for buyers seeking supply diversity and open software options. [AMD Instinct](https://www.amd.com/en/products/accelerators/instinct.html)
- **Intel competes through portfolio breadth and enterprise reach.** Gaudi accelerators emphasize price-performance and Ethernet-based scaling for AI systems. [Intel Gaudi](https://www.intel.com/content/www/us/en/products/details/processors/ai-accelerators/gaudi.html)
- **Google’s TPU changes the buying model.** Cloud customers can consume purpose-built accelerators as a managed platform rather than purchase general-purpose GPUs. [Google Cloud TPU](https://cloud.google.com/tpu)

### Operations

| Priority | Owner | Action | Timeframe | Success measure |
|---|---|---|---|---|
| Now | VP Product | Publish workload-level training and inference TCO comparisons | 30 days | Validated benchmarks for five priority workloads |
| Now | Developer Platform | Reduce migration friction from alternative software stacks | 60 days | 20% faster time-to-first-model for new teams |
| Next | Product Marketing | Build segment-specific competitive playbooks | 90 days | Playbooks adopted in 80% of strategic opportunities |
| Next | Strategy | Track hyperscaler accelerator adoption and displacement signals | Quarterly | Decision dashboard reviewed each quarter |

## Competitive snapshot

| Competitor | Primary challenge | Strategic angle | Signal to monitor |
|---|---|---|---|
| AMD | Merchant GPU alternative | Open ecosystem and supply diversification | ROCm adoption and large-cluster deployments |
| Intel | AI accelerator plus enterprise portfolio | Price-performance and Ethernet scaling | Gaudi customer wins and roadmap execution |
| Google Cloud TPU | Purpose-built cloud accelerator | Vertically integrated cloud AI platform | TPU availability beyond Google-native workloads |

## Recommended product questions

1. Which customer workloads value CUDA compatibility enough to outweigh accelerator price differences?
2. Where does inference economics create the largest opening for specialized or custom silicon?
3. Which developer workflows still create avoidable migration or deployment friction?
4. What early indicators would show hyperscaler accelerators displacing general-purpose GPU demand?

## Evidence appendix

### Representative primary sources

- [NVIDIA Data Center](https://www.nvidia.com/en-us/data-center/)
- [NVIDIA CUDA](https://developer.nvidia.com/cuda-toolkit)
- [AMD Instinct Accelerators](https://www.amd.com/en/products/accelerators/instinct.html)
- [AMD ROCm](https://www.amd.com/en/products/software/rocm.html)
- [Intel Gaudi Accelerators](https://www.intel.com/content/www/us/en/products/details/processors/ai-accelerators/gaudi.html)
- [Google Cloud TPU](https://cloud.google.com/tpu)

## Demo notes

- This prepared report demonstrates the interface, executive structure, citations, action orientation, downloads, and cost reporting.
- It is intentionally free to load and does not represent a fresh research run.
- A live run uses the selected freshness window, dynamically discovers competitors, validates citations, and reports actual API cost.

## Run cost

- You.com Search: **$0.0000** (0 calls)
- LLM: **$0.0000** (0 calls)
- Total API cost: **$0.0000**
"""
    return briefing, markdown
