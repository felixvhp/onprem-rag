"""Single console logger shared by every module."""

import logging
import os
import sys

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

for noisy in ("httpx", "huggingface_hub", "urllib3", "sentence_transformers"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("onprem_rag")
