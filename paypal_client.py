"""
PayPal API Client
=================

Thin HTTP client for the PayPal REST API.

This module is deliberately narrow in scope: it handles authentication
(delegating token lifecycle to ``security.token_manager``) and exposes
the transaction-fetching endpoint used throughout the platform.

Business-specific PayPal operations (invoicing, disputes, etc.) live in
their own managers — ``invoice_manager``, ``dispute_manager`` — so that
this module stays a pure transport layer.

Version: 3.0.0
"""

from __future__ import annotations

import time
from typing import Any

import requests

from observability import logging as obs_logging, metrics
from security.token_manager import PayPalTokenManager

logger = obs_logging.get_logger("paypal-client")

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = "https://api-m.sandbox.paypal.com"

# Singleton token manager — shared across all calls in this process.
_token_manager = PayPalTokenManager()

# =============================================================================
# AUTHENTICATION
# =============================================================================

def get_access_token() -> str | None:
    """
    Return a valid PayPal access token, refreshing if necessary.

    The underlying ``PayPalTokenManager`` handles caching, expiry, and
    retry logic. This function is a thin convenience wrapper.

    Returns:
        A bearer token string on success, or ``None`` on failure.
    """
    try:
        token = _token_manager.get_token()
        logger.debug("access_token_retrieved")
        return token
    except Exception as exc:
        logger.error("access_token_retrieval_failed", error=str(exc), exc_info=True)
        return None


def invalidate_token() -> None:
    """Force the cached token to be discarded. Useful after auth errors."""
    _token_manager.invalidate_token()
    logger.info("access_token_invalidated")


def get_token_stats() -> dict[str, Any]:
    """Expose token-manager statistics for diagnostics."""
    return _token_manager.get_stats()


# =============================================================================
# TRANSACTION SEARCH
# =============================================================================

def fetch_transactions(
    token: str,
    days_back: int = 30,
    fields: str = "all",
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """
    Fetch transactions from the PayPal Reporting API.

    Args:
        token: Valid PayPal access token.
        days_back: Number of days of history to retrieve.
        fields: Level of detail (``"all"`` or ``"basic"``).
        page_size: Maximum transactions per response (PayPal caps at 1000).

    Returns:
        A list of transaction dictionaries, or an empty list on failure.
    """
    from datetime import datetime, timedelta

    url = f"{BASE_URL}/v1/reporting/transactions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)

    params = {
        "start_date": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_date": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fields": fields,
        "page_size": page_size,
    }

    start = time.perf_counter()
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        transactions = data.get("transaction_details", [])

        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            "/v1/reporting/transactions", "success", duration
        )

        logger.info(
            "transactions_fetched",
            count=len(transactions),
            days_back=days_back,
            duration_ms=round(duration * 1000, 2),
        )
        return transactions

    except requests.exceptions.Timeout:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            "/v1/reporting/transactions", "timeout", duration
        )
        logger.error("fetch_transactions_timeout", days_back=days_back)
        return []

    except requests.exceptions.RequestException as exc:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            "/v1/reporting/transactions", "error", duration
        )
        logger.error(
            "fetch_transactions_failed",
            error=str(exc),
            exc_info=True,
        )
        return []

    except ValueError as exc:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            "/v1/reporting/transactions", "parse_error", duration
        )
        logger.error(
            "fetch_transactions_parse_failed",
            error=str(exc),
            exc_info=True,
        )
        return []