"""
Performance Test Fixtures
=========================

Provides large-scale test data and benchmark-specific fixtures for
performance testing the PayFlow AI platform.

Version: 1.0.0
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest


# =============================================================================
# SCALE FIXTURES
# =============================================================================


@pytest.fixture
def small_batch_transactions() -> list[dict[str, Any]]:
    """10 transactions — for quick latency checks."""
    return _generate_transactions(10)


@pytest.fixture
def medium_batch_transactions() -> list[dict[str, Any]]:
    """100 transactions — typical batch size."""
    return _generate_transactions(100)


@pytest.fixture
def large_batch_transactions() -> list[dict[str, Any]]:
    """1000 transactions — stress test size."""
    return _generate_transactions(1000)


@pytest.fixture
def huge_batch_transactions() -> list[dict[str, Any]]:
    """5000 transactions — upper bound stress test."""
    return _generate_transactions(5000)


def _generate_transactions(count: int) -> list[dict[str, Any]]:
    """Generate realistic PayPal transaction payloads."""
    templates = [
        ("Payment from TechCorp for web development", "2500.00", "Freelance Income"),
        ("Adobe Creative Cloud", "52.99", "Software Subscription"),
        ("Starbucks Coffee", "7.50", "Personal Expense"),
        ("GitHub Pro subscription", "4.00", "Software Subscription"),
        ("Payment from StartupXYZ for consulting", "1500.00", "Freelance Income"),
        ("AWS monthly bill", "250.00", "Software Subscription"),
        ("Uber ride", "25.00", "Personal Expense"),
        ("Payment from client for design work", "800.00", "Freelance Income"),
    ]

    transactions = []
    for i in range(count):
        desc, amount, _ = templates[i % len(templates)]
        transactions.append(
            {
                "transaction_info": {
                    "transaction_id": f"TX-PERF-{i:06d}",
                    "transaction_subject": desc,
                    "transaction_amount": {"value": amount, "currency_code": "USD"},
                    "transaction_status": "S",
                }
            }
        )
    return transactions


# =============================================================================
# DATAFRAME FIXTURES
# =============================================================================


@pytest.fixture
def small_categorized_df() -> pd.DataFrame:
    """10-row categorized DataFrame."""
    return _generate_categorized_df(10)


@pytest.fixture
def medium_categorized_df() -> pd.DataFrame:
    """100-row categorized DataFrame."""
    return _generate_categorized_df(100)


@pytest.fixture
def large_categorized_df() -> pd.DataFrame:
    """1000-row categorized DataFrame."""
    return _generate_categorized_df(1000)


def _generate_categorized_df(count: int) -> pd.DataFrame:
    """Generate a realistic categorized DataFrame."""
    categories = ["Freelance Income", "Software Subscription", "Personal Expense", "Suspicious Activity"]
    descriptions = [
        "Payment from client for services",
        "Adobe Creative Cloud",
        "Starbucks Coffee",
        "GitHub Pro",
        "AWS bill",
        "Consulting fee",
        "Software license",
        "Restaurant dinner",
    ]

    data = []
    for i in range(count):
        data.append(
            {
                "Amount": f"{100.0 + (i % 50):.2f} USD",
                "Description": descriptions[i % len(descriptions)],
                "Status": "S",
                "AI Category": categories[i % len(categories)],
                "Confidence": 0.75 + (i % 25) * 0.01,
            }
        )
    return pd.DataFrame(data)


# =============================================================================
# MOCK CLASSIFIERS (at different speeds)
# =============================================================================


@pytest.fixture
def fast_mock_classifier() -> MagicMock:
    """
    Ultra-fast mock classifier for throughput testing.
    Returns in < 1ms — measures framework overhead.
    """

    def _classify(text: str, categories: list[str]) -> dict[str, Any]:
        return {"labels": ["Personal Expense"], "scores": [0.85]}

    return MagicMock(side_effect=_classify)


@pytest.fixture
def realistic_mock_classifier() -> MagicMock:
    """
    Realistic-speed mock classifier (~50ms per call).
    Simulates actual model inference latency.
    """
    import time

    def _classify(text: str, categories: list[str]) -> dict[str, Any]:
        time.sleep(0.05)  # Simulate 50ms inference
        text_lower = text.lower()
        if "payment" in text_lower:
            return {"labels": ["Freelance Income"], "scores": [0.92]}
        if "adobe" in text_lower or "subscription" in text_lower:
            return {"labels": ["Software Subscription"], "scores": [0.88]}
        return {"labels": ["Personal Expense"], "scores": [0.78]}

    return MagicMock(side_effect=_classify)


# =============================================================================
# BENCHMARK CONFIGURATION
# =============================================================================


@pytest.fixture
def benchmark_warmup():
    """
    Warm up the system before benchmarking.

    Ensures that first-call overhead (JIT compilation, model loading,
    connection pooling) doesn't skew results.
    """
    import gc

    gc.collect()
    yield
    gc.collect()