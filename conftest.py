import pytest
import allure
from pathlib import Path
from playwright.sync_api import sync_playwright


# ==========================================================
# STEP 1: ADD COMMAND LINE OPTIONS
# ==========================================================
def pytest_addoption(parser):
    """
    Adds command line options for test configuration.
    """

    parser.addoption(
        "--browser",
        default="chromium",
        help="Browser: chromium, firefox, webkit"
    )

    parser.addoption(
        "--headed",
        action="store_true",
        help="Run in headed (visible) mode"
    )

    parser.addoption(
        "--base-url",
        default="https://tutorialsninja.com/demo/",
        help="Base URL for tests"
    )

    parser.addoption(
        "--video",
        default="retain-on-failure",
        help="Record video: on, off, retain-on-failure"
    )

    parser.addoption(
        "--screenshot",
        default="only-on-failure",
        help="Take screenshot: on, off, only-on-failure"
    )

    parser.addoption(
        "--tracing",
        default="retain-on-failure",
        help="Tracing: on, off, retain-on-failure"
    )


# ==========================================================
# STEP 2: GET CONFIGURATION VALUE
# ==========================================================
def get_config_value(config, option_name):
    """
    Reads configuration values from command line or pytest.ini.
    """

    cmd_value = config.getoption(option_name)
    if cmd_value is not None:
        return cmd_value

    if option_name == "headed":
        ini_value = config.getini(option_name)
        return (
            ini_value.lower() == "true"
            if isinstance(ini_value, str)
            else ini_value
        )

    return config.getini(option_name)


# ==========================================================
# STEP 3: TRACK TEST RESULT
# ==========================================================
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Captures the test result (pass/fail/skip).
    """

    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


# ==========================================================
# STEP 4: BROWSER CONTEXT FIXTURE
# ==========================================================
@pytest.fixture(scope="function")
def browser_context(request):
    """
    Creates and manages Playwright browser context.
    """

    browser_name = get_config_value(request.config, "browser")
    headed_flag = get_config_value(request.config, "headed")
    video_option = get_config_value(request.config, "video")

    print(f"🎯 Starting browser: {browser_name}")
    print(f"🎯 Headless mode: {not headed_flag}")

    playwright = sync_playwright().start()

    if browser_name.lower() == "chromium":
        browser = playwright.chromium.launch(headless=not headed_flag)
    elif browser_name.lower() == "firefox":
        browser = playwright.firefox.launch(headless=not headed_flag)
    elif browser_name.lower() == "webkit":
        browser = playwright.webkit.launch(headless=not headed_flag)
    else:
        raise ValueError(f"Unsupported browser: {browser_name}")

    if video_option in ["on", "retain-on-failure"]:
        context = browser.new_context(
            record_video_dir="reports/videos"
        )
    else:
        context = browser.new_context()

    yield context

    print("🧹 Closing browser context...")
    context.close()
    browser.close()
    playwright.stop()


# ==========================================================
# STEP 5: PAGE FIXTURE
# ==========================================================
@pytest.fixture(scope="function")
def page(request, browser_context):
    """
    Creates a page and manages screenshots,
    videos and traces.
    """

    base_url = get_config_value(request.config, "base_url")
    screenshot_option = get_config_value(
        request.config, "screenshot"
    )
    tracing_option = get_config_value(
        request.config, "tracing"
    )
    video_option = get_config_value(
        request.config, "video"
    )

    print(f"🌐 Navigating to: {base_url}")

    if tracing_option in ["on", "retain-on-failure"]:
        browser_context.tracing.start(
            screenshots=True,
            snapshots=True,
            sources=True
        )

    page = browser_context.new_page()
    page.goto(base_url)

    yield page

    test_name = request.node.name
    test_failed = (
        hasattr(request.node, "rep_call")
        and request.node.rep_call.failed
    )

    print(
        f"📊 Test '{test_name}' result: "
        f"{'FAILED' if test_failed else 'PASSED'}"
    )

    # Save trace
    if tracing_option in ["on", "retain-on-failure"]:
        trace_path = (
            f"reports/traces/{test_name}_trace.zip"
        )

        browser_context.tracing.stop(
            path=trace_path
        )

        print(f"💾 Trace saved: {trace_path}")

    # Screenshot
    if (
        test_failed
        and screenshot_option in
        ["on", "only-on-failure"]
    ):
        screenshot_path = (
            f"reports/screenshots/{test_name}.png"
        )

        page.screenshot(path=screenshot_path)

        allure.attach.file(
            screenshot_path,
            name=f"{test_name}_screenshot",
            attachment_type=allure.attachment_type.PNG
        )

        print("📸 Screenshot attached")

    # Video
    if (
        test_failed
        and video_option in
        ["on", "retain-on-failure"]
    ):
        video_path = (
            page.video.path()
            if page.video
            else None
        )

        if (
            video_path
            and Path(video_path).exists()
        ):
            allure.attach.file(
                video_path,
                name=f"{test_name}_video",
                attachment_type=allure.attachment_type.WEBM
            )

            print("🎥 Video attached")