from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright

APP_URL = "http://localhost:8501"
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
OUTPUT_PATH = Path("demo/market-intelligence-orchestrator-demo.webm")


def pause(page, milliseconds: int = 900) -> None:
    page.wait_for_timeout(milliseconds)


def caption(page, message: str) -> None:
    page.evaluate(
        """message => {
            let banner = document.getElementById('demo-caption');
            if (!banner) {
                banner = document.createElement('div');
                banner.id = 'demo-caption';
                Object.assign(banner.style, {
                    position: 'fixed', left: '50%', bottom: '28px', transform: 'translateX(-50%)',
                    zIndex: '999999', padding: '12px 22px', borderRadius: '10px',
                    background: 'rgba(15, 23, 42, 0.94)', color: 'white', font: '600 18px Arial',
                    boxShadow: '0 8px 24px rgba(0,0,0,.28)', transition: 'opacity .2s'
                });
                document.body.appendChild(banner);
            }
            banner.textContent = message;
        }""",
        message,
    )


def spotlight(page, locator, message: str) -> None:
    caption(page, message)
    locator.scroll_into_view_if_needed()
    locator.evaluate(
        """element => {
            const box = element.closest(
                '[data-testid="stTextInput"], [data-testid="stSelectbox"], '
                + '[data-testid="stCheckbox"], [data-testid="stMetric"]'
            ) || element;
            box.style.transition = 'box-shadow .2s, background .2s';
            box.style.boxShadow = '0 0 0 4px #ff4b4b';
            box.style.background = 'rgba(255, 75, 75, .08)';
            setTimeout(() => {
                box.style.boxShadow = '';
                box.style.background = '';
            }, 850);
        }"""
    )
    pause(page)


def skim_to(page, heading: str, message: str) -> None:
    caption(page, message)
    locator = page.get_by_role("heading", name=heading, exact=True)
    locator.evaluate(
        "element => element.scrollIntoView({behavior: 'smooth', block: 'start'})"
    )
    pause(page, 500)
    locator.evaluate("element => element.style.color = '#ff4b4b'")
    pause(page, 1200)
    locator.evaluate("element => element.style.color = ''")


def skim_fraction(page, fraction: float, message: str) -> None:
    caption(page, message)
    page.evaluate(
        "fraction => window.scrollTo({top: document.body.scrollHeight * fraction, behavior: 'smooth'})",
        fraction,
    )
    pause(page, 1400)


def main() -> None:
    if not CHROME_PATH.exists():
        raise FileNotFoundError(f"Chrome was not found at {CHROME_PATH}")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with (
        TemporaryDirectory(prefix="market-intel-recording-") as recording_dir,
        sync_playwright() as playwright,
    ):
        browser = playwright.chromium.launch(executable_path=str(CHROME_PATH), headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=recording_dir,
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=30_000)
        page.get_by_role("heading", name="Market Intelligence Orchestrator").wait_for()
        caption(page, "Configure a fresh competitor-intelligence run")
        pause(page, 1400)

        spotlight(page, page.get_by_label("Target company"), "Choose any target company")
        spotlight(page, page.get_by_label("Market/category"), "Define the market to analyze")
        spotlight(
            page,
            page.get_by_role("combobox", name="Data freshness"),
            "Control how recent the evidence must be",
        )
        spotlight(
            page,
            page.get_by_role("combobox", name="Primary audience"),
            "Tailor the briefing to its decision-maker",
        )
        spotlight(
            page,
            page.get_by_test_id("stMetric").filter(has_text="Estimated total"),
            "Review cost before any API call",
        )
        spotlight(page, page.get_by_role("checkbox"), "The user explicitly approves paid research")

        caption(page, "Load a zero-cost project-review sample")
        page.get_by_role("button", name="Load project-review demo").click()
        page.get_by_text("Project-review demo · Prepared sample · No API calls made").wait_for()
        pause(page, 1400)
        skim_to(page, "Executive brief", "Skim the decision, impact, and evidence")
        skim_to(page, "Operations", "Turn findings into owned, measurable actions")
        skim_to(page, "Competitive snapshot", "Compare the market at a glance")
        skim_to(page, "Recommended product questions", "Leave the team with decisions to investigate")
        skim_to(page, "Evidence appendix", "Every briefing includes source links")
        skim_to(page, "Run cost", "Estimated and actual provider costs stay visible")

        page.goto(f"{APP_URL}/How_It_Works", wait_until="domcontentloaded", timeout=30_000)
        page.get_by_role("heading", name="How the research system works").wait_for()
        caption(page, "See the real LangGraph orchestration and agent handoffs")
        pause(page, 1800)
        skim_fraction(page, 0.38, "Six focused agents divide the research workflow")
        skim_fraction(page, 0.68, "Parallel fan-out, state reducers, and checkpoints")
        skim_fraction(page, 1.0, "Understand every tool call and expected cost")
        caption(page, "Market Intelligence Orchestrator · Ready for project review")
        pause(page, 1800)

        video = page.video
        context.close()
        video.save_as(OUTPUT_PATH)
        browser.close()

    print(f"Saved demo recording to {OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
