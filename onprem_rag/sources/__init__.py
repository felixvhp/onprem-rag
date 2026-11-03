"""Knowledge sources. Each one turns an external system into chunked Documents."""

from .base import BaseSource
from .local_docs import LocalDocsSource

__all__ = ["BaseSource", "LocalDocsSource"]
