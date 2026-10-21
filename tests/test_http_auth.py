"""Tests for HTTP-mode authentication."""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from girafmcp.server import require_bearer_token, run_http_server


def _app() -> Starlette:
    async def ok(request: object) -> PlainTextResponse:
        return PlainTextResponse("ok")

    return Starlette(routes=[Route("/health", ok), Route("/sse", ok)])


class TestBearerToken:
    """Requests other than /health need the configured bearer token."""

    def test_rejects_missing_token(self):
        client = TestClient(require_bearer_token(_app(), "s3cret"))
        assert client.get("/sse").status_code == 401

    def test_rejects_wrong_token(self):
        client = TestClient(require_bearer_token(_app(), "s3cret"))
        assert client.get("/sse", headers={"Authorization": "Bearer nope"}).status_code == 401

    def test_accepts_correct_token(self):
        client = TestClient(require_bearer_token(_app(), "s3cret"))
        assert client.get("/sse", headers={"Authorization": "Bearer s3cret"}).status_code == 200

    def test_health_is_open(self):
        client = TestClient(require_bearer_token(_app(), "s3cret"))
        assert client.get("/health").status_code == 200


class TestBindPolicy:
    """Non-loopback binds without a token must refuse to start."""

    def test_refuses_public_bind_without_token(self, monkeypatch):
        monkeypatch.delenv("GIRAF_MCP_TOKEN", raising=False)
        with pytest.raises(SystemExit, match="GIRAF_MCP_TOKEN"):
            run_http_server(host="0.0.0.0", port=0)
