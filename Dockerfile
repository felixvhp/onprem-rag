FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY onprem_rag ./onprem_rag
RUN pip install --no-cache-dir ".[embeddings,mediawiki]"
COPY demo ./demo
COPY eval ./eval
ENV SOURCE=local DOCS_PATH=/app/demo/corpus STORAGE_DIR=/data/storage PORT=5000
EXPOSE 5000
CMD ["python", "-m", "onprem_rag", "serve"]
