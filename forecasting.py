"""
Cash Flow Forecaster
====================

Uses Meta's Prophet to project net cash flow 30 days forward, based on
the historical transaction ledger stored in Elasticsearch.

Daily net cash flow is computed as:
    income (AI Category == "Freelance Income")  →  +amount
    everything else                             →  -amount

Prophet then fits a trend + weekly seasonality and emits point predictions
with uncertainty intervals.

Version: 3.0.0
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import pandas as pd
from prophet import Prophet

import elastic_manager
from observability import logging as obs_logging, metrics

logger = obs_logging.get_logger("forecasting")

# =============================================================================
# CONFIGURATION
# =============================================================================

INCOME_CATEGORIES: frozenset[str] = frozenset({"Freelance Income"})
DEFAULT_FORECAST_DAYS: int = 30
MIN_HISTORICAL_DAYS: int = 3

# Prophet hyperparameters — tuned for short-horizon financial data
PROPHET_CONFIG: dict[str, Any] = {
    "yearly_seasonality": False,
    "weekly_seasonality": True,
    "daily_seasonality": False,
    "changepoint_prior_scale": 0.05,
}

# =============================================================================
# DATA PREPARATION
# =============================================================================

def prepare_forecasting_data() -> pd.DataFrame:
    """
    Aggregate the transaction ledger into daily net cash flow.

    Returns:
        DataFrame with columns ``ds`` (date) and ``y`` (net cash flow).
        Empty DataFrame if no usable data is available.
    """
    start = time.perf_counter()
    try:
        df = elastic_manager.get_all_transactions()
        duration = time.perf_counter() - start
        metrics.record_elasticsearch_query(duration, operation="forecast_read")
    except Exception as exc:
        duration = time.perf_counter() - start
        metrics.record_elasticsearch_query(duration, operation="forecast_read", status="error")
        logger.error("forecast_data_fetch_failed", error=str(exc), exc_info=True)
        return pd.DataFrame(columns=["ds", "y"])

    if df.empty:
        logger.warning("forecast_data_empty")
        return pd.DataFrame(columns=["ds", "y"])

    try:
        df = _attach_date_column(df)
        df = _attach_amount_column(df)
        df = _attach_direction_column(df)
        daily = _aggregate_daily(df)

        logger.info("forecast_data_prepared", days=len(daily))
        return daily

    except Exception as exc:
        logger.error("forecast_data_preparation_failed", error=str(exc), exc_info=True)
        return pd.DataFrame(columns=["ds", "y"])


def _attach_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the ``timestamp`` column into a datetime, falling back to today."""
    if "timestamp" in df.columns:
        try:
            df["date"] = pd.to_datetime(df["timestamp"])
            return df
        except Exception as exc:
            logger.warning("timestamp_parse_failed", error=str(exc))

    logger.warning("no_timestamp_column_using_today")
    df["date"] = datetime.utcnow()
    return df


def _attach_amount_column(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the ``amount`` column into a float, handling formatted strings."""
    def parse(value: Any) -> float:
        try:
            if isinstance(value, str):
                return float(value.split()[0].replace(",", ""))
            return float(value)
        except (ValueError, AttributeError, IndexError):
            return 0.0

    df["amount_value"] = df["amount"].apply(parse)
    return df


def _attach_direction_column(df: pd.DataFrame) -> pd.DataFrame:
    """Mark each row as income (+) or expense (-)."""
    df["is_income"] = df["ai_category"].isin(INCOME_CATEGORIES)
    df["daily_net"] = df.apply(
        lambda row: row["amount_value"] if row["is_income"] else -row["amount_value"],
        axis=1,
    )
    return df


def _aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Sum daily net cash flow and format for Prophet."""
    daily = df.groupby(df["date"].dt.date)["daily_net"].sum().reset_index()
    daily.columns = ["ds", "y"]
    daily["ds"] = pd.to_datetime(daily["ds"])
    return daily


# =============================================================================
# FORECASTING
# =============================================================================

def forecast_cash_flow(days_ahead: int = DEFAULT_FORECAST_DAYS) -> pd.DataFrame:
    """
    Fit a Prophet model and project ``days_ahead`` days into the future.

    Args:
        days_ahead: Number of future days to forecast.

    Returns:
        DataFrame with columns ``ds``, ``yhat``, ``yhat_lower``, ``yhat_upper``.
        Empty DataFrame if insufficient historical data.
    """
    df = prepare_forecasting_data()

    if df.empty or len(df) < MIN_HISTORICAL_DAYS:
        logger.warning(
            "insufficient_data_for_forecast",
            available_days=len(df),
            required_days=MIN_HISTORICAL_DAYS,
        )
        return pd.DataFrame()

    start = time.perf_counter()
    try:
        model = Prophet(**PROPHET_CONFIG)
        model.fit(df)

        future = model.make_future_dataframe(periods=days_ahead)
        forecast = model.predict(future)

        duration = time.perf_counter() - start
        logger.info(
            "forecast_generated",
            historical_days=len(df),
            forecast_days=days_ahead,
            total_rows=len(forecast),
            duration_ms=round(duration * 1000, 2),
        )
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    except Exception as exc:
        duration = time.perf_counter() - start
        logger.error(
            "forecast_failed",
            error=str(exc),
            exc_info=True,
            duration_ms=round(duration * 1000, 2),
        )
        return pd.DataFrame()


# =============================================================================
# SUMMARY
# =============================================================================

def get_forecast_summary() -> dict[str, Any]:
    """
    Compute a human-readable summary of the 30-day forecast.

    Returns:
        Dictionary with keys:
            - ``status``: ``"success"`` or ``"insufficient_data"``
            - ``total_predicted_net``: sum of future daily predictions
            - ``best_day``: ``{"date": ..., "predicted_net": ...}``
            - ``worst_day``: ``{"date": ..., "predicted_net": ...}``
            - ``forecast_data``: full forecast DataFrame
    """
    forecast = forecast_cash_flow(DEFAULT_FORECAST_DAYS)

    if forecast.empty:
        return {
            "status": "insufficient_data",
            "message": (
                f"Not enough historical data to generate a forecast. "
                f"Need at least {MIN_HISTORICAL_DAYS} days of transactions."
            ),
        }

    try:
        future = forecast.tail(DEFAULT_FORECAST_DAYS)

        total_predicted = float(future["yhat"].sum())
        best_idx = future["yhat"].idxmax()
        worst_idx = future["yhat"].idxmin()

        summary = {
            "status": "success",
            "total_predicted_net": round(total_predicted, 2),
            "best_day": {
                "date": future.loc[best_idx, "ds"].strftime("%Y-%m-%d"),
                "predicted_net": round(float(future.loc[best_idx, "yhat"]), 2),
            },
            "worst_day": {
                "date": future.loc[worst_idx, "ds"].strftime("%Y-%m-%d"),
                "predicted_net": round(float(future.loc[worst_idx, "yhat"]), 2),
            },
            "forecast_data": forecast,
        }

        logger.info(
            "forecast_summary_generated",
            total_predicted=summary["total_predicted_net"],
            best_day=summary["best_day"]["date"],
            worst_day=summary["worst_day"]["date"],
        )
        return summary

    except Exception as exc:
        logger.error("forecast_summary_failed", error=str(exc), exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to generate forecast summary: {exc}",
        }