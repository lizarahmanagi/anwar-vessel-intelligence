#!/usr/bin/env python3
"""
Vector store for BlueRoute Shipping Intelligence.

Stores every daily report (markdown chunks) and every vessel record into a
persistent Chroma vector database so historical data can be searched later.

Storage layout (all under the mounted /app/weekly_data volume in Docker,
so data survives redeploys):
    weekly_data/vector_db/          -> Chroma persistent data
    weekly_data/.cache/chroma/      -> embedding model cache (downloaded once)
"""

import os
import csv
import glob
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Point HOME at the mounted weekly_data volume so the Chroma ONNX embedding
# model cache (~80 MB) is downloaded once and persists across redeploys.
_WEEKLY_DIR = os.path.join(PROJECT_DIR, "weekly_data")
os.environ.setdefault("HOME", _WEEKLY_DIR)
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

STORE_DIR = os.path.join(_WEEKLY_DIR, "vector_db")
COLLECTION = "vessel_reports"


class VectorStore:
    """Chroma-backed persistent store for daily reports and vessel rows."""

    def __init__(self, store_dir=STORE_DIR, collection=COLLECTION):
        self.store_dir = store_dir or STORE_DIR
        self.collection_name = collection
        self._client = None
        self._collection = None

    def _connect(self):
        if self._client is None:
            import chromadb
            os.makedirs(self.store_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.store_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    @staticmethod
    def chunk_report(markdown_text, chunk_size=1500, overlap_lines=4):
        """Split a markdown report into overlapping chunks at line boundaries."""
        lines = markdown_text.split("\n")
        chunks = []
        current = []
        current_len = 0
        for line in lines:
            if current and current_len + len(line) > chunk_size:
                chunks.append("\n".join(current))
                current = current[-overlap_lines:] + [line]
                current_len = sum(len(l) for l in current)
            else:
                current.append(line)
                current_len += len(line)
        if current:
            chunks.append("\n".join(current))
        return chunks

    def save_report(self, markdown_text, date_str=None, csv_rows=None):
        """Persist one daily report (and optionally its vessel rows).

        Never raises: a vector-store problem must not block the daily email.
        Returns the number of records stored (0 on failure).
        """
        try:
            date_str = date_str or datetime.now().strftime("%d_%m_%Y")
            collection = self._connect()

            ids, documents, metadatas = [], [], []
            for i, chunk in enumerate(self.chunk_report(markdown_text)):
                ids.append(f"{date_str}_report_{i}")
                documents.append(chunk)
                metadatas.append({"date": date_str, "kind": "report", "chunk": i})

            if csv_rows:
                for j, row in enumerate(csv_rows):
                    text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
                    if not text.strip():
                        continue
                    ids.append(f"{date_str}_vessel_{j}")
                    documents.append(text)
                    metadatas.append({
                        "date": date_str,
                        "kind": "vessel",
                        "vessel_name": str(row.get("Vessel_Name", "")),
                        "cargo_type": str(row.get("Cargo_Type", "")),
                        "section": str(row.get("Section", "")),
                        "local_agent": str(row.get("Local_Agent", "")),
                    })

            if ids:
                collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                logger.info(f"🧠 Vector store: saved {len(ids)} records for {date_str}")
            return len(ids)

        except Exception as e:
            logger.warning(f"⚠️  Vector store skipped: {str(e)}")
            return 0

    def query(self, text, n_results=5, where=None):
        """Semantic search over stored reports/vessels."""
        collection = self._connect()
        return collection.query(query_texts=[text], n_results=n_results, where=where)

    def count(self):
        """Total records stored."""
        try:
            return self._connect().count()
        except Exception:
            return 0


def read_csv_rows(csv_file):
    """Read the extracted CSV into a list of dicts (never raises)."""
    try:
        if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
            return []
        with open(csv_file, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        logger.warning(f"⚠️  Could not read CSV for vector store: {str(e)}")
        return []


def main():
    """CLI: store the latest report and print collection stats."""
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)

    reports = sorted(
        glob.glob(os.path.join(PROJECT_DIR, "reports", "*.md")),
        key=os.path.getmtime,
    )
    if not reports:
        print("No reports found")
        return 1

    latest = reports[-1]
    with open(latest, encoding="utf-8") as f:
        content = f.read()

    store = VectorStore()
    rows = read_csv_rows(os.path.join(PROJECT_DIR, "vessels_data.csv"))
    n = store.save_report(content, csv_rows=rows)
    print(f"Stored {n} records from {os.path.basename(latest)}; collection count = {store.count()}")
    return 0


if __name__ == "__main__":
    exit(main())
