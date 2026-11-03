"""End-to-end demo: index the sample corpus, answer a few questions, score the retriever.

    python demo/run_demo.py            # uses Ollama if it is running, otherwise the extractive fallback
    python demo/run_demo.py --serve    # then also start the OpenAI-compatible API on port 5000
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from onprem_rag.config import Settings  # noqa: E402
from onprem_rag.factory import build_index, build_source, load_or_build  # noqa: E402
from eval.evaluate import recall_at_k  # noqa: E402

QUESTIONS = [
    "How long does a full charge take, and when do robots go back to the dock?",
    "A robot keeps saying payload rejected. What should I check?",
    "Which firewall ports does the fleet need?",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    os.environ.setdefault("STORAGE_DIR", os.path.join(here, "storage"))
    os.environ.setdefault("ASSISTANT_DOMAIN", "the Halden Robotics Atlas fleet documentation")
    os.environ.setdefault("MODEL_ID", "atlas-docs-rag")
    settings = Settings.from_env()

    source = build_source("local", settings, os.path.join(here, "corpus"))
    index = load_or_build(build_index(settings), source, rebuild=args.rebuild)
    print(f"\nIndex: {index.stats()}\n")

    for question in QUESTIONS:
        print(f"Q: {question}\nA: ", end="", flush=True)
        for delta in index.query(question):
            print(delta, end="", flush=True)
        print("\n")

    import json

    with open(os.path.join(here, "queries.json"), encoding="utf-8") as handle:
        queries = json.load(handle)
    scores = recall_at_k(index, queries)
    print("Retriever evaluation on", len(queries), "labelled queries:", ", ".join(f"Recall@{k} {v:.0%}" for k, v in scores.items()))

    if args.serve:
        from onprem_rag.api import create_app

        print("\nServing on http://localhost:5000 (POST /v1/chat/completions). Point Open WebUI at it, or try:")
        print("  curl -s localhost:5000/v1/chat/completions -H 'Content-Type: application/json' "
              "-d '{\"messages\":[{\"role\":\"user\",\"content\":\"What is the API rate limit?\"}]}'")
        create_app(index, source, settings).run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
