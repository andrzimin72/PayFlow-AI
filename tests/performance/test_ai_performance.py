"""
AI Pipeline Performance Tests
=============================

Benchmarks the AI categorization and risk scoring pipelines.

Thresholds are set conservatively for CI stability. Run locally with
real models to get true performance numbers.

Version: 1.0.0
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

import ai_engine
import risk_engine


pytestmark = [pytest.mark.performance, pytest.mark.slow]


# =============================================================================
# AI CATEGORIZATION LATENCY
# =============================================================================


class TestAICategorizationLatency:
    """Benchmark single-transaction categorization latency."""

    def test_single_transaction_latency_with_fast_classifier(
        self, benchmark, fast_mock_classifier, sample_paypal_transactions
    ):
        """
        Measure latency for categorizing a single transaction.

        Threshold: < 10ms (framework overhead only)
        """

        def categorize_one():
            return ai_engine.process_transactions(sample_paypal_transactions[:1], fast_mock_classifier)

        result = benchmark(categorize_one)
        assert len(result) == 1
        assert benchmark.stats.mean < 0.010  # 10ms threshold

    def test_single_transaction_latency_with_realistic_classifier(
        self, benchmark, realistic_mock_classifier, sample_paypal_transactions
    ):
        """
        Measure latency with realistic model speed (~50ms).

        Threshold: < 200ms (includes mock delay + overhead)
        """

        def categorize_one():
            return ai_engine.process_transactions(
                sample_paypal_transactions[:1], realistic_mock_classifier
            )

        result = benchmark(categorize_one)
        assert len(result) == 1
        assert benchmark.stats.mean < 0.200  # 200ms threshold


# =============================================================================
# AI CATEGORIZATION THROUGHPUT
# =============================================================================


class TestAICategorizationThroughput:
    """Benchmark batch categorization throughput."""

    def test_small_batch_throughput(
        self, benchmark, fast_mock_classifier, small_batch_transactions
    ):
        """
        Throughput for 10 transactions.

        Threshold: < 50ms total
        """

        def categorize_batch():
            return ai_engine.process_transactions(small_batch_transactions, fast_mock_classifier)

        result = benchmark(categorize_batch)
        assert len(result) == 10
        assert benchmark.stats.mean < 0.050

    def test_medium_batch_throughput(
        self, benchmark, fast_mock_classifier, medium_batch_transactions
    ):
        """
        Throughput for 100 transactions.

        Threshold: < 200ms total
        """

        def categorize_batch():
            return ai_engine.process_transactions(medium_batch_transactions, fast_mock_classifier)

        result = benchmark(categorize_batch)
        assert len(result) == 100
        assert benchmark.stats.mean < 0.200

    def test_large_batch_throughput(
        self, benchmark, fast_mock_classifier, large_batch_transactions
    ):
        """
        Throughput for 1000 transactions.

        Threshold: < 2s total
        """

        def categorize_batch():
            return ai_engine.process_transactions(large_batch_transactions, fast_mock_classifier)

        result = benchmark(categorize_batch)
        assert len(result) == 1000
        assert benchmark.stats.mean < 2.0

    def test_huge_batch_throughput(
        self, benchmark, fast_mock_classifier, huge_batch_transactions
    ):
        """
        Throughput for 5000 transactions (stress test).

        Threshold: < 10s total
        """

        def categorize_batch():
            return ai_engine.process_transactions(huge_batch_transactions, fast_mock_classifier)

        result = benchmark(categorize_batch)
        assert len(result) == 5000
        assert benchmark.stats.mean < 10.0


# =============================================================================
# RISK SCORING PERFORMANCE
# =============================================================================


class TestRiskScoringPerformance:
    """Benchmark risk scoring throughput."""

    def test_risk_scoring_small_batch(self, benchmark, small_categorized_df):
        """
        Risk scoring for 10 transactions.

        Threshold: < 100ms
        """
        # Prepare anomaly data format
        anomaly_df = _prepare_anomaly_data(small_categorized_df)

        def score_batch():
            from unittest.mock import patch

            with patch("risk_engine.anomaly_detector.get_anomaly_data_with_scores", return_value=anomaly_df):
                return risk_engine.score_all_transactions()

        result = benchmark(score_batch)
        assert len(result) == 10
        assert benchmark.stats.mean < 0.100

    def test_risk_scoring_medium_batch(self, benchmark, medium_categorized_df):
        """
        Risk scoring for 100 transactions.

        Threshold: < 500ms
        """
        anomaly_df = _prepare_anomaly_data(medium_categorized_df)

        def score_batch():
            from unittest.mock import patch

            with patch("risk_engine.anomaly_detector.get_anomaly_data_with_scores", return_value=anomaly_df):
                return risk_engine.score_all_transactions()

        result = benchmark(score_batch)
        assert len(result) == 100
        assert benchmark.stats.mean < 0.500

    def test_risk_scoring_large_batch(self, benchmark, large_categorized_df):
        """
        Risk scoring for 1000 transactions.

        Threshold: < 3s
        """
        anomaly_df = _prepare_anomaly_data(large_categorized_df)

        def score_batch():
            from unittest.mock import patch

            with patch("risk_engine.anomaly_detector.get_anomaly_data_with_scores", return_value=anomaly_df):
                return risk_engine.score_all_transactions()

        result = benchmark(score_batch)
        assert len(result) == 1000
        assert benchmark.stats.mean < 3.0


# =============================================================================
# PORTFOLIO METRICS PERFORMANCE
# =============================================================================


class TestPortfolioMetricsPerformance:
    """Benchmark portfolio-level risk computation."""

    def test_portfolio_metrics_medium_dataset(self, benchmark, medium_categorized_df):
        """
        Portfolio metrics for 100 transactions.

        Threshold: < 1s
        """
        anomaly_df = _prepare_anomaly_data(medium_categorized_df)

        def compute_metrics():
            from unittest.mock import patch

            with patch("risk_engine.anomaly_detector.get_anomaly_data_with_scores", return_value=anomaly_df):
                return risk_engine.get_portfolio_risk_metrics()

        result = benchmark(compute_metrics)
        assert result["status"] == "success"
        assert result["total_transactions"] == 100
        assert benchmark.stats.mean < 1.0

    def test_portfolio_metrics_large_dataset(self, benchmark, large_categorized_df):
        """
        Portfolio metrics for 1000 transactions.

        Threshold: < 5s
        """
        anomaly_df = _prepare_anomaly_data(large_categorized_df)

        def compute_metrics():
            from unittest.mock import patch

            with patch("risk_engine.anomaly_detector.get_anomaly_data_with_scores", return_value=anomaly_df):
                return risk_engine.get_portfolio_risk_metrics()

        result = benchmark(compute_metrics)
        assert result["status"] == "success"
        assert result["total_transactions"] == 1000
        assert benchmark.stats.mean < 5.0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _prepare_anomaly_data(df: pd.DataFrame) -> pd.DataFrame:
    """Convert categorized DataFrame to anomaly detector format."""
    anomaly_df = df.copy()

    # Parse amount
    anomaly_df["amount_value"] = anomaly_df["Amount"].apply(
        lambda x: float(str(x).split()[0]) if isinstance(x, str) else float(x)
    )

    # Add mock anomaly features
    anomaly_df["anomaly_score"] = 0.3
    anomaly_df["confidence_value"] = anomaly_df["Confidence"]
    anomaly_df["ai_category"] = anomaly_df["AI Category"]
    anomaly_df["description"] = anomaly_df["Description"]
    anomaly_df["amount"] = anomaly_df["Amount"]

    return anomaly_df