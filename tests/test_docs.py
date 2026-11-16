import re
from pathlib import Path

import pytest

from app.platforms.registry import all_platforms

ROOT = Path(__file__).resolve().parent.parent
ENV_CALL = re.compile(r"""\benv\(\s*["']([A-Z0-9_]+)["']""")


def variables_read_by_code() -> set[str]:
    names = set()
    for source in (ROOT / "app").rglob("*.py"):
        names.update(ENV_CALL.findall(source.read_text()))
    return names


def variables_in_env_example() -> set[str]:
    names = set()
    for line in (ROOT / ".env.example").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            names.add(line.split("=", 1)[0])
    return names


def test_code_reads_some_variables():
    assert {"MASTODON_ACCESS_TOKEN", "BLUESKY_HANDLE", "GITHUB_TOKEN"} <= variables_read_by_code()


def test_env_example_lists_every_variable_the_code_reads():
    missing = variables_read_by_code() - variables_in_env_example()
    assert not missing, f"Add to .env.example: {sorted(missing)}"


def test_env_example_has_no_stale_variables():
    stale = variables_in_env_example() - variables_read_by_code()
    assert not stale, f"Not used by the code: {sorted(stale)}"


def test_env_example_contains_no_secret_values():
    for line in (ROOT / ".env.example").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            name, value = line.split("=", 1)
            if name.endswith(("TOKEN", "KEY", "PASSWORD", "HANDLE")):
                assert value == "", f"{name} must be empty in .env.example"


def test_gitignore_protects_the_real_env_file():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in lines


@pytest.fixture(scope="module")
def readme() -> str:
    path = ROOT / "README.md"
    assert path.exists(), "README.md is missing"
    return path.read_text()


def test_readme_explains_how_to_run_the_server(readme):
    assert "uvicorn app.main:app --host 0.0.0.0 --port 4000" in readme
    assert "http://localhost:4000/docs" in readme
    assert "pip install -r requirements.txt" in readme
    assert "pytest" in readme


def test_readme_documents_the_endpoint_with_sample_request_and_response(readme):
    assert "POST http://localhost:4000/posting" in readme
    assert "curl" in readme
    assert '"results"' in readme
    assert '"public_access"' in readme
    assert "422" in readme


def test_readme_covers_every_platform(readme):
    for platform in all_platforms():
        assert platform.name in readme, f"README does not mention {platform.name}"


def test_readme_documents_every_environment_variable(readme):
    for name in variables_read_by_code():
        assert name in readme, f"README does not document {name}"


def test_readme_points_to_env_example(readme):
    assert ".env.example" in readme


LIVE_RESULTS = ROOT / "docs" / "live-results.json"
SERVER_LOG = ROOT / "docs" / "server.log"


def test_readme_lists_every_live_post_link(readme):
    import json

    results = json.loads(LIVE_RESULTS.read_text())["results"]
    links = [r["posted_url"] for r in results if r["posted_url"]]
    assert links, "docs/live-results.json has no posted links"
    for link in links:
        assert link in readme, f"README is missing {link}"


def test_readme_embeds_the_raw_live_results_json(readme):
    import json

    pretty = json.dumps(json.loads(LIVE_RESULTS.read_text()), indent=2)
    assert pretty in readme


def test_readme_embeds_the_server_log(readme):
    for line in SERVER_LOG.read_text().splitlines():
        if line.strip():
            assert line in readme, f"README is missing log line: {line}"


SCREENSHOTS = ["mastodon", "bluesky", "devto", "github-gist", "pastebin"]


def screenshot_files() -> dict[str, Path]:
    folder = ROOT / "docs" / "screenshots"
    found = {}
    for name in SCREENSHOTS:
        matches = sorted(folder.glob(f"{name}.*")) if folder.exists() else []
        if matches:
            found[name] = matches[0]
    return found


@pytest.mark.parametrize("name", SCREENSHOTS)
def test_screenshot_exists_for_every_successful_platform(name):
    path = screenshot_files().get(name)
    assert path is not None, f"docs/screenshots/{name}.* is missing"
    assert path.stat().st_size > 1000, f"{path.name} looks empty"


def test_readme_embeds_every_screenshot(readme):
    for name, path in screenshot_files().items():
        reference = f"docs/screenshots/{path.name}"
        assert f"]({reference})" in readme, f"README does not embed {reference}"
