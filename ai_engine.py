"""
AI Categorisation Engine
========================

Zero-shot NLP classification for PayPal transaction descriptions.

Uses Hugging Face's BART-large-mnli to assign each transaction to one of
the predefined business categories with a confidence score.

Version: 3.0.0
"""

from __future__ import annotations

import time
from typing import Any, Callable

import pandas as pd

from observability import logging as obs_logging, metrics
from utils.formatters import format_currency, truncate_text

logger = obs_logging.get_logger("ai-engine")

# =============================================================================
# CONFIGURATION
# =============================================================================

CATEGORIES: list[str] = [
    "Freelance Income",
    "Software Subscription",
    "Personal Expense",
    "Suspicious Activity",
]

INCOME_CATEGORIES: frozenset[str] = frozenset({"Freelance Income"})

# =============================================================================
# CORE PROCESSING
# =============================================================================

def process_transactions(
    transactions: list[dict[str, Any]],
    classifier: Callable[[str, list[str]], dict[str, Any]],
) -> pd.DataFrame:
    """
    Categorise a list of PayPal transactions using a zero-shot classifier.

    Args:
        transactions: Raw PayPal transaction payloads (each must contain
            a ``transaction_info`` dictionary).
        classifier: A callable matching the Hugging Face zero-shot pipeline
            signature: ``classifier(text, candidate_labels) -> dict``.

    Returns:
        DataFrame with columns ``Amount``, ``Description``, ``Status``,
        ``AI Category``, ``Confidence``. Empty DataFrame on empty input.
    """
    if not transactions:
        logger.warning("process_transactions_called_with_empty_input")
        return pd.DataFrame()

    logger.info("process_transactions_started", count=len(transactions))
    start = time.perf_counter()

    rows: list[dict[str, Any]] = []

    for idx, tx in enumerate(transactions, start=1):
        try:
            row = _process_single(tx, classifier)
            rows.append(row)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "transaction_processing_failed",
                index=idx,
                error=str(exc),
                exc_info=True,
            )
            continue

    duration = time.perf_counter() - start
    metrics.record_ai_inference(duration)

    logger.info(
        "process_transactions_completed",
        processed=len(rows),
        failed=len(transactions) - len(rows),
        duration_ms=round(duration * 1000, 2),
    )

    return pd.DataFrame(rows)


def _process_single(
    tx: dict[str, Any],
    classifier: Callable[[str, list[str]], dict[str, Any]],
) -> dict[str, Any]:
    """Process a single transaction payload into a categorised row."""
    info = tx.get("transaction_info", {}) or {}

    amount_raw = info.get("transaction_amount", {}).get("value", 0.0)
    currency = info.get("transaction_amount", {}).get("currency_code", "USD")
    description = (
        info.get("transaction_subject")
        or info.get("transaction_note")
        or "Standard PayPal transfer"
    )
    status = info.get("transaction_status", "Unknown")

    result = classifier(description, CATEGORIES)
    category = result["labels"][0]
    confidence = float(result["scores"][0])

    metrics.record_ai_categorization(category, confidence=confidence)

    return {
        "Amount": format_currency(amount_raw, currency),
        "Description": truncate_text(description, max_length=40),
        "Status": status,
        "AI Category": category,
        "Confidence": confidence,
    }


# =============================================================================
# HELPERS
# =============================================================================

def get_categories() -> list[str]:
    """Return a copy of the configured category list."""
    return list(CATEGORIES)


def validate_category(category: str) -> bool:
    """Return True if ``category`` is one of the configured labels."""
    return category in CATEGORIES


def is_income_category(category: str) -> bool:
    """Return True if ``category`` represents income."""
    return category in INCOME_CATEGORIES