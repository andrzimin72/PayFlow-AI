"""
Tests for the FastAPI REST API
==============================

Version: 2.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# =============================================================================
# Health & Monitoring
# =============================================================================

class TestHealthEndpoints:

    def test_root_returns_healthy(self, api_client):
        response = api_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_endpoint_returns_full_info(self, api_client):
        response = api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ai_model"] == "facebook/bart-large-mnli"
        assert data["risk_engine"] == "enabled"
        assert data["observability"]["metrics"] == "enabled"

    def test_metrics_endpoint_returns_prometheus_format(self, api_client):
        response = api_client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")


# =============================================================================
# Data Endpoints
# =============================================================================

class TestDataEndpoints:

    @patch("api.elastic_manager.get_all_transactions")
    def test_get_all_transactions_empty(self, mock_get_all, api_client):
        mock_get_all.return_value = pd.DataFrame()
        response = api_client.get("/transactions")
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 0
        assert data["transactions"] == []

    @patch("api.elastic_manager.get_all_transactions")
    def test_get_all_transactions_with_data(self, mock_get_all, api_client):
        mock_df = pd.DataFrame({
            "Amount": ["50.00 USD"],
            "Description": ["Test transaction"],
            "Status": ["S"],
            "AI Category": ["Personal Expense"],
            "Confidence": [0.85],
        })
        mock_get_all.return_value = mock_df

        response = api_client.get("/transactions")
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1
        assert data["transactions"][0]["ai_category"] == "Personal Expense"

    @patch("api.elastic_manager.search_transactions")
    def test_search_transactions(self, mock_search, api_client):
        mock_df = pd.DataFrame({
            "Amount": ["52.99 USD"],
            "Description": ["Adobe Creative Cloud"],
            "Status": ["S"],
            "AI Category": ["Software Subscription"],
            "Confidence": [0.88],
        })
        mock_search.return_value = mock_df

        response = api_client.get("/search?q=Adobe")
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 1

    def test_search_without_query_returns_422(self, api_client):
        response = api_client.get("/search")
        assert response.status_code == 422

    def test_get_categories(self, api_client):
        response = api_client.get("/categories")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 4
        assert "Freelance Income" in data["categories"]


# =============================================================================
# AI Endpoints
# =============================================================================

class TestAIEndpoints:

    @patch("api.elastic_manager.get_all_transactions")
    @patch("api.elastic_manager.index_transactions")
    @patch("api.ai_engine.process_transactions")
    @patch("api.paypal_client.fetch_transactions")
    @patch("api.paypal_client.get_access_token")
    def test_analyze_success(
        self, mock_token, mock_fetch, mock_process, mock_index, mock_get_all, api_client
    ):
        mock_token.return_value = "valid_token"
        mock_fetch.return_value = [{"transaction_info": {"transaction_id": "TX1"}}]
        mock_process.return_value = pd.DataFrame({
            "AI Category": ["Freelance Income"],
        })
        mock_get_all.return_value = pd.DataFrame({"Amount": ["1.00 USD"]})

        response = api_client.post("/analyze")
        assert response.status_code == 200
        data = response.json()
        assert data["transactions_processed"] == 1

    @patch("api.paypal_client.get_access_token")
    def test_analyze_auth_failure(self, mock_token, api_client):
        mock_token.return_value = None
        response = api_client.post("/analyze")
        assert response.status_code == 500

    @patch("api.paypal_client.fetch_transactions")
    @patch("api.paypal_client.get_access_token")
    def test_analyze_no_transactions(self, mock_token, mock_fetch, api_client):
        mock_token.return_value = "valid_token"
        mock_fetch.return_value = []

        response = api_client.post("/analyze")
        assert response.status_code == 200
        data = response.json()
        assert data["transactions_processed"] == 0


# =============================================================================
# Risk Endpoints
# =============================================================================

class TestRiskEndpoints:

    @patch("api.elastic_manager.get_all_transactions")
    def test_score_single_transaction(self, mock_get_all, api_client):
        mock_get_all.return_value = pd.DataFrame({
            "Amount": ["100.00 USD", "200.00 USD"],
        })

        payload = {
            "description": "Test transaction",
            "amount": 150.0,
            "ai_category": "Personal Expense",
            "ai_confidence": 0.85,
        }
        response = api_client.post("/risk/score", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert 0.0 <= data["risk_score"] <= 100.0
        assert data["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    @patch("api.risk_engine.get_portfolio_risk_metrics")
    def test_get_portfolio_risk(self, mock_metrics, api_client):
        mock_metrics.return_value = {
            "status": "success",
            "portfolio_risk_score": 45.0,
            "risk_level": "MEDIUM",
            "risk_color": "#ffc107",
            "risk_description": "Slightly unusual.",
            "recommended_action": "MONITOR",
            "total_transactions": 100,
            "risk_distribution": {"LOW": 60, "MEDIUM": 30, "HIGH": 8, "CRITICAL": 2},
            "high_risk_count": 10,
            "high_risk_percentage": 10.0,
            "average_risk_score": 35.0,
            "max_risk_score": 92.0,
            "min_risk_score": 5.0,
        }

        response = api_client.get("/risk/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "MEDIUM"
        assert data["total_transactions"] == 100

    @patch("api.risk_engine.score_all_transactions")
    def test_get_risk_transactions(self, mock_score, api_client):
        mock_score.return_value = [
            {
                "description": "TX1",
                "amount": "100.00 USD",
                "amount_value": 100.0,
                "ai_category": "Personal Expense",
                "ai_confidence": 0.8,
                "anomaly_score": 0.1,
                "risk_score": 25.0,
                "risk_level": "LOW",
                "risk_color": "#28a745",
                "recommended_action": "AUTO_APPROVE",
                "action_description": "Normal.",
            }
        ]
        response = api_client.get("/risk/transactions")
        assert response.status_code == 200
        data = response.json()
        assert data["total_transactions"] == 1


# =============================================================================
# Invoice Endpoints
# =============================================================================

class TestInvoiceEndpoints:

    @patch("api.invoice_manager.list_invoices")
    @patch("api.paypal_client.get_access_token")
    def test_list_invoices(self, mock_token, mock_list, api_client):
        mock_token.return_value = "valid_token"
        mock_list.return_value = {"invoices": [], "total_pages": 0, "total_items": 0}

        response = api_client.get("/invoices")
        assert response.status_code == 200

    @patch("api.invoice_manager.send_invoice")
    @patch("api.invoice_manager.create_invoice")
    @patch("api.paypal_client.get_access_token")
    def test_create_invoice_success(self, mock_token, mock_create, mock_send, api_client):
        mock_token.return_value = "valid_token"
        mock_create.return_value = {
            "id": "INV2-TEST",
            "invoice_number": "INV-0001",
            "status": "DRAFT",
        }
        mock_send.return_value = True

        payload = {
            "merchant_email": "merchant@example.com",
            "client_email": "client@example.com",
            "client_name": "Jane Doe",
            "items": [{"name": "Service", "quantity": 1, "unit_price": 100.0}],
        }
        response = api_client.post("/invoices/create", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["invoice_id"] == "INV2-TEST"


# =============================================================================
# Dispute Endpoints
# =============================================================================

class TestDisputeEndpoints:

    @patch("api.dispute_manager.list_disputes")
    @patch("api.paypal_client.get_access_token")
    def test_list_disputes(self, mock_token, mock_list, api_client):
        mock_token.return_value = "valid_token"
        mock_list.return_value = {"items": [], "total_items": 0}

        response = api_client.get("/disputes")
        assert response.status_code == 200

    @patch("api.dispute_manager.generate_dispute_response")
    @patch("api.dispute_manager.get_dispute")
    @patch("api.paypal_client.get_access_token")
    def test_generate_dispute_response(self, mock_token, mock_get, mock_gen, api_client):
        mock_token.return_value = "valid_token"
        mock_get.return_value = {"dispute_id": "PP-D-1", "status": "OPEN"}
        mock_gen.return_value = "Dear customer, we are investigating..."

        response = api_client.get("/disputes/PP-D-1/generate-response")
        assert response.status_code == 200
        data = response.json()
        assert "ai_response" in data

    @patch("api.dispute_manager.get_dispute")
    @patch("api.paypal_client.get_access_token")
    def test_generate_response_dispute_not_found(self, mock_token, mock_get, api_client):
        mock_token.return_value = "valid_token"
        mock_get.return_value = None

        response = api_client.get("/disputes/UNKNOWN/generate-response")
        assert response.status_code == 404