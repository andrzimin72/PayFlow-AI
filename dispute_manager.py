"""
Dispute Manager
===============

Wraps the PayPal Disputes API and orchestrates AI-assisted responses.

Responsibilities:
    - List and retrieve customer disputes
    - Submit evidence on behalf of the merchant
    - Accept disputes (issue refunds)
    - Delegate AI response drafting to ``generative_ai``

All external calls are timed, logged, and recorded as Prometheus metrics.

Version: 3.0.0
"""

from __future__ import annotations

import time
from typing import Any

import requests

import generative_ai
import paypal_client
from observability import logging as obs_logging, metrics

logger = obs_logging.get_logger("dispute-manager")

BASE_URL = "https://api-m.sandbox.paypal.com"

# =============================================================================
# READ OPERATIONS
# =============================================================================

def list_disputes(token: str, page_size: int = 10) -> dict[str, Any] | None:
    """
    Retrieve a paginated list of customer disputes.

    Args:
        token: Valid PayPal access token.
        page_size: Number of disputes per page (1-50).

    Returns:
        PayPal response payload on success, or ``None`` on failure.
    """
    url = f"{BASE_URL}/v1/customer/disputes"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    params = {"page_size": page_size}

    start = time.perf_counter()
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        duration = time.perf_counter() - start
        metrics.record_paypal_api_call("/v1/customer/disputes", "success", duration)
        metrics.record_dispute("listed")

        logger.info(
            "disputes_listed",
            count=len(data.get("items", [])),
            duration_ms=round(duration * 1000, 2),
        )
        return data

    except requests.exceptions.RequestException as exc:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call("/v1/customer/disputes", "error", duration)
        logger.error("list_disputes_failed", error=str(exc), exc_info=True)
        return None


def get_dispute(token: str, dispute_id: str) -> dict[str, Any] | None:
    """
    Retrieve detailed information about a single dispute.

    Args:
        token: Valid PayPal access token.
        dispute_id: PayPal dispute identifier.

    Returns:
        PayPal dispute payload on success, or ``None`` on failure.
    """
    url = f"{BASE_URL}/v1/customer/disputes/{dispute_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    start = time.perf_counter()
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            f"/v1/customer/disputes/{dispute_id}", "success", duration
        )

        logger.info(
            "dispute_retrieved",
            dispute_id=dispute_id,
            status=data.get("status"),
            duration_ms=round(duration * 1000, 2),
        )
        return data

    except requests.exceptions.RequestException as exc:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            f"/v1/customer/disputes/{dispute_id}", "error", duration
        )
        logger.error(
            "get_dispute_failed",
            dispute_id=dispute_id,
            error=str(exc),
            exc_info=True,
        )
        return None


# =============================================================================
# WRITE OPERATIONS
# =============================================================================

def provide_evidence(
    token: str, dispute_id: str, evidence: dict[str, Any]
) -> bool:
    """
    Submit evidence in support of the merchant's position on a dispute.

    Args:
        token: Valid PayPal access token.
        dispute_id: PayPal dispute identifier.
        evidence: Evidence payload (tracking info, notes, documents, etc.).

    Returns:
        True on success, False on failure.
    """
    url = f"{BASE_URL}/v1/customer/disputes/{dispute_id}/provide-evidence"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    start = time.perf_counter()
    try:
        response = requests.post(url, headers=headers, json=evidence, timeout=10)
        response.raise_for_status()

        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            f"/v1/customer/disputes/{dispute_id}/provide-evidence", "success", duration
        )
        metrics.record_dispute("evidence_provided")

        logger.info(
            "evidence_provided",
            dispute_id=dispute_id,
            duration_ms=round(duration * 1000, 2),
        )
        return True

    except requests.exceptions.RequestException as exc:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            f"/v1/customer/disputes/{dispute_id}/provide-evidence", "error", duration
        )
        logger.error(
            "provide_evidence_failed",
            dispute_id=dispute_id,
            error=str(exc),
            exc_info=True,
        )
        return False


def accept_dispute(token: str, dispute_id: str) -> bool:
    """
    Accept a dispute, effectively issuing a refund to the customer.

    Args:
        token: Valid PayPal access token.
        dispute_id: PayPal dispute identifier.

    Returns:
        True on success, False on failure.
    """
    url = f"{BASE_URL}/v1/customer/disputes/{dispute_id}/accept-offer"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"note": "Dispute accepted - refund issued to customer"}

    start = time.perf_counter()
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            f"/v1/customer/disputes/{dispute_id}/accept-offer", "success", duration
        )
        metrics.record_dispute("accepted")

        logger.info(
            "dispute_accepted",
            dispute_id=dispute_id,
            duration_ms=round(duration * 1000, 2),
        )
        return True

    except requests.exceptions.RequestException as exc:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(
            f"/v1/customer/disputes/{dispute_id}/accept-offer", "error", duration
        )
        logger.error(
            "accept_dispute_failed",
            dispute_id=dispute_id,
            error=str(exc),
            exc_info=True,
        )
        return False


# =============================================================================
# AI-ASSISTED OPERATIONS
# =============================================================================

def generate_dispute_response(dispute_details: dict[str, Any]) -> str:
    """
    Generate a professional response to a customer dispute using Mistral-7B.

    This method delegates the actual LLM call to ``generative_ai`` to avoid
    duplicating prompt-engineering logic across modules.

    Args:
        dispute_details: PayPal dispute payload.

    Returns:
        AI-generated response text, or an error message if generation fails.
    """
    dispute_id = dispute_details.get("dispute_id", "unknown")
    logger.info("dispute_response_generation_requested", dispute_id=dispute_id)

    start = time.perf_counter()
    try:
        response = generative_ai.generate_dispute_response(dispute_details)
        duration = time.perf_counter() - start

        logger.info(
            "dispute_response_generated",
            dispute_id=dispute_id,
            duration_ms=round(duration * 1000, 2),
        )
        return response

    except Exception as exc:
        duration = time.perf_counter() - start
        logger.error(
            "dispute_response_generation_failed",
            dispute_id=dispute_id,
            error=str(exc),
            exc_info=True,
            duration_ms=round(duration * 1000, 2),
        )
        return f"⚠️ Unable to generate response: {exc}"