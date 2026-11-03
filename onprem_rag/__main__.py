"""Command line: ``python -m onprem_rag serve|build|ask``."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from .config import Settings
from .factory import build_index, build_source, load_or_build
from .logging_setup import logger


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="onprem_rag", description="On-premise RAG platform")
    parser.add_argument("--source", choices=["local", "mediawiki", "suitecrm", "gitlab"], default=os.getenv("SOURCE", "local"))
    parser.add_argument("--path", help="folder to index when --source local")
    parser.add_argument("--rebuild", action="store_true", help="ignore any persisted index")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the HTTP API")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")))
    sub.add_parser("build", help="build the index and exit")
    ask = sub.add_parser("ask", help="answer one question from the command line")
    ask.add_argument("question")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    source = build_source(args.source, settings, args.path)
    index = load_or_build(build_index(settings), source, rebuild=args.rebuild)

    if args.command == "build":
        logger.info("Index ready: %s", index.stats())
    elif args.command == "ask":
        for delta in index.query(args.question):
            print(delta, end="", flush=True)
        print()
    else:
        from .api import create_app
        from .notifier import Notifier

        app = create_app(index, source, settings, Notifier(settings.slack_webhook_url))
        logger.info("Serving %s on http://%s:%d (POST /v1/chat/completions)", source.name, args.host, args.port)
        app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
