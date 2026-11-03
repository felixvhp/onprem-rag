import json

import pytest

from onprem_rag.api import create_app


@pytest.fixture
def client(index, source, settings):
    app = create_app(index, source, settings)
    app.config["TESTING"] = True
    return app.test_client()


def test_models_and_health(client):
    assert client.get("/v1/models").get_json()["data"][0]["id"] == "onprem-rag"
    health = client.get("/health").get_json()
    assert health["status"] == "healthy" and health["total_chunks"] > 0 and health["source"] == "local"


def test_chat_completion_non_streaming(client):
    resp = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "What is the API rate limit?"}]})
    body = resp.get_json()
    assert resp.status_code == 200 and body["object"] == "chat.completion"
    assert "600 requests per minute" in body["choices"][0]["message"]["content"]


def test_chat_completion_streaming_is_valid_sse(client):
    resp = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "What is the API rate limit?"}], "stream": True})
    assert resp.status_code == 200 and resp.mimetype == "text/event-stream"
    events = [line[len("data: "):] for line in resp.get_data(as_text=True).split("\n") if line.startswith("data: ")]
    assert events[-1] == "[DONE]"
    chunks = [json.loads(e) for e in events[:-1]]
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    text = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
    assert "600 requests per minute" in text


def test_missing_user_message_is_400(client):
    assert client.post("/v1/chat/completions", json={"messages": []}).status_code == 400


def test_webhook_updates_and_deletes(client, index):
    before = index.stats()["total_chunks"]
    resp = client.post("/webhook", json={"action": "edit", "ref": "safety.md"})
    assert resp.status_code == 200 and resp.get_json()["chunks_after"] == before
    resp = client.post("/webhook", json={"action": "delete", "ref": "safety.md"})
    assert resp.status_code == 200 and resp.get_json()["chunks_after"] < before
    assert client.post("/webhook", json={"nonsense": True}).status_code == 400


def test_rebuild_restores_everything(client, index):
    client.post("/webhook", json={"action": "delete", "ref": "safety.md"})
    resp = client.post("/rebuild")
    assert resp.status_code == 200
    assert any(d.metadata["title"] == "Safety System" for d in index.documents)
