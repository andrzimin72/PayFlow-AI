"""
Tests for the Dispute Manager
=============================

Version: 2.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

import dispute_manager


# =============================================================================
# list_disputes
# =============================================================================

class TestListDisputes:

    @patch("dispute_manager.requests.get")
    def test_list_disputes_success(self, mock_get, mock_paypal_token, sample_dispute_list):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_dispute_list
        mock_get.return_value = mock_response

        result = dispute_manager.list_disputes(mock_paypal_token)
        assert result is not None
        assert len(result["items"]) == 1

    @patch("dispute_manager.requests.get")
    def test_list_disputes_returns_none_on_error(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        mock_get.return_value = mock_response

        result = dispute_manager.list_disputes(mock_paypal_token)
        assert result is None

    @patch("dispute_manager.requests.get")
    def test_list_disputes_handles_timeout(self, mock_get, mock_paypal_token):
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")
        result = dispute_manager.list_disputes(mock_paypal_token)
        assert result is None


# =============================================================================
# get_dispute
# =============================================================================

class TestGetDispute:

    @patch("dispute_manager.requests.get")
    def test_get_dispute_success(self, mock_get, mock_paypal_token, sample_dispute_payload):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_dispute_payload
        mock_get.return_value = mock_response

        result = dispute_manager.get_dispute(mock_paypal_token, "PP-D-12345")
        assert result is not None
        assert result["dispute_id"] == "PP-D-12345"
        assert result["reason"] == "Item not received"

    @patch("dispute_manager.requests.get")
    def test_get_dispute_returns_none_on_error(self, mock_get, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock_get.return_value = mock_response

        result = dispute_manager.get_dispute(mock_paypal_token, "UNKNOWN")
        assert result is None


# =============================================================================
# provide_evidence
# =============================================================================

class TestProvideEvidence:

    @patch("dispute_manager.requests.post")
    def test_provide_evidence_success(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        evidence = {"notes": "Tracking number: ABC123"}
        assert dispute_manager.provide_evidence(
            mock_paypal_token, "PP-D-12345", evidence
        ) is True

    @patch("dispute_manager.requests.post")
    def test_provide_evidence_failure(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400")
        mock_post.return_value = mock_response

        assert dispute_manager.provide_evidence(
            mock_paypal_token, "PP-D-12345", {}
        ) is False


# =============================================================================
# accept_dispute
# =============================================================================

class TestAcceptDispute:

    @patch("dispute_manager.requests.post")
    def test_accept_dispute_success(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        assert dispute_manager.accept_dispute(mock_paypal_token, "PP-D-12345") is True

    @patch("dispute_manager.requests.post")
    def test_accept_dispute_failure(self, mock_post, mock_paypal_token):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400")
        mock_post.return_value = mock_response

        assert dispute_manager.accept_dispute(mock_paypal_token, "PP-D-12345") is False


# =============================================================================
# generate_dispute_response
# =============================================================================

class TestGenerateDisputeResponse:

    @patch("dispute_manager.generative_ai.generate_dispute_response")
    def test_delegates_to_generative_ai(self, mock_gen, sample_dispute_payload):
        mock_gen.return_value = "Dear customer, we are investigating..."

        result = dispute_manager.generate_dispute_response(sample_dispute_payload)
        assert result == "Dear customer, we are investigating..."
        mock_gen.assert_called_once_with(sample_dispute_payload)

    @patch("dispute_manager.generative_ai.generate_dispute_response")
    def test_handles_generative_ai_failure(self, mock_gen, sample_dispute_payload):
        mock_gen.side_effect = Exception("HF API down")

        result = dispute_manager.generate_dispute_response(sample_dispute_payload)
        assert "Unable to generate response" in result

    @patch("dispute_manager.generative_ai.generate_dispute_response")
    def test_handles_missing_dispute_id(self, mock_gen):
        mock_gen.return_value = "Response"
        result = dispute_manager.generate_dispute_response({})
        assert result == "Response"