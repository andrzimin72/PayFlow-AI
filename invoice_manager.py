"""
Invoice Manager
===============

Wraps the PayPal Invoicing v2 API: create, send, list, retrieve, and
cancel invoices. All calls are logged and timed.

Version: 3.0.0
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import requests

import paypal_client
from observability import logging as obs_logging, metrics

logger = obs_logging.get_logger("invoice-manager")

BASE_URL = "https://api-m.sandbox.paypal.com"

# =============================================================================
# CREATE
# =============================================================================

def create_invoice(
    token: str,
    merchant_email: str,
    client_email: str,
    client_name: str,
    items: list[dict[str, Any]],
    note: str = "",
    payment_terms: str = "NET_30",
) -> dict[str, Any] | None:
    """
    Create a PayPal invoice.

    Args:
        token: Valid PayPal access token.
        merchant_email: Sender's business email.
        client_email: Recipient email.
        client_name: Recipient name.
        items: List of dicts with keys ``name``, ``quantity``, ``unit_price``
            and optional ``description``.
        note: Optional free-text note.
        payment_terms: One of ``NET_10``, ``NET_15``, ``NET_30``,
            ``DUE_ON_RECEIPT``.

    Returns:
        The PayPal invoice payload on success, or ``None`` on failure.
    """
    url = f"{BASE_URL}/v2/invoicing/invoices"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    invoice_number = f"INV-{int(datetime.utcnow().timestamp())}"
    name_parts = (client_name or "Client").split(maxsplit=1)
    given_name = name_parts[0]
    surname = name_parts[1] if len(name_parts) > 1 else ""

    payload = {
        "detail": {
            "invoice_number": invoice_number,
            "reference": "PayFlow AI Generated Invoice",
            "invoice_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "currency_code": "USD",
            "note": note or "Thank you for your business!",
            "payment_term": {"term_type": payment_terms},
            "metadata": {"created_via": "PayFlow AI", "sender_category": "ECOMMERCE"},
        },
        "invoicer": {
            "name": {"given_name": "PayFlow", "surname": "AI"},
            "email_address": merchant_email,
        },
        "primary_recipients": [
            {
                "billing_info": {
                    "name": {"given_name": given_name, "surname": surname},
                    "email_address": client_email,
                }
            }
        ],
        "items": [
            {
                "name": item["name"],
                "quantity": str(item["quantity"]),
                "unit_amount": {
                    "currency_code": "USD",
                    "value": f"{float(item['unit_price']):.2f}",
                },
                "description": item.get("description", f"Item {idx}"),
            }
            for idx, item in enumerate(items, start=1)
        ],
        "configuration": {
            "partial_payment": {"allow_partial_payment": False},
            "tax_calculated_after_discount": False,
            "tax_inclusive": False,
        },
    }

    start = time.perf_counter()
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        duration = time.perf_counter() - start
        metrics.record_paypal_api_call("/v2/invoicing/invoices", "success", duration)
        metrics.record_invoice("created")

        logger.info(
            "invoice_created",
            invoice_id=data.get("id"),
            invoice_number=invoice_number,
            duration_ms=round(duration * 1000, 2),
        )
        return data

    except requests.exceptions.RequestException as exc:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call("/v2/invoicing/invoices", "error", duration)
        logger.error("invoice_creation_failed", error=str(exc), exc_info=True)
        return None


# =============================================================================
# SEND
# =============================================================================

def send_invoice(token: str, invoice_id: str) -> bool:
    """Send a previously-created invoice to the client by email."""
    url = f"{BASE_URL}/v2/invoicing/invoices/{invoice_id}/send"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    start = time.perf_counter()
    try:
        requests.post(url, headers=headers, timeout=10).raise_for_status()
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(f"/v2/invoicing/invoices/{invoice_id}/send", "success", duration)
        metrics.record_invoice("sent")
        logger.info("invoice_sent", invoice_id=invoice_id, duration_ms=round(duration * 1000, 2))
        return True
    except requests.exceptions.RequestException as exc:
        duration = time.perf_counter() - start
        metrics.record_paypal_api_call(f"/v2/invoicing/invoices/{invoice_id}/send", "error", duration)
        logger.error("invoice_send_failed", invoice_id=invoice_id, error=str(exc))
        return False


# =============================================================================
# READ
# =============================================================================

def get_invoice(token: str, invoice_id: str) -> dict[str, Any] | None:
    """Retrieve a single invoice by ID."""
    url = f"{BASE_URL}/v2/invoicing/invoices/{invoice_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        logger.error("get_invoice_failed", invoice_id=invoice_id, error=str(exc))
        return None


def list_invoices(token: str, page: int = 1, page_size: int = 10) -> dict[str, Any] | None:
    """List invoices with pagination."""
    url = f"{BASE_URL}/v2/invoicing/invoices"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    params = {"page": page, "page_size": page_size, "fields": "all"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        logger.error("list_invoices_failed", error=str(exc))
        return None


# =============================================================================
# CANCEL
# =============================================================================

def cancel_invoice(token: str, invoice_id: str, reason: str = "Cancelled by merchant") -> bool:
    """Cancel a draft invoice."""
    url = f"{BASE_URL}/v2/invoicing/invoices/{invoice_id}/cancel"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "subject": "Invoice Cancelled",
        "note": reason,
        "send_to_merchant": True,
        "send_to_payer": True,
    }
    try:
        requests.post(url, headers=headers, json=payload, timeout=10).raise_for_status()
        metrics.record_invoice("cancelled")
        logger.info("invoice_cancelled", invoice_id=invoice_id)
        return True
    except requests.exceptions.RequestException as exc:
        logger.error("invoice_cancel_failed", invoice_id=invoice_id, error=str(exc))
        return False