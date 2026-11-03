import json
import os

from eval.evaluate import recall_at_k
from onprem_rag.webhook import parse_webhook

QUERIES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo", "queries.json")


def test_recall_is_monotonic_and_reasonable(index):
    with open(QUERIES, encoding="utf-8") as handle:
        queries = json.load(handle)
    scores = recall_at_k(index, queries, ks=(1, 3, 5))
    assert scores[1] <= scores[3] <= scores[5]
    assert scores[5] >= 0.8


def test_webhook_json_and_mediawiki_formats():
    assert parse_webhook({"action": "delete", "ref": "page.md"}) == ("delete", "page.md")
    assert parse_webhook({"content": "Alice (talk) edited [Setup](<https://wiki.example/Setup>) with comment"}) == ("edit", "https://wiki.example/Setup")
    assert parse_webhook({"content": "nothing useful"}) == ("", "")
