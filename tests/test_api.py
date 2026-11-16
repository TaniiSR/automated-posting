import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from app.schemas import PlatformResult, PostingResponse

MESSAGE = "Grow your visibility https://example.com"


class StubService:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or PostingResponse(
            success=True,
            results=[
                PlatformResult(
                    platform="A",
                    status="success",
                    posted_url="https://a.test/1",
                    public_access=True,
                    date="2026-11-15",
                    time="10:30:00",
                ),
                PlatformResult(platform="B", status="failed", error="Authentication failed"),
            ],
        )

    async def publish(self, message, url):
        self.calls.append((message, url))
        return self.response


@pytest.fixture
def stub():
    service = StubService()
    app.dependency_overrides[get_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture
def client(stub):
    return TestClient(app)


def test_valid_request_returns_results(client, stub):
    response = client.post("/posting", json={"message": MESSAGE})

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "results": [
            {
                "platform": "A",
                "status": "success",
                "posted_url": "https://a.test/1",
                "public_access": True,
                "date": "2026-11-15",
                "time": "10:30:00",
                "error": None,
            },
            {
                "platform": "B",
                "status": "failed",
                "posted_url": None,
                "public_access": False,
                "date": None,
                "time": None,
                "error": "Authentication failed",
            },
        ],
    }


def test_service_receives_message_and_extracted_url(client, stub):
    client.post("/posting", json={"message": MESSAGE})
    assert stub.calls == [(MESSAGE, "https://example.com")]


def test_all_platforms_failing_is_still_http_200(client, stub):
    stub.response = PostingResponse(
        success=False,
        results=[PlatformResult(platform="A", status="failed", error="down")],
    )
    response = client.post("/posting", json={"message": MESSAGE})
    assert response.status_code == 200
    assert response.json()["success"] is False


@pytest.mark.parametrize(
    "message, expected_text",
    [
        ("x" * 190 + " https://example.com", "200"),
        ("No link here", "exactly one"),
        ("Two https://a.com and https://b.com", "exactly one"),
        ("Local https://localhost", "Invalid CTA URL"),
        ("", "empty"),
    ],
)
def test_invalid_message_returns_422_with_readable_error(client, stub, message, expected_text):
    response = client.post("/posting", json={"message": message})

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["field"] == "message"
    assert expected_text in body["errors"][0]["message"]
    assert not body["errors"][0]["message"].startswith("Value error")
    assert stub.calls == []


def test_missing_message_field_returns_422(client, stub):
    response = client.post("/posting", json={})
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "message", "message": "Field required"}]
    assert stub.calls == []


def test_invalid_json_returns_422(client, stub):
    response = client.post(
        "/posting", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert stub.calls == []


def test_non_string_message_returns_422(client, stub):
    response = client.post("/posting", json={"message": 123})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "message"


def test_get_on_posting_is_not_allowed(client):
    assert client.get("/posting").status_code == 405


def test_docs_page_is_available(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_openapi_lists_posting_endpoint(client):
    schema = client.get("/openapi.json").json()
    assert "post" in schema["paths"]["/posting"]
