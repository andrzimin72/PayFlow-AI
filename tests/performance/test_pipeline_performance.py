"""
Pipeline Performance Tests
==========================

Benchmarks end-to-end pipeline flows including forecasting and anomaly detection.

Version: 1.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import anomaly_detector
import forecasting


pytestmark = [pytest.mark.performance, pytest.mark.slow]


# =============================================================================
# FORECASTING PERFORMANCE
# =============================================================================


class TestForecastingPerformance:
    """Benchmark cash flow forecasting."""

    def test_forecasting_with_30_days_data(self, benchmark):
        """
        Forecasting with 30 days of historical data.

        Threshold: < 3s (Prophet model training)
        """
        dates = pd.date_range("2026-10-01", periods=30, freq="D")
        mock_data = pd.DataFrame(
            {
                "ds": dates,
                "y": np.random.normal(500, 100, 30),
            }
        )

        def run_forecast():
            with patch("forecasting.prepare_forecasting_data", return_value=mock_data):
                return forecasting.forecast_cash_flow(days_ahead=30)

        result = benchmark(run_forecast)
        assert not result.empty
        assert len(result) == 60  # 30 historical + 30 forecast
        assert benchmark.stats.mean < 3.0

    def test_forecasting_with_90_days_data(self, benchmark):
        """
        Forecasting with 90 days of historical data.

        Threshold: < 5s
        """
        dates = pd.date_range("2026-08-01", periods=90, freq="D")
        mock_data = pd.DataFrame(
            {
                "ds": dates,
                "y": np.random.normal(500, 100, 90),
            }
        )

        def run_forecast():
            with patch("forecasting.prepare_forecasting_data", return_value=mock_data):
                return forecasting.forecast_cash_flow(days_ahead=30)

        result = benchmark(run_forecast)
        assert not result.empty
        assert len(result) == 120  # 90 historical + 30 forecast
        assert benchmark.stats.mean < 5.0

    def test_forecast_summary_generation(self, benchmark):
        """
        Full forecast summary generation.

        Threshold: < 5s
        """
        dates = pd.date_range("2026-10-01", periods=30, freq="D")
        mock_data = pd.DataFrame(
            {
                "ds": dates,
                "y": np.random.normal(500, 100, 30),
            }
        )

        def generate_summary():
            with patch("forecasting.prepare_forecasting_data", return_value=mock_data):
                return forecasting.get_forecast_summary()

        result = benchmark(generate_summary)
        assert result["status"] == "success"
        assert "total_predicted_net" in result
        assert benchmark.stats.mean < 5.0


# =============================================================================
# ANOMALY DETECTION PERFORMANCE
# =============================================================================


class TestAnomalyDetectionPerformance:
    """Benchmark anomaly detection with Isolation Forest."""

    def test_anomaly_detection_small_dataset(self, benchmark):
        """
        Anomaly detection on 100 transactions.

        Threshold: < 2s
        """
        mock_data = _generate_anomaly_data(100)

        def detect():
            with patch("anomaly_detector.elastic_manager.get_all_transactions", return_value=mock_data):
                return anomaly_detector.detect_anomalies()

        result = benchmark(detect)
        assert not result.empty
        assert "anomaly_score" in result.columns
        assert benchmark.stats.mean < 2.0

    def test_anomaly_detection_medium_dataset(self, benchmark):
        """
        Anomaly detection on 500 transactions.

        Threshold: < 5s
        """
        mock_data = _generate_anomaly_data(500)

        def detect():
            with patch("anomaly_detector.elastic_manager.get_all_transactions", return_value=mock_data):
                return anomaly_detector.detect_anomalies()

        result = benchmark(detect)
        assert not result.empty
        assert benchmark.stats.mean < 5.0

    def test_anomaly_detection_large_dataset(self, benchmark):
        """
        Anomaly detection on 2000 transactions.

        Threshold: < 15s
        """
        mock_data = _generate_anomaly_data(2000)

        def detect():
            with patch("anomaly_detector.elastic_manager.get_all_transactions", return_value=mock_data):
                return anomaly_detector.detect_anomalies()

        result = benchmark(detect)
        assert not result.empty
        assert benchmark.stats.mean < 15.0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _generate_anomaly_data(count: int) -> pd.DataFrame:
    """Generate realistic data for anomaly detection testing."""
    np.random.seed(42)

    descriptions = [
        "Adobe Creative Cloud",
        "Payment from client",
        "Starbucks Coffee",
        "GitHub Pro",
        "URGENT wire transfer",
    ]

    data = []
    for i in range(count):
        amount = np.random.exponential(100) + 10
        # Inject some anomalies (large amounts)
        if i % 20 == 0:
            amount = np.random.uniform(5000, 20000)

        data.append(
            {
                "description": descriptions[i % len(descriptions)],
                "amount": f"{amount:.2f} USD",
                "amount_value": amount,
                "ai_category": "Personal Expense",
                "confidence": np.random.uniform(0.6, 0.99),
                "timestamp": f"2026-11-{(i % 28) + 1:02d}T12:00:00Z",
            }
        )

    return pd.DataFrame(data)