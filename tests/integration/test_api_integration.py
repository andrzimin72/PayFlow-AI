"""
API Integration Tests
=====================

Tests the FastAPI endpoints with real module interactions (not just mocks).
Uses TestClient but lets the underlying modules interact for real.

Version: 1.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


@pytest.fixture
def integration_api_client(integration_es_client, mock_classifier):
    """
    FastAPI TestClient with real module interactions.

    Patches the classifier at import time to avoid loading real ML models,
    but lets all other modules interact for real.
    """
    with patch("api.pipeline", return_value=MagicMock(side_effect=lambda text, cats: {
        "labels": ["Personal Expense"], "scores": [0.75]
    })):
        import importlib
        import api as api_module
        importlib.reload(api_module)

        # Patch the classifier in the reloaded module
        api_module.classifier = mock_classifier

        with TestClient(api_module.app) as client:
            yield client


# =============================================================================
# ANALYZE → RETRIEVE FLOW
# =============================================================================

class TestAnalyzeAndRetrieveFlow:
    """Test the analyze → retrieve data flow through the API."""

    @patch("api.paypal_client.fetch_transactions")
    @patch("api.paypal_client.get_access_token")
    def test_analyze_then_retrieve(
        self, mock_token, mock_fetch, integration_api_client
    ):
        """
        Verify that:
        1. POST /analyze ingests transactions
        2. GET /transactions returns the ingested data
        """
        mock_token.return_value = "valid_token"
        mock_fetch.return_value = [
            {
                "transaction_info": {
                    "transaction_id": "TX-API-001",
                    "transaction_subject": "Adobe Creative Cloud",
                    "transaction_amount": {"value": "52.99", "currency_code": "USD"},
                    "transaction_status": "S",
                }
            },
            {
                "transaction_info": {
                    "transaction_id": "TX-API-002",
                    "transaction_subject": "Starbucks Coffee",
                    "transaction_amount": {"value": "7.50", "currency_code": "USD"},
                    "transaction_status": "S",
                }
            },
        ]

        # Step 1: Analyze
        response = integration_api_client.post("/analyze")
        assert response.status_code == 200
        data = response.json()
        assert data["transactions_processed"] == 2

        # Step 2: Retrieve
        response = integration_api_client.get("/transactions")
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 2
        assert len(data["transactions"]) == 2

    @patch("api.paypal_client.fetch_transactions")
    @patch("api.paypal_client.get_access_token")
    def test_analyze_then_search(
        self, mock_token, mock_fetch, integration_api_client
    ):
        """Verify that analyzed transactions are searchable."""
        mock_token.return_value = "valid_token"
        mock_fetch.return_value = [
            {
                "transaction_info": {
                    "transaction_id": "TX-SEARCH-API-001",
                    "transaction_subject": "Adobe Creative Cloud",
                    "transaction_amount": {"value": "52.99", "currency_code": "USD"},
                    "transaction_status": "S",
                }
            },
        ]

        # Analyze
        integration_api_client.post("/analyze")

        # Search
        response = integration_api_client.get("/search?q=Adobe")
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] >= 1


# =============================================================================
# ANALYZE → RISK FLOW
# =============================================================================

class TestAnalyzeAndRiskFlow:
    """Test the analyze → risk scoring flow."""

    @patch("api.paypal_client.fetch_transactions")
    @patch("api.paypal_client.get_access_token")
    def test_analyze_then_portfolio_risk(
        self, mock_token, mock_fetch, integration_api_client
    ):
        """Verify that analyzed data feeds into risk metrics."""
        mock_token.return_value = "valid_token"
        mock_fetch.return_value = [
            {
                "transaction_info": {
                    "transaction_id": "TX-RISK-001",
                    "transaction_subject": "Normal subscription",
                    "transaction_amount": {"value": "50.00", "currency_code": "USD"},
                    "transaction_status": "S",
                }
            },
            {
                "transaction_info": {
                    "transaction_id": "TX-RISK-002",
                    "transaction_subject": "URGENT offshore wire",
                    "transaction_amount": {"value": "25000.00", "currency_code": "USD"},
                    "transaction_status": "S",
                }
            },
        ]

        # Analyze
        response = integration_api_client.post("/analyze")
        assert response.status_code == 200

        # Get portfolio risk
        response = integration_api_client.get("/risk/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_transactions"] >= 1


# =============================================================================
# INVOICE LIFECYCLE
# =============================================================================

class TestInvoiceLifecycle:
    """Test the full invoice lifecycle through the API."""

    @patch("api.invoice_manager.send_invoice")
    @patch("api.invoice_manager.create_invoice")
    @patch("api.invoice_manager.list_invoices")
    @patch("api.paypal_client.get_access_token")
    def test_create_then_list_invoice(
        self, mock_token, mock_list, mock_create, mock_send, integration_api_client
    ):
        """Verify create → list flow."""
        mock_token.return_value = "valid_token"
        mock_create.return_value = {
            "id": "INV2-LIFECYCLE",
            "invoice_number": "INV-2026-9999",
            "status": "DRAFT",
        }
        mock_send.return_value = True
        mock_list.return_value = {
            "invoices": [
                {
                    "id": "INV2-LIFECYCLE",
                    "status": "SENT",
                    "detail": {
                        "invoice_number": "INV-2026-9999",
                        "total_amount": {"currency_code": "USD", "value": "1500.00"},
                    },
                }
            ],
            "total_pages": 1,
            "total_items": 1,
        }

        # Create
        payload = {
            "merchant_email": "merchant@example.com",
            "client_email": "client@example.com",
            "client_name": "Jane Doe",
            "items": [{"name": "Consulting", "quantity": 10, "unit_price": 150.0}],
        }
        response = integration_api_client.post("/invoices/create", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["invoice_id"] == "INV2-LIFECYCLE"

        # List
        response = integration_api_client.get("/invoices")
        assert response.status_code == 200
        data = response.json()
        assert len(data["invoices"]) == 1


# =============================================================================
# ERROR FLOW INTEGRATION
# =============================================================================

class TestErrorFlowIntegration:
    """Test that errors propagate correctly through the API."""

    @patch("api.paypal_client.get_access_token")
    def test_auth_failure_returns_500(self, mock_token, integration_api_client):
        """Verify PayPal auth failure returns 500."""
        mock_token.return_value = None

        response = integration_api_client.post("/analyze")
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_invalid_search_query_returns_422(self, integration_api_client):
        """Verify missing query parameter returns 422."""
        response = integration_api_client.get("/search")
        assert response.status_code == 422

    def test_invalid_risk_score_request_returns_422(self, integration_api_client):
        """Verify invalid risk score payload returns 422."""
        payload = {
            "description": "",  # Empty - should fail validation
            "amount": -100.0,   # Negative - should fail validation
            "ai_category": "Unknown",
            "ai_confidence": 2.0,  # > 1.0 - should fail validation
        }
        response = integration_api_client.post("/risk/score", json=payload)
        assert response.status_code == 422