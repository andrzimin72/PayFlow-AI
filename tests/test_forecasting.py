"""
Tests for the Cash Flow Forecaster
==================================

Version: 2.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import forecasting


# =============================================================================
# prepare_forecasting_data
# =============================================================================

class TestPrepareForecastingData:

    @patch("forecasting.elastic_manager.get_all_transactions")
    def test_returns_empty_dataframe_when_no_data(self, mock_get):
        mock_get.return_value = pd.DataFrame()
        result = forecasting.prepare_forecasting_data()
        assert result.empty
        assert list(result.columns) == ["ds", "y"]

    @patch("forecasting.elastic_manager.get_all_transactions")
    def test_aggregates_daily_net_cash_flow(self, mock_get):
        mock_get.return_value = pd.DataFrame({
            "amount": ["100.00 USD", "50.00 USD", "200.00 USD"],
            "ai_category": [
                "Freelance Income",
                "Software Subscription",
                "Freelance Income",
            ],
            "timestamp": [
                "2026-11-01T10:00:00Z",
                "2026-11-01T14:00:00Z",
                "2026-11-02T09:00:00Z",
            ],
        })

        result = forecasting.prepare_forecasting_data()
        assert not result.empty
        assert "ds" in result.columns
        assert "y" in result.columns
        # Nov 1: +100 - 50 = +50; Nov 2: +200
        assert 50.0 in result["y"].values
        assert 200.0 in result["y"].values

    @patch("forecasting.elastic_manager.get_all_transactions")
    def test_handles_elasticsearch_failure(self, mock_get):
        mock_get.side_effect = Exception("ES down")
        result = forecasting.prepare_forecasting_data()
        assert result.empty


# =============================================================================
# forecast_cash_flow
# =============================================================================

class TestForecastCashFlow:

    @patch("forecasting.prepare_forecasting_data")
    def test_returns_empty_when_insufficient_data(self, mock_prepare):
        mock_prepare.return_value = pd.DataFrame({"ds": [], "y": []})
        result = forecasting.forecast_cash_flow()
        assert result.empty

    @patch("forecasting.prepare_forecasting_data")
    def test_returns_forecast_with_expected_columns(self, mock_prepare):
        # Build 10 days of data
        dates = pd.date_range("2026-10-01", periods=10, freq="D")
        mock_prepare.return_value = pd.DataFrame({
            "ds": dates,
            "y": [100.0 + i * 10 for i in range(10)],
        })

        result = forecasting.forecast_cash_flow(days_ahead=7)
        expected_columns = {"ds", "yhat", "yhat_lower", "yhat_upper"}
        assert expected_columns.issubset(set(result.columns))
        # Should have 10 historical + 7 future = 17 rows
        assert len(result) == 17


# =============================================================================
# get_forecast_summary
# =============================================================================

class TestGetForecastSummary:

    @patch("forecasting.forecast_cash_flow")
    def test_returns_insufficient_data_status_when_empty(self, mock_forecast):
        mock_forecast.return_value = pd.DataFrame()
        result = forecasting.get_forecast_summary()
        assert result["status"] == "insufficient_data"
        assert "message" in result

    @patch("forecasting.forecast_cash_flow")
    def test_returns_success_with_expected_keys(self, mock_forecast):
        dates = pd.date_range("2026-11-01", periods=40, freq="D")
        mock_forecast.return_value = pd.DataFrame({
            "ds": dates,
            "yhat": [100.0] * 40,
            "yhat_lower": [80.0] * 40,
            "yhat_upper": [120.0] * 40,
        })

        result = forecasting.get_forecast_summary()
        assert result["status"] == "success"
        assert "total_predicted_net" in result
        assert "best_day" in result
        assert "worst_day" in result
        assert "forecast_data" in result

    @patch("forecasting.forecast_cash_flow")
    def test_best_and_worst_day_have_date_and_amount(self, mock_forecast):
        dates = pd.date_range("2026-11-01", periods=40, freq="D")
        mock_forecast.return_value = pd.DataFrame({
            "ds": dates,
            "yhat": [100.0 + i for i in range(40)],
            "yhat_lower": [80.0] * 40,
            "yhat_upper": [120.0] * 40,
        })

        result = forecasting.get_forecast_summary()
        assert "date" in result["best_day"]
        assert "predicted_net" in result["best_day"]
        assert "date" in result["worst_day"]
        assert "predicted_net" in result["worst_day"]