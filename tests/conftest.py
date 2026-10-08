import os

import pytest
import httpx
from starlette.testclient import _TestClientTransport

original_httpx_send = httpx.Client.send


os.environ["OPENAI_API_KEY"] = "test-only-no-network"
os.environ["LANGSMITH_TRACING"] = "false"


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not call live model, GitHub, or retrieval services")
    def local_asgi_only(client, *args, **kwargs):
        if isinstance(client._transport, _TestClientTransport):
            return original_httpx_send(client, *args, **kwargs)
        return blocked()
    monkeypatch.setattr("requests.sessions.Session.request", blocked)
    monkeypatch.setattr("httpx.Client.send", local_asgi_only)
    monkeypatch.setattr("httpx.AsyncClient.send", blocked)
