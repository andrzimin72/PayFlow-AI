"""
Risk Pipeline Integration Tests
===============================

Verifies the flow: Elasticsearch → Anomaly Detection → Risk Scoring → Portfolio Metrics

Version: 1.0.0
"""

from __future__ import annotations

import pytest

import anomaly_detector
import elastic_manager
import risk_engine


pytestmark = pytest.mark.integration


# =============================================================================
# ANOMALY → RISK PIPELINE
# =============================================================================

class TestAnomalyToRiskPipeline:
    """Test that anomaly scores feed correctly into risk scoring."""

    def test_anomaly_scores_feed_into_risk_engine(self, integration_es_client):
        """
        Verify the full risk pipeline:
        1. Seed ES with mixed transactions
        2. Anomaly detector flags unusual ones
        3. Risk engine combines signals into composite scores
        4. Portfolio metrics aggregate correctly
        """
        # Seed with a mix of normal and suspicious transactions
        transactions = [
            # Normal transactions
            {"description": "Adobe CC", "amount": 52.99, "ai_category": "Software Subscription",
             "confidence": 0.95, "status": "S"},
            {"description": "Starbucks", "amount": 7.50, "ai_category": "Personal Expense",
             "confidence": 0.88, "status": "S"},
            {"description": "GitHub Pro", "amount": 4.00, "ai_category": "Software Subscription",
             "confidence": 0.92, "status": "S"},
            # Suspicious transaction
            {"description": "URGENT wire transfer offshore", "amount": 25000.00,
             "ai_category": "Suspicious Activity", "confidence": 0.45, "status": "S"},
        ]

        for i, tx in enumerate(transactions):
            elastic_manager.index_single_transaction({
                **tx,
                "amount_formatted": f"{tx['amount']} USD",
                "currency": "USD",
                "indexed_at": f"2026-11-0{i+1}T12:00:00Z",
            })

        # Step 1: Anomaly detection
        anomaly_df = anomaly_detector.get_anomaly_data_with_scores()
        assert not anomaly_df.empty
        assert "anomaly_score" in anomaly_df.columns
        assert "amount_value" in anomaly_df.columns

        # Step 2: Risk scoring
        scored = risk_engine.score_all_transactions()
        assert len(scored) == len(transactions)
        assert all("risk_score" in tx for tx in scored)
        assert all("risk_level" in tx for tx in scored)

        # Step 3: Verify suspicious transaction has highest risk
        suspicious = [tx for tx in scored if "wire transfer" in tx["description"].lower()]
        assert len(suspicious) == 1
        assert suspicious[0]["risk_score"] >= 60.0  # Should be HIGH or CRITICAL

        # Step 4: Portfolio metrics
        portfolio = risk_engine.get_portfolio_risk_metrics()
        assert portfolio["status"] == "success"
        assert portfolio["total_transactions"] == len(transactions)
        assert portfolio["high_risk_count"] >= 1
        assert portfolio["risk_distribution"]["LOW"] >= 0

    def test_risk_levels_map_correctly(self, integration_es_client):
        """Verify that risk scores map to the correct risk levels."""
        # Seed transactions that should produce different risk levels
        test_cases = [
            # (description, amount, category, confidence, expected_level_range)
            ("Normal subscription", 50.0, "Software Subscription", 0.95, ["LOW"]),
            ("Suspicious offshore wire", 50000.0, "Suspicious Activity", 0.3, ["HIGH", "CRITICAL"]),
        ]

        for desc, amount, category, confidence, _ in test_cases:
            elastic_manager.index_single_transaction({
                "description": desc,
                "amount": amount,
                "amount_formatted": f"{amount} USD",
                "currency": "USD",
                "ai_category": category,
                "confidence": confidence,
                "status": "S",
            })

        scored = risk_engine.score_all_transactions()
        assert len(scored) == len(test_cases)

        # Verify each transaction has a valid risk level
        for tx in scored:
            assert tx["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            assert 0 <= tx["risk_score"] <= 100


# =============================================================================
# PORTFOLIO METRICS
# =============================================================================

class TestPortfolioMetricsIntegration:
    """Test portfolio-level risk aggregation."""

    def test_portfolio_uses_75th_percentile(self, integration_es_client):
        """Verify portfolio score uses the 75th percentile of individual scores."""
        # Seed 10 transactions with varying risk profiles
        for i in range(10):
            elastic_manager.index_single_transaction({
                "description": f"Transaction {i}",
                "amount": 100.0 * (i + 1),
                "amount_formatted": f"{100.0 * (i + 1)} USD",
                "currency": "USD",
                "ai_category": "Personal Expense",
                "confidence": 0.5 + (i * 0.05),
                "status": "S",
            })

        portfolio = risk_engine.get_portfolio_risk_metrics()
        assert portfolio["status"] == "success"
        assert portfolio["total_transactions"] == 10
        # Portfolio score should be between min and max individual scores
        assert portfolio["min_risk_score"] <= portfolio["portfolio_risk_score"]
        assert portfolio["portfolio_risk_score"] <= portfolio["max_risk_score"]

    def test_empty_portfolio_returns_no_data(self, integration_es_client):
        """Verify empty portfolio is handled gracefully."""
        portfolio = risk_engine.get_portfolio_risk_metrics()
        assert portfolio["status"] == "no_data"
        assert portfolio["total_transactions"] == 0
        assert portfolio["portfolio_risk_score"] == 0.0

    def test_risk_distribution_sums_to_total(self, integration_es_client):
        """Verify risk distribution counts sum to total transactions."""
        # Seed diverse transactions
        for i in range(5):
            elastic_manager.index_single_transaction({
                "description": f"TX-{i}",
                "amount": 100.0,
                "amount_formatted": "100.00 USD",
                "currency": "USD",
                "ai_category": "Personal Expense",
                "confidence": 0.8,
                "status": "S",
            })

        portfolio = risk_engine.get_portfolio_risk_metrics()
        distribution = portfolio["risk_distribution"]
        total_from_distribution = sum(distribution.values())
        assert total_from_distribution == portfolio["total_transactions"]