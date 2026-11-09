"""
Risk Management Engine
======================

Combines three signals into a weighted, explainable risk score (0-100):

    score = 0.50 * anomaly_factor
          + 0.30 * ai_uncertainty
          + 0.20 * financial_impact

The score maps to four risk levels, each with a recommended automated action:

    LOW      (0-39)   -> AUTO_APPROVE
    MEDIUM   (40-59)  -> MONITOR
    HIGH     (60-79)  -> MANUAL_REVIEW
    CRITICAL (80-100) -> HOLD_AND_INVESTIGATE

Version: 3.0.0
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import anomaly_detector
from observability import logging as obs_logging, metrics

logger = obs_logging.get_logger("risk-engine")

# =============================================================================
# RISK LEVEL DEFINITIONS
# =============================================================================

RISK_LEVELS: dict[str, dict[str, Any]] = {
    "LOW": {
        "min_score": 0,
        "max_score": 39,
        "color": "#28a745",
        "action": "AUTO_APPROVE",
        "description": "Transaction appears normal. No action required.",
    },
    "MEDIUM": {
        "min_score": 40,
        "max_score": 59,
        "color": "#ffc107",
        "action": "MONITOR",
        "description": "Slightly unusual. Monitor for patterns.",
    },
    "HIGH": {
        "min_score": 60,
        "max_score": 79,
        "color": "#fd7e14",
        "action": "MANUAL_REVIEW",
        "description": "Unusual activity. Requires human review before processing.",
    },
    "CRITICAL": {
        "min_score": 80,
        "max_score": 100,
        "color": "#dc3545",
        "action": "HOLD_AND_INVESTIGATE",
        "description": "High-risk transaction. Place on hold and investigate immediately.",
    },
}

# =============================================================================
# SCORING
# =============================================================================

def calculate_risk_score(
    anomaly_score: float,
    ai_confidence: float,
    amount: float,
    avg_amount: float,
) -> float:
    """
    Compute a weighted risk score in the range 0-100.

    Args:
        anomaly_score: Normalised anomaly signal (0-1, higher = more anomalous).
        ai_confidence: AI categorisation confidence (0-1).
        amount: Transaction amount.
        avg_amount: Mean transaction amount for the portfolio.

    Returns:
        Risk score rounded to one decimal place.
    """
    anomaly_factor = max(0.0, min(1.0, float(anomaly_score)))
    ai_uncertainty = 1.0 - max(0.0, min(1.0, float(ai_confidence)))

    if avg_amount > 0:
        amount_factor = min(1.0, float(amount) / (float(avg_amount) * 5.0))
    else:
        amount_factor = 0.5

    raw = (anomaly_factor * 0.50) + (ai_uncertainty * 0.30) + (amount_factor * 0.20)
    return round(raw * 100.0, 1)


def get_risk_level(score: float) -> dict[str, Any]:
    """Map a numeric score to its risk level metadata."""
    for level, meta in RISK_LEVELS.items():
        if meta["min_score"] <= score <= meta["max_score"]:
            return {
                "level": level,
                "score": score,
                "color": meta["color"],
                "action": meta["action"],
                "description": meta["description"],
            }
    return {
        "level": "UNKNOWN",
        "score": score,
        "color": "#6c757d",
        "action": "MANUAL_REVIEW",
        "description": "Unable to determine risk level.",
    }


# =============================================================================
# TRANSACTION-LEVEL SCORING
# =============================================================================

def score_transaction(transaction: dict[str, Any], avg_amount: float) -> dict[str, Any]:
    """Score a single transaction and return a risk assessment dict."""
    anomaly_score = float(transaction.get("anomaly_score", 0.0))
    ai_confidence = float(transaction.get("confidence_value", 0.5))
    amount = float(transaction.get("amount_value", 0.0))

    risk_score = calculate_risk_score(anomaly_score, ai_confidence, amount, avg_amount)
    level = get_risk_level(risk_score)

    return {
        "description": transaction.get("description", ""),
        "amount": transaction.get("amount", ""),
        "amount_value": amount,
        "ai_category": transaction.get("ai_category", "Unknown"),
        "ai_confidence": ai_confidence,
        "anomaly_score": round(anomaly_score, 4),
        "risk_score": risk_score,
        "risk_level": level["level"],
        "risk_color": level["color"],
        "recommended_action": level["action"],
        "action_description": level["description"],
    }


def score_all_transactions() -> list[dict[str, Any]]:
    """Score every transaction in the index. Returns a list sorted by risk desc."""
    anomaly_df = anomaly_detector.get_anomaly_data_with_scores()
    if anomaly_df.empty:
        logger.warning("score_all_transactions_no_data")
        return []

    avg_amount = float(anomaly_df["amount_value"].mean())
    scored = [score_transaction(row.to_dict(), avg_amount) for _, row in anomaly_df.iterrows()]
    scored.sort(key=lambda t: t["risk_score"], reverse=True)

    high_risk = sum(1 for t in scored if t["risk_score"] >= 60)
    logger.info(
        "transactions_scored",
        count=len(scored),
        high_risk=high_risk,
    )
    return scored


# =============================================================================
# PORTFOLIO-LEVEL METRICS
# =============================================================================

def get_portfolio_risk_metrics() -> dict[str, Any]:
    """
    Aggregate risk metrics across the entire portfolio.

    Uses the 75th percentile of individual risk scores as the portfolio score.
    """
    scored = score_all_transactions()

    if not scored:
        return {
            "status": "no_data",
            "message": "No transactions available for risk assessment.",
            "portfolio_risk_score": 0.0,
            "risk_level": "LOW",
            "risk_color": "#28a745",
            "risk_description": "No data available.",
            "recommended_action": "AUTO_APPROVE",
            "total_transactions": 0,
            "risk_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            "high_risk_count": 0,
            "high_risk_percentage": 0.0,
            "average_risk_score": 0.0,
            "max_risk_score": 0.0,
            "min_risk_score": 0.0,
            "scored_transactions": [],
        }

    scores = np.array([t["risk_score"] for t in scored])
    portfolio_score = float(np.percentile(scores, 75))
    portfolio_level = get_risk_level(portfolio_score)

    distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for tx in scored:
        level = tx["risk_level"]
        if level in distribution:
            distribution[level] += 1

    total = len(scored)
    high_risk_count = distribution["HIGH"] + distribution["CRITICAL"]
    high_risk_pct = (high_risk_count / total * 100.0) if total else 0.0

    metrics.set_portfolio_risk_score(portfolio_score)

    result = {
        "status": "success",
        "portfolio_risk_score": portfolio_score,
        "risk_level": portfolio_level["level"],
        "risk_color": portfolio_level["color"],
        "risk_description": portfolio_level["description"],
        "recommended_action": portfolio_level["action"],
        "total_transactions": total,
        "risk_distribution": distribution,
        "high_risk_count": high_risk_count,
        "high_risk_percentage": round(high_risk_pct, 1),
        "average_risk_score": round(float(scores.mean()), 1),
        "max_risk_score": round(float(scores.max()), 1),
        "min_risk_score": round(float(scores.min()), 1),
        "scored_transactions": scored,
    }

    logger.info(
        "portfolio_risk_assessed",
        score=portfolio_score,
        level=portfolio_level["level"],
        high_risk=high_risk_count,
    )
    return result