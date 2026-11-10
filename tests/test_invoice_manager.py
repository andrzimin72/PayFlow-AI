"""
Tests for the Invoice Manager
=============================

Version: 2.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

import invoice_manager


# =============================================================================
# create_invoice
# =============================================================================

class TestCreateInvoice:

    @patch("invoice_manager.requests.post")
    def test_create_invoice_success(self, mock_post, mock_paypal_token, sample_invoice_payload):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = sample_invoice_payload
        mock_post.return_value = mock_response

        result = invoice_manager.create_invoice(
            token=mock_paypal_token,
            merchant_email="merchant@example.com",
            client_email="client@example.com",
            client_name="Jane Doe",
            items=[{"name": "Service", "quantity": 1, "unit_price": 1500.0}],
        )

        assert result is not None
        assert result["id"] == "INV2-ABCD-1234-5678"
        mock_post.assert_called_once()

    @patch("invoice_manager.requests.post")
    def test_create_invoice_returns_none_on_http_error(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        mock_post.return_value = mock_response

        result = invoice_manager.create_invoice(
            token=mock_paypal_token,
            merchant_email="merchant@example.com",
            client_email="client@example.com",
            client_name="Jane Doe",
            items=[{"name": "Service", "quantity": 1, "unit_price": 100.0}],
        )

        assert result is None

    @patch("invoice_manager.requests.post")
    def test_create_invoice_handles_timeout(self, mock_post, mock_paypal_token):
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        result = invoice_manager.create_invoice(
            token=mock_paypal_token,
            merchant_email="merchant@example.com",
            client_email="client@example.com",
            client_name="Jane Doe",
            items=[{"name": "Service", "quantity": 1, "unit_price": 100.0}],
        )

        assert result is None

    @patch("invoice_manager.requests.post")
    def test_create_invoice_uses_payment_terms(self, mock_post, mock_paypal_token, sample_invoice_payload):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_invoice_payload
        mock_post.return_value = mock_response

        invoice_manager.create_invoice(
            token=mock_paypal_token,
            merchant_email="merchant@example.com",
            client_email="client@example.com",
            client_name="Jane Doe",
            items=[{"name": "Service", "quantity": 1, "unit_price": 100.0}],
            payment_terms="NET_15",
        )

        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["detail"]["payment_term"]["term_type"] == "NET_15"


# =============================================================================
# send_invoice
# =============================================================================

class TestSendInvoice:

    @patch("invoice_manager.requests.post")
    def test_send_invoice_success(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        assert invoice_manager.send_invoice(mock_paypal_token, "INV2-TEST") is True

    @patch("invoice_manager.requests.post")
    def test_send_invoice_failure(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400")
        mock_post.return_value = mock_response

        assert invoice_manager.send_invoice(mock_paypal_token, "INV2-TEST") is False


# =============================================================================
# get_invoice
# =============================================================================

class TestGetInvoice:

    @patch("invoice_manager.requests.get")
    def test_get_invoice_success(self, mock_get, mock_paypal_token, sample_invoice_payload):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_invoice_payload
        mock_get.return_value = mock_response

        result = invoice_manager.get_invoice(mock_paypal_token, "INV2-TEST")
        assert result is not None
        assert result["id"] == "INV2-ABCD-1234-5678"

    @patch("invoice_manager.requests.get")
    def test_get_invoice_returns_none_on_error(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock_get.return_value = mock_response

        result = invoice_manager.get_invoice(mock_paypal_token, "UNKNOWN")
        assert result is None


# =============================================================================
# list_invoices
# =============================================================================

class TestListInvoices:

    @patch("invoice_manager.requests.get")
    def test_list_invoices_success(self, mock_get, mock_paypal_token, sample_invoice_list):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_invoice_list
        mock_get.return_value = mock_response

        result = invoice_manager.list_invoices(mock_paypal_token)
        assert result is not None
        assert len(result["invoices"]) == 2

    @patch("invoice_manager.requests.get")
    def test_list_invoices_returns_none_on_error(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        mock_get.return_value = mock_response

        result = invoice_manager.list_invoices(mock_paypal_token)
        assert result is None


# =============================================================================
# cancel_invoice
# =============================================================================

class TestCancelInvoice:

    @patch("invoice_manager.requests.post")
    def test_cancel_invoice_success(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        assert invoice_manager.cancel_invoice(mock_paypal_token, "INV2-TEST") is True

    @patch("invoice_manager.requests.post")
    def test_cancel_invoice_failure(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400")
        mock_post.return_value = mock_response

        assert invoice_manager.cancel_invoice(mock_paypal_token, "INV2-TEST") is False