# onprem-rag

An on-premise retrieval-augmented generation platform: index internal knowledge sources (a wiki, a CRM, GitLab, or a folder of documents), keep the index in sync as they change, and expose an OpenAI-compatible chat API that any chat front end can talk to. Everything runs locally: embeddings with sentence-transformers, vector search with FAISS, generation with a local model through Ollama.

This is a sanitised, generalised version of a platform I designed and built as the sole developer during a 2025 internship, where it served 50+ employees over three internal systems. All company data, connector customisations and names have been removed; the connectors are now configured entirely from environment variables and a JSON file, and a bundled demo corpus replaces the internal one.

```
                      +-------------------+        +----------------------+
  MediaWiki --------> |                   |        |  OpenAI-compatible   |   Open WebUI,
  SuiteCRM  --------> |  sources/         |------> |  API (Flask)         | <-- curl, any
  GitLab    --------> |  chunk by section |        |  /v1/chat/completions|     OpenAI client
  local folder -----> |                   |        |  /health /rebuild    |
                      +---------+---------+        |  /webhook            |
                                |                  +-----------+----------+
                                v                              |
                      +-------------------+                    v
                      |  FAISS index      |<------+   +-------------------+
                      |  persisted store  |       +---|  query engine     |---> Ollama (local LLM)
                      +-------------------+           |  top-k + prompt   |     or extractive fallback
                                                      +-------------------+
```

## Try it in two minutes

```bash
git clone https://github.com/felixvhp/onprem-rag && cd onprem-rag
python -m venv venv && source venv/bin/activate
pip install -e ".[embeddings,dev]"
python demo/run_demo.py
```

The demo indexes a small synthetic wiki for a fictional robot fleet (`demo/corpus`), answers three questions, and scores the retriever on 15 labelled queries. If [Ollama](https://ollama.com) is running with a model pulled (`ollama pull llama3.1:8b`), answers are generated; otherwise the platform falls back to returning the retrieved passages, so the demo always runs. Add `--serve` to start the API on port 5000, then point Open WebUI at `http://localhost:5000` or call it directly:

```bash
curl -s localhost:5000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"What is the API rate limit?"}],"stream":true}'
```

No model download at all: set `EMBED_MODEL=hashing` to use a built-in hashed bag-of-words embedding. Retrieval quality drops to lexical matching, but it is enough for tests and for trying the plumbing on a laptop.

## What it does

- **Section-aware chunking.** Pages are split on headings first, then packed into token-bounded chunks with sentence overlap, so a chunk never straddles two topics and section titles travel with the text as metadata. Sections marked obsolete are skipped.
- **Pluggable sources.** `LocalDocsSource` (Markdown or text files), `MediaWikiSource` (MediaWiki API, wikitext cleaned with infoboxes turned into key-value lines, namespace and blacklist filters), `SuiteCRMSource` (REST v4.1, modules, fields and relationships declared in JSON, related records numbered so a model can count them) and `GitLabSource` (READMEs, docs folders and issues). Each source can load everything or a single item, which is what incremental updates use.
- **Persistent FAISS index** that loads instantly on restart and rebuilds only when a source changes.
- **Live updates** through `POST /webhook`, either a plain `{"action": "edit|create|delete", "ref": ...}` or the chat-notification text a MediaWiki instance posts, and `POST /rebuild` for a full refresh. Optional Slack-compatible notifications report every update.
- **OpenAI-compatible API** with streaming server-sent events, so the service is a drop-in model for Open WebUI and for any OpenAI client library. Answers end with a sources line listing the pages they came from.
- **Local generation** through Ollama, with an extractive fallback when no model server is reachable.
- **Evaluation harness** (`eval/evaluate.py`): Recall@k of the retriever on a labelled query set, which is the loop for tuning chunk size, overlap, embedding model and k without touching the generator.

## Running against your own systems

Copy `.env.example` to `.env`, set `SOURCE` and the variables for that source, then:

```bash
python -m onprem_rag build            # index once
python -m onprem_rag ask "question"   # answer from the command line
python -m onprem_rag serve --port 5000
```

Extras per source: `pip install -e ".[mediawiki]"` for MediaWiki, `".[gitlab]"` for GitLab. SuiteCRM needs only the core dependencies and an entity file like `examples/suitecrm_entities.json`.

A `Dockerfile` is included; mount a volume at `/data` to keep the index between restarts.

## Evaluating retrieval

```bash
python -m eval.evaluate --path demo/corpus --queries demo/queries.json
```

`demo/queries.json` maps questions to the page titles that answer them. A query is a hit at k when any chunk from a relevant page is in the top k. Write a similar file for your own corpus (twenty to fifty questions is enough to see differences) and compare settings by changing `CHUNK_MAX_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `EMBED_MODEL` or `TOP_K`, rebuilding, and re-running.

## Design notes

- **Why pre-chunk instead of letting the index split?** Sections are the unit people search for. Splitting on headings first keeps each chunk about one thing and makes the section title available to the prompt and to the sources line.
- **Why rebuild the FAISS index on every update?** Flat FAISS indexes are immutable. For tens of thousands of chunks a rebuild takes seconds and keeps the code simple; past that, swap `FaissVectorStore` for a mutable store, which is the one change the `RagIndex` class isolates.
- **Why an OpenAI-compatible surface?** It made the platform usable from an existing chat UI on day one, with no custom front end.

## Layout

```
onprem_rag/
  chunking.py      section-aware chunker with token overlap
  embedding.py     sentence-transformers wrapper and the hashing fallback
  llm.py           Ollama client and extractive fallback
  index.py         FAISS index: build, persist, load, replace, query, retrieve
  api.py           Flask app: /v1/chat/completions, /v1/models, /health, /rebuild, /webhook
  webhook.py       webhook payload parsing
  notifier.py      optional update notifications
  factory.py       wiring from settings
  sources/         local_docs, mediawiki, suitecrm, gitlab
demo/              sample corpus, labelled queries, run_demo.py
eval/evaluate.py   Recall@k harness
tests/             runs offline with the hashing embedding and the extractive fallback
```

## Tests

```bash
pip install -e ".[dev]" && pytest
```

## Licence

MIT.
