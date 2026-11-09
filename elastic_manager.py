"""
Elasticsearch Manager
=====================

Owns all interaction with Elasticsearch: index lifecycle, bulk indexing,
fuzzy search, and statistics.

Version: 3.0.0
"""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import NotFoundError, RequestError

from observability import logging as obs_logging, metrics

load_dotenv()
logger = obs_logging.get_logger("elastic-manager")

# =============================================================================
# CONFIGURATION
# =============================================================================

import os

ES_HOST: str = os.getenv("ES_HOST", "http://localhost:9200")
ES_USERNAME: str | None = os.getenv("ES_USERNAME")
ES_PASSWORD: str | None = os.getenv("ES_PASSWORD")
INDEX_NAME: str = os.getenv("ES_INDEX_NAME", "payflow_transactions")

INDEX_MAPPINGS: dict[str, Any] = {
    "properties": {
        "transaction_id": {"type": "keyword"},
        "description": {
            "type": "text",
            "analyzer": "standard",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
        },
        "ai_category": {"type": "keyword"},
        "amount": {"type": "float"},
        "amount_formatted": {"type": "keyword"},
        "currency": {"type": "keyword"},
        "confidence": {"type": "float"},
        "status": {"type": "keyword"},
        "timestamp": {"type": "date"},
        "indexed_at": {"type": "date"},
    }
}

# Columns the UI expects after retrieval
_UI_COLUMNS: list[str] = [
    "Amount", "Description", "AI Category", "Confidence", "Status",
]
_RENAME_MAP: dict[str, str] = {
    "amount_formatted": "Amount",
    "description": "Description",
    "ai_category": "AI Category",
    "confidence": "Confidence",
    "status": "Status",
}

# =============================================================================
# CLIENT
# =============================================================================

_client: Elasticsearch | None = None


def get_client() -> Elasticsearch:
    """Return a lazily-initialised Elasticsearch client."""
    global _client
    if _client is None:
        kwargs: dict[str, Any] = {
            "hosts": [ES_HOST],
            "retry_on_timeout": True,
            "max_retries": 3,
            "request_timeout": 30,
        }
        if ES_USERNAME and ES_PASSWORD:
            kwargs["basic_auth"] = (ES_USERNAME, ES_PASSWORD)
        _client = Elasticsearch(**kwargs)
        logger.info("elasticsearch_client_initialised", host=ES_HOST)
    return _client


# =============================================================================
# INDEX LIFECYCLE
# =============================================================================

def setup_index() -> bool:
    """Create the index with mappings if it does not already exist."""
    es = get_client()
    try:
        if not es.indices.exists(index=INDEX_NAME):
            es.indices.create(
                index=INDEX_NAME,
                mappings=INDEX_MAPPINGS,
                settings={"number_of_shards": 1, "number_of_replicas": 0},
            )
            logger.info("index_created", index=INDEX_NAME)
        return True
    except RequestError as exc:
        logger.error("index_creation_failed", error=str(exc))
        return False


def delete_index() -> bool:
    """Delete the index. Use with caution."""
    es = get_client()
    try:
        if es.indices.exists(index=INDEX_NAME):
            es.indices.delete(index=INDEX_NAME)
            logger.info("index_deleted", index=INDEX_NAME)
            return True
        logger.warning("index_not_found_for_delete", index=INDEX_NAME)
        return False
    except Exception as exc:
        logger.error("index_deletion_failed", error=str(exc), exc_info=True)
        return False


# =============================================================================
# INGESTION
# =============================================================================

def index_transactions(df: pd.DataFrame) -> int:
    """
    Bulk-index a DataFrame of categorised transactions.

    Args:
        df: DataFrame with columns ``Amount``, ``Description``,
            ``AI Category``, ``Confidence``, ``Status``.

    Returns:
        Number of documents successfully indexed.
    """
    if df.empty:
        logger.warning("index_transactions_called_with_empty_dataframe")
        return 0

    setup_index()
    es = get_client()
    start = time.perf_counter()

    try:
        actions: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            amount_str = str(row.get("Amount", "0.00"))
            amount_value, currency = _parse_amount(amount_str)
            description = str(row.get("Description", ""))

            doc_id = f"{description}_{amount_value}_{currency}"
            doc_id = doc_id.replace(" ", "_").lower()[:500]

            actions.append(
                {
                    "_index": INDEX_NAME,
                    "_id": doc_id,
                    "_source": {
                        "description": description,
                        "ai_category": row.get("AI Category", "Unknown"),
                        "amount": amount_value,
                        "amount_formatted": amount_str,
                        "currency": currency,
                        "confidence": float(row.get("Confidence", 0.0)),
                        "status": row.get("Status", "Unknown"),
                        "indexed_at": pd.Timestamp.utcnow().isoformat(),
                    },
                }
            )

        if not actions:
            return 0

        success, errors = helpers.bulk(
            es, actions, raise_on_error=False, raise_on_exception=False
        )

        duration = time.perf_counter() - start
        status = "success" if not errors else "partial"
        metrics.record_elasticsearch_query(duration, operation="bulk_index", status=status)

        logger.info(
            "bulk_index_completed",
            indexed=success,
            errors=len(errors),
            duration_ms=round(duration * 1000, 2),
        )
        return success

    except Exception as exc:
        duration = time.perf_counter() - start
        metrics.record_elasticsearch_query(duration, operation="bulk_index", status="error")
        logger.error("bulk_index_failed", error=str(exc), exc_info=True)
        return 0


def index_single_transaction(doc: dict[str, Any]) -> bool:
    """Index a single document. Returns True on success."""
    setup_index()
    es = get_client()
    try:
        description = str(doc.get("description", ""))
        amount = doc.get("amount", 0.0)
        doc_id = f"{description}_{amount}".replace(" ", "_").lower()[:500]
        doc = {**doc, "indexed_at": pd.Timestamp.utcnow().isoformat()}
        es.index(index=INDEX_NAME, id=doc_id, document=doc)
        logger.info("single_document_indexed", doc_id=doc_id)
        return True
    except Exception as exc:
        logger.error("single_document_index_failed", error=str(exc), exc_info=True)
        return False


# =============================================================================
# SEARCH & RETRIEVAL
# =============================================================================

def search_transactions(query: str, size: int = 100) -> pd.DataFrame:
    """
    Multi-match fuzzy search across description and AI category.
    """
    if not query or not query.strip():
        return get_all_transactions()

    es = get_client()
    start = time.perf_counter()

    try:
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["description^3", "description.keyword^2", "ai_category^2"],
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                    "max_expansions": 50,
                }
            },
            "size": size,
            "sort": [
                {"_score": {"order": "desc"}},
                {"indexed_at": {"order": "desc"}},
            ],
        }
        response = es.search(index=INDEX_NAME, body=body)
        df = _hits_to_dataframe(response["hits"]["hits"])

        duration = time.perf_counter() - start
        metrics.record_elasticsearch_query(duration, operation="search", status="success")
        logger.info(
            "search_completed",
            query=query,
            results=len(df),
            duration_ms=round(duration * 1000, 2),
        )
        return df

    except NotFoundError:
        logger.warning("search_index_missing", index=INDEX_NAME)
        return pd.DataFrame()
    except Exception as exc:
        duration = time.perf_counter() - start
        metrics.record_elasticsearch_query(duration, operation="search", status="error")
        logger.error("search_failed", query=query, error=str(exc), exc_info=True)
        return pd.DataFrame()


def get_all_transactions(size: int = 1000) -> pd.DataFrame:
    """Return all documents in the index, newest first."""
    es = get_client()
    start = time.perf_counter()
    try:
        body = {
            "query": {"match_all": {}},
            "size": size,
            "sort": [{"indexed_at": {"order": "desc"}}],
        }
        response = es.search(index=INDEX_NAME, body=body)
        df = _hits_to_dataframe(response["hits"]["hits"])

        duration = time.perf_counter() - start
        metrics.record_elasticsearch_query(duration, operation="get_all", status="success")
        logger.info("get_all_completed", count=len(df), duration_ms=round(duration * 1000, 2))
        return df

    except NotFoundError:
        logger.warning("get_all_index_missing", index=INDEX_NAME)
        return pd.DataFrame()
    except Exception as exc:
        duration = time.perf_counter() - start
        metrics.record_elasticsearch_query(duration, operation="get_all", status="error")
        logger.error("get_all_failed", error=str(exc), exc_info=True)
        return pd.DataFrame()


def get_transaction_count() -> int:
    """Return the total document count in the index."""
    es = get_client()
    try:
        return es.count(index=INDEX_NAME)["count"]
    except NotFoundError:
        return 0
    except Exception as exc:
        logger.error("count_failed", error=str(exc))
        return 0


def get_index_stats() -> dict[str, Any]:
    """Return storage and document statistics for the index."""
    es = get_client()
    try:
        stats = es.indices.stats(index=INDEX_NAME)["indices"][INDEX_NAME]["total"]
        return {
            "index_name": INDEX_NAME,
            "document_count": stats["docs"]["count"],
            "store_size_bytes": stats["store"]["size_in_bytes"],
            "store_size_mb": round(stats["store"]["size_in_bytes"] / (1024 * 1024), 2),
        }
    except Exception as exc:
        logger.error("index_stats_failed", error=str(exc))
        return {"index_name": INDEX_NAME, "error": str(exc)}


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _hits_to_dataframe(hits: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert Elasticsearch hits into a UI-ready DataFrame."""
    if not hits:
        return pd.DataFrame(columns=_UI_COLUMNS)
    data = [h["_source"] for h in hits]
    df = pd.DataFrame(data).rename(columns=_RENAME_MAP)
    return df[[c for c in _UI_COLUMNS if c in df.columns]]


def _parse_amount(value: str) -> tuple[float, str]:
    """Parse '1,234.56 USD' into (1234.56, 'USD')."""
    try:
        parts = str(value).replace(",", "").split()
        amount = float(parts[0])
        currency = parts[1] if len(parts) > 1 else "USD"
        return amount, currency
    except (ValueError, IndexError):
        return 0.0, "USD"