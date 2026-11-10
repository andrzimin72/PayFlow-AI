"""
Tests for the PayPal API Client
===============================

Version: 2.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

import paypal_client


# =============================================================================
# get_access_token
# =============================================================================

class TestGetAccessToken:
    """Tests for token retrieval."""

    @patch.object(paypal_client, "_token_manager")
    def test_returns_token_on_success(self, mock_manager):
        mock_manager.get_token.return_value = "valid_token"
        assert paypal_client.get_access_token() == "valid_token"

    @patch.object(paypal_client, "_token_manager")
    def test_returns_none_on_failure(self, mock_manager):
        mock_manager.get_token.side_effect = Exception("Auth failed")
        assert paypal_client.get_access_token() is None

    @patch.object(paypal_client, "_token_manager")
    def test_delegates_to_token_manager(self, mock_manager):
        mock_manager.get_token.return_value = "token"
        paypal_client.get_access_token()
        mock_manager.get_token.assert_called_once()


# =============================================================================
# invalidate_token
# =============================================================================

class TestInvalidateToken:

    @patch.object(paypal_client, "_token_manager")
    def test_calls_invalidate_on_manager(self, mock_manager):
        paypal_client.invalidate_token()
        mock_manager.invalidate_token.assert_called_once()


# =============================================================================
# get_token_stats
# =============================================================================

class TestGetTokenStats:

    @patch.object(paypal_client, "_token_manager")
    def test_returns_stats_dict(self, mock_manager):
        mock_manager.get_stats.return_value = {
            "total_requests": 10,
            "cache_hits": 8,
            "cache_hit_rate": "80.0%",
        }
        stats = paypal_client.get_token_stats()
        assert stats["total_requests"] == 10
        assert stats["cache_hit_rate"] == "80.0%"


# =============================================================================
# fetch_transactions
# =============================================================================

class TestFetchTransactions:
    """Tests for the transaction search endpoint."""

    @patch("paypal_client.requests.get")
    def test_returns_transactions_on_success(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transaction_details": [
                {"transaction_info": {"transaction_id": "TX1"}},
                {"transaction_info": {"transaction_id": "TX2"}},
            ]
        }
        mock_get.return_value = mock_response

        result = paypal_client.fetch_transactions(mock_paypal_token)
        assert len(result) == 2
        assert result[0]["transaction_info"]["transaction_id"] == "TX1"

    @patch("paypal_client.requests.get")
    def test_returns_empty_list_on_http_error(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        mock_get.return_value = mock_response

        result = paypal_client.fetch_transactions(mock_paypal_token)
        assert result == []

    @patch("paypal_client.requests.get")
    def test_returns_empty_list_on_timeout(self, mock_get, mock_paypal_token):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        result = paypal_client.fetch_transactions(mock_paypal_token)
        assert result == []

    @patch("paypal_client.requests.get")
    def test_returns_empty_list_on_connection_error(self, mock_get, mock_paypal_token):
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS failure")

        result = paypal_client.fetch_transactions(mock_paypal_token)
        assert result == []

    @patch("paypal_client.requests.get")
    def test_returns_empty_list_on_parse_error(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        result = paypal_client.fetch_transactions(mock_paypal_token)
        assert result == []

    @patch("paypal_client.requests.get")
    def test_handles_empty_transaction_details(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transaction_details": []}
        mock_get.return_value = mock_response

        result = paypal_client.fetch_transactions(mock_paypal_token)
        assert result == []

    @patch("paypal_client.requests.get")
    def test_respects_days_back_parameter(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transaction_details": []}
        mock_get.return_value = mock_response

        paypal_client.fetch_transactions(mock_paypal_token, days_back=7)

        call_kwargs = mock_get.call_args.kwargs
        assert "start_date" in call_kwargs["params"]
        assert "end_date" in call_kwargs["params"]