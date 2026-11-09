"""
Anomaly Detector
================

Uses scikit-learn's Isolation Forest to flag transactions that deviate
from the portfolio's normal patterns.

Features used for detection:
    - ``log_amount``: log-scaled transaction amount (handles skew)
    - ``hour``: hour of day the transaction occurred
    - ``desc_length``: character count of the description
    - ``confidence_value``: AI categorisation confidence

The detector emits a normalised anomaly score in ``[0, 1]`` where 1 is
the most anomalous transaction in the current dataset.

Version: 3.0.0
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

import elastic_manager
from observability import logging as obs_logging

logger = obs_logging.get_logger("anomaly-detector")

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_CONTAMINATION: float = 0.1
MIN_TRANSACTIONS_FOR_DETECTION: int = 5

FEATURE_COLUMNS: list[str] = [
    "log_amount",
    "hour",
    "desc_length",
    "confidence_value",
]

ISOLATION_FOREST_CONFIG: dict[str, Any] = {
    "n_estimators": 100,
    "contamination": DEFAULT_CONTAMINATION,
    "random_state": 42,
    "max_samples": "auto",
}

# =============================================================================
# DATA PREPARATION
# =============================================================================

def prepare_anomaly_data() -> pd.DataFrame:
    """
    Load the transaction ledger and engineer features for anomaly detection.

    Returns:
        DataFrame with the original columns plus the four feature columns.
        Empty DataFrame if no data is available.
    """
    try:
        df = elastic_manager.get_all_transactions()
    except Exception as exc:
        logger.error("anomaly_data_fetch_failed", error=str(exc), exc_info=True)
        return pd.DataFrame()

    if df.empty:
        logger.warning("anomaly_data_empty")
        return pd.DataFrame()

    try:
        df = _attach_amount_column(df)
        df = _attach_log_amount(df)
        df = _attach_hour_column(df)
        df = _attach_description_length(df)
        df = _attach_confidence_column(df)
        return df
    except Exception as exc:
        logger.error("anomaly_feature_engineering_failed", error=str(exc), exc_info=True)
        return pd.DataFrame()


def _attach_amount_column(df: pd.DataFrame) -> pd.DataFrame:
    def parse(value: Any) -> float:
        try:
            if isinstance(value, str):
                return float(value.split()[0].replace(",", ""))
            return float(value)
        except (ValueError, AttributeError, IndexError):
            return 0.0

    df["amount_value"] = df["amount"].apply(parse)
    return df


def _attach_log_amount(df: pd.DataFrame) -> pd.DataFrame:
    df["log_amount"] = np.log1p(df["amount_value"])
    return df


def _attach_hour_column(df: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" in df.columns:
        try:
            df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
            return df
        except Exception as exc:
            logger.warning("hour_extraction_failed", error=str(exc))
    df["hour"] = 12
    return df


def _attach_description_length(df: pd.DataFrame) -> pd.DataFrame:
    df["desc_length"] = df["description"].fillna("").astype(str).str.len()
    return df


def _attach_confidence_column(df: pd.DataFrame) -> pd.DataFrame:
    df["confidence_value"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0.5)
    return df


# =============================================================================
# DETECTION
# =============================================================================

def detect_anomalies(contamination: float = DEFAULT_CONTAMINATION) -> pd.DataFrame:
    """
    Run Isolation Forest over the prepared feature matrix.

    Args:
        contamination: Expected proportion of anomalies in the dataset.

    Returns:
        DataFrame augmented with:
            - ``is_anomaly``: boolean flag
            - ``anomaly_score``: normalised score in ``[0, 1]`` (1 = most anomalous)
            - ``avg_amount`` / ``std_amount`` / ``amount_z_score``: statistical context
        Empty DataFrame if insufficient data.
    """
    df = prepare_anomaly_data()

    if df.empty or len(df) < MIN_TRANSACTIONS_FOR_DETECTION:
        logger.warning(
            "insufficient_data_for_anomaly_detection",
            count=len(df),
            required=MIN_TRANSACTIONS_FOR_DETECTION,
        )
        return pd.DataFrame()

    start = time.perf_counter()
    try:
        features = df[FEATURE_COLUMNS].fillna(0).to_numpy()

        model = IsolationForest(**ISOLATION_FOREST_CONFIG, contamination=contamination)
        predictions = model.fit_predict(features)
        raw_scores = model.score_samples(features)

        df["is_anomaly"] = predictions == -1
        df["anomaly_score"] = _normalise_scores(raw_scores)

        df = _attach_statistical_context(df)
        df = df.sort_values("is_anomaly", ascending=False)

        duration = time.perf_counter() - start
        anomaly_count = int(df["is_anomaly"].sum())

        logger.info(
            "anomaly_detection_completed",
            total_transactions=len(df),
            anomalies_detected=anomaly_count,
            anomaly_rate=f"{anomaly_count / len(df):.1%}" if len(df) else "0.0%",
            duration_ms=round(duration * 1000, 2),
        )
        return df

    except Exception as exc:
        duration = time.perf_counter() - start
        logger.error(
            "anomaly_detection_failed",
            error=str(exc),
            exc_info=True,
            duration_ms=round(duration * 1000, 2),
        )
        return pd.DataFrame()


def _normalise_scores(raw_scores: np.ndarray) -> np.ndarray:
    """Map raw Isolation Forest scores to ``[0, 1]`` where 1 = most anomalous."""
    min_score = raw_scores.min()
    max_score = raw_scores.max()
    if max_score <= min_score:
        return np.zeros_like(raw_scores)
    normalised = (raw_scores - min_score) / (max_score - min_score)
    return 1.0 - normalised


def _attach_statistical_context(df: pd.DataFrame) -> pd.DataFrame:
    """Compute portfolio-level amount statistics for downstream risk scoring."""
    df["avg_amount"] = float(df["amount_value"].mean())
    df["std_amount"] = float(df["amount_value"].std()) if len(df) > 1 else 0.0
    if df["std_amount"].iloc[0] > 0:
        df["amount_z_score"] = np.abs(
            (df["amount_value"] - df["avg_amount"]) / df["std_amount"].iloc[0]
        )
    else:
        df["amount_z_score"] = 0.0
    return df


# =============================================================================
# PUBLIC SUMMARIES
# =============================================================================

def get_anomaly_summary() -> dict[str, Any]:
    """
    Return a human-readable summary of detected anomalies.

    Returns:
        Dictionary with keys:
            - ``status``: ``"success"`` or ``"insufficient_data"``
            - ``total_transactions``
            - ``total_anomalies``
            - ``anomaly_rate``: formatted percentage
            - ``average_amount``
            - ``anomalies``: list of anomaly detail dicts
    """
    df = detect_anomalies()

    if df.empty:
        return {
            "status": "insufficient_data",
            "message": "Not enough transaction data to detect anomalies.",
            "total_anomalies": 0,
            "total_transactions": 0,
            "anomaly_rate": "0.0%",
            "average_amount": 0.0,
            "anomalies": [],
        }

    anomalies = df[df["is_anomaly"]]
    columns = [
        "description", "amount", "amount_value", "ai_category",
        "confidence_value", "anomaly_score", "amount_z_score",
    ]
    available = [c for c in columns if c in anomalies.columns]

    return {
        "status": "success",
        "total_transactions": len(df),
        "total_anomalies": len(anomalies),
        "anomaly_rate": f"{len(anomalies) / len(df) * 100:.1f}%",
        "average_amount": round(float(df["amount_value"].mean()), 2),
        "anomalies": anomalies[available].to_dict(orient="records"),
    }


def get_anomaly_data_with_scores() -> pd.DataFrame:
    """
    Return the full anomaly-scored DataFrame for consumption by the risk engine.

    This is the primary bridge between anomaly detection and risk scoring.
    """
    return detect_anomalies()