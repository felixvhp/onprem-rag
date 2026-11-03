"""OpenAI-compatible HTTP API around a RagIndex, plus operational endpoints.

``/v1/chat/completions`` and ``/v1/models`` make the service a drop-in backend
for chat front ends such as Open WebUI; ``/health``, ``/rebuild`` and
``/webhook`` are for operators and for keeping the index in sync with the source.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from .config import Settings
from .index import RagIndex
from .logging_setup import logger
from .notifier import Notifier
from .sources.base import BaseSource
from .webhook import parse_webhook


def create_app(index: RagIndex, source: BaseSource, settings: Settings, notifier: Notifier | None = None) -> Flask:
    app = Flask(__name__)
    CORS(app)
    notifier = notifier or Notifier(None)
    model_id = settings.model_id

    def _chunk(chunk_id: str, created: int, delta: dict, finish: str | None) -> str:
        payload = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_id,
            "choices": [{"index": 0, "delta": delta, "logprobs": None, "finish_reason": finish}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    @app.post("/v1/chat/completions")
    def chat_completions():
        data = request.get_json(silent=True) or {}
        messages = data.get("messages") or []
        user_message = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        if not user_message:
            return jsonify({"error": "No user message provided"}), 400
        if not index.ready:
            return jsonify({"error": "Index is not ready"}), 503

        if data.get("stream", False):
            def generate():
                chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                created = int(time.time())
                yield _chunk(chunk_id, created, {"role": "assistant", "content": ""}, None)
                try:
                    for delta in index.query(user_message):
                        if delta:
                            yield _chunk(chunk_id, created, {"content": delta}, None)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Query failed: %s", exc)
                    yield _chunk(chunk_id, created, {"content": f"Error: {exc}"}, None)
                yield _chunk(chunk_id, created, {}, "stop")
                yield "data: [DONE]\n\n"

            return Response(
                generate(),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        try:
            answer = index.answer(user_message)
        except Exception as exc:  # noqa: BLE001
            logger.error("Query failed: %s", exc)
            return jsonify({"error": str(exc)}), 500
        return jsonify(
            {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_id,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": len(user_message.split()),
                    "completion_tokens": len(answer.split()),
                    "total_tokens": len(user_message.split()) + len(answer.split()),
                },
            }
        )

    @app.get("/v1/models")
    def list_models():
        return jsonify({"object": "list", "data": [{"id": model_id, "object": "model", "created": int(time.time()), "owned_by": "local"}]})

    @app.get("/health")
    def health():
        return jsonify({"status": "healthy" if index.ready else "starting", "source": source.name, "timestamp": datetime.now().isoformat(), **index.stats()})

    @app.post("/rebuild")
    def rebuild():
        try:
            documents = source.load_all()
            index.build(documents)
            notifier.send("rebuild", source.name, True, chunks_after=len(index.documents))
            return jsonify({"status": "success", "chunks_indexed": len(index.documents)})
        except Exception as exc:  # noqa: BLE001
            logger.error("Rebuild failed: %s", exc)
            notifier.send("rebuild", source.name, False, error=str(exc))
            return jsonify({"status": "error", "error": str(exc)}), 500

    @app.post("/webhook")
    def webhook():
        """Apply a single-document change: JSON ``{"action": "edit|create|delete", "ref": ...}``
        or a MediaWiki chat notification in a ``content`` field."""
        payload = request.get_json(silent=True)
        if payload is None:
            try:
                payload = json.loads(request.data or b"{}")
            except json.JSONDecodeError:
                return jsonify({"error": "Body must be JSON"}), 400
        action, ref = parse_webhook(payload)
        if not action:
            return jsonify({"error": "Could not parse webhook"}), 400
        prefix = source.doc_prefix(ref)
        try:
            if action == "delete":
                before, after = index.remove(prefix)
            else:
                before, after = index.replace(prefix, source.load_one(ref))
        except NotImplementedError:
            return jsonify({"error": f"Source '{source.name}' does not support single-document updates"}), 400
        except Exception as exc:  # noqa: BLE001
            logger.error("Webhook %s for %s failed: %s", action, ref, exc)
            notifier.send(action, ref, False, error=str(exc))
            return jsonify({"status": "error", "error": str(exc)}), 500
        notifier.send(action, ref, True, chunks_before=before, chunks_after=after)
        return jsonify({"status": "success", "action": action, "ref": ref, "chunks_before": before, "chunks_after": after})

    return app
