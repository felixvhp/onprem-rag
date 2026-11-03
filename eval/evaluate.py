"""Retrieval evaluation: Recall@k over a labelled query set.

Each query lists the page titles that contain its answer. A query is a hit at k
when any chunk from a relevant page appears in the top-k retrieved chunks. This
isolates the retriever (chunking, embeddings, k) from the generator, which is the
loop used to tune the platform: change a setting, rebuild, re-run.

    python -m eval.evaluate --path demo/corpus --queries demo/queries.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from onprem_rag.config import Settings
from onprem_rag.factory import build_index, build_source, load_or_build
from onprem_rag.index import RagIndex


def recall_at_k(index: RagIndex, queries: list[dict], ks: tuple[int, ...] = (1, 3, 5)) -> dict[int, float]:
    hits = {k: 0 for k in ks}
    for item in queries:
        nodes = index.retrieve(item["query"], top_k=max(ks))
        titles = [n.node.metadata.get("title", "") for n in nodes]
        relevant = set(item["relevant"])
        for k in ks:
            if any(t in relevant for t in titles[:k]):
                hits[k] += 1
    return {k: hits[k] / len(queries) for k in ks}


def main(argv: list[str] | None = None) -> dict[int, float]:
    parser = argparse.ArgumentParser(description="Recall@k of the retriever on a labelled query set")
    parser.add_argument("--path", default="demo/corpus")
    parser.add_argument("--queries", default="demo/queries.json")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    source = build_source("local", settings, args.path)
    index = load_or_build(build_index(settings), source, rebuild=args.rebuild)
    with open(args.queries, encoding="utf-8") as handle:
        queries = json.load(handle)

    scores = recall_at_k(index, queries)
    print(f"\nRetriever: embeddings={settings.embed_model}, chunk={settings.chunk_max_tokens} tokens, overlap={settings.chunk_overlap_tokens}")
    print(f"{len(queries)} labelled queries over {index.stats()['total_documents']} pages ({index.stats()['total_chunks']} chunks)\n")
    for k, score in scores.items():
        print(f"  Recall@{k}: {score:.0%}")
    return scores


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    main()
