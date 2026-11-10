"""
Shared Test Fixtures
====================

Centralizes fixtures used across the test suite to avoid duplication
and ensure consistent test data.

Fixture Categories
------------------

1. PayPal Transaction Fixtures
   - sample_paypal_transactions: Realistic PayPal API payloads
   - empty_paypal_transactions: Empty transaction list
   - malformed_paypal_transaction: Edge case with missing fields

2. AI/ML Fixtures
   - mock_classifier: Mock zero-shot NLP classifier
   - sample_categorized_df: Pre-categorized DataFrame
   - empty_categorized_df: Empty DataFrame

3. Elasticsearch Fixtures
   - sample_es_hits: Realistic ES search hits
   - integration_es_client: In-memory ES mock for integration tests

4. Invoice Fixtures
   - sample_invoice_payload: PayPal invoice response
   - sample_invoice_list: PayPal invoice list

5. Dispute Fixtures
   - sample_dispute_payload: PayPal dispute payload
   - sample_dispute_list: PayPal dispute list

6. API Fixtures
   - api_client: FastAPI TestClient with mocked dependencies

7. Integration Fixtures
   - integration_es_client: In-memory Elasticsearch
   - mock_hf_client: Mock Hugging Face client
   - mock_zapier: Mock Zapier webhook
   - valid_webhook_payload: Realistic webhook payload
   - high_risk_webhook_payload: High-risk webhook

Usage
-----

Fixtures are automatically available to all test files. Simply include
them as function parameters:

    def test_something(sample_paypal_transactions, mock_classifier):
        # Use the fixtures
        result = process_transactions(sample_paypal_transactions, mock_classifier)
        assert len(result) == len(sample_paypal_transactions)

Version: 2.0.0
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# =============================================================================
# PAYPAL TRANSACTION FIXTURES
# =============================================================================


@pytest.fixture
def sample_paypal_transactions() -> list[dict[str, Any]]:
    """
    Realistic PayPal transaction payloads for testing.

    Includes a mix of categories:
    - Freelance income
    - Software subscriptions
    - Personal expenses
    - Suspicious activity

    Returns:
        List of 4 transaction dictionaries matching PayPal API format
    """
    return [
        {
            "transaction_info": {
                "transaction_id": "TX100001",
                "transaction_subject": "Payment from TechCorp for web development",
                "transaction_amount": {"value": "2500.00", "currency_code": "USD"},
                "transaction_status": "S",
            }
        },
        {
            "transaction_info": {
                "transaction_id": "TX100002",
                "transaction_subject": "Adobe Creative Cloud",
                "transaction_amount": {"value": "52.99", "currency_code": "USD"},
                "transaction_status": "S",
            }
        },
        {
            "transaction_info": {
                "transaction_id": "TX100003",
                "transaction_subject": "Starbucks Coffee",
                "transaction_amount": {"value": "7.50", "currency_code": "USD"},
                "transaction_status": "S",
            }
        },
        {
            "transaction_info": {
                "transaction_id": "TX100004",
                "transaction_subject": "URGENT: Wire transfer to offshore account",
                "transaction_amount": {"value": "25000.00", "currency_code": "USD"},
                "transaction_status": "S",
            }
        },
    ]


@pytest.fixture
def empty_paypal_transactions() -> list[dict[str, Any]]:
    """Empty transaction list for edge case testing."""
    return []


@pytest.fixture
def malformed_paypal_transaction() -> list[dict[str, Any]]:
    """Transaction with missing fields for edge-case testing."""
    return [
        {
            "transaction_info": {
                "transaction_id": "TX999999",
                # Missing subject, amount, status
            }
        }
    ]


@pytest.fixture
def large_paypal_transactions() -> list[dict[str, Any]]:
    """Large batch of transactions for performance testing."""
    return [
        {
            "transaction_info": {
                "transaction_id": f"TX{100000 + i}",
                "transaction_subject": f"Transaction {i}",
                "transaction_amount": {"value": f"{100.0 + i:.2f}", "currency_code": "USD"},
                "transaction_status": "S",
            }
        }
        for i in range(100)
    ]


# =============================================================================
# AI/ML FIXTURES
# =============================================================================


@pytest.fixture
def mock_classifier() -> MagicMock:
    """
    Mock zero-shot classifier that routes by keyword.

    Mirrors the real classifier's signature:
        classifier(text, candidate_labels) -> {"labels": [...], "scores": [...]}

    Returns:
        MagicMock with side_effect that classifies based on keywords
    """

    def _classify(text: str, categories: list[str]) -> dict[str, Any]:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["payment from", "consulting", "web development"]):
            return {"labels": ["Freelance Income"], "scores": [0.95]}
        if any(kw in text_lower for kw in ["adobe", "subscription", "github", "aws"]):
            return {"labels": ["Software Subscription"], "scores": [0.88]}
        if any(kw in text_lower for kw in ["suspicious", "wire transfer", "offshore", "urgent"]):
            return {"labels": ["Suspicious Activity"], "scores": [0.65]}
        return {"labels": ["Personal Expense"], "scores": [0.78]}

    return MagicMock(side_effect=_classify)


@pytest.fixture
def sample_categorized_df() -> pd.DataFrame:
    """
    DataFrame of categorised transactions as produced by ai_engine.

    Includes realistic data with varying confidence scores.

    Returns:
        DataFrame with columns: Amount, Description, Status, AI Category, Confidence
    """
    return pd.DataFrame(
        {
            "Amount": ["2,500.00 USD", "52.99 USD", "7.50 USD", "25,000.00 USD"],
            "Description": [
                "Payment from TechCorp for web development",
                "Adobe Creative Cloud",
                "Starbucks Coffee",
                "URGENT: Wire transfer to offshore account",
            ],
            "Status": ["S", "S", "S", "S"],
            "AI Category": [
                "Freelance Income",
                "Software Subscription",
                "Personal Expense",
                "Suspicious Activity",
            ],
            "Confidence": [0.95, 0.88, 0.78, 0.65],
        }
    )


@pytest.fixture
def empty_categorized_df() -> pd.DataFrame:
    """Empty categorised DataFrame."""
    return pd.DataFrame(
        columns=["Amount", "Description", "Status", "AI Category", "Confidence"]
    )


@pytest.fixture
def high_confidence_df() -> pd.DataFrame:
    """DataFrame with high confidence scores (all > 0.9)."""
    return pd.DataFrame(
        {
            "Amount": ["100.00 USD", "200.00 USD"],
            "Description": ["Normal TX 1", "Normal TX 2"],
            "Status": ["S", "S"],
            "AI Category": ["Personal Expense", "Personal Expense"],
            "Confidence": [0.95, 0.92],
        }
    )


@pytest.fixture
def low_confidence_df() -> pd.DataFrame:
    """DataFrame with low confidence scores (all < 0.6)."""
    return pd.DataFrame(
        {
            "Amount": ["1000.00 USD", "2000.00 USD"],
            "Description": ["Suspicious TX 1", "Suspicious TX 2"],
            "Status": ["S", "S"],
            "AI Category": ["Suspicious Activity", "Suspicious Activity"],
            "Confidence": [0.45, 0.52],
        }
    )


# =============================================================================
# TOKEN FIXTURES
# =============================================================================


@pytest.fixture
def mock_paypal_token() -> str:
    """A fake PayPal bearer token."""
    return "mock_access_token_abc123"


@pytest.fixture
def expired_paypal_token() -> str:
    """An expired PayPal bearer token."""
    return "expired_token_xyz789"


# =============================================================================
# INVOICE FIXTURES
# =============================================================================


@pytest.fixture
def sample_invoice_payload() -> dict[str, Any]:
    """
    Realistic PayPal invoice creation response.

    Returns:
        Dictionary matching PayPal Invoicing API response format
    """
    return {
        "id": "INV2-ABCD-1234-5678",
        "invoice_number": "INV-2026-0001",
        "status": "DRAFT",
        "detail": {
            "invoice_number": "INV-2026-0001",
            "currency_code": "USD",
            "total_amount": {"currency_code": "USD", "value": "1500.00"},
        },
    }


@pytest.fixture
def sample_invoice_list() -> dict[str, Any]:
    """
    Realistic PayPal invoice list response.

    Returns:
        Dictionary with invoices array and pagination info
    """
    return {
        "total_items": 2,
        "total_pages": 1,
        "invoices": [
            {
                "id": "INV2-AAAA",
                "status": "PAID",
                "detail": {
                    "invoice_number": "INV-2026-0001",
                    "total_amount": {"currency_code": "USD", "value": "1500.00"},
                },
            },
            {
                "id": "INV2-BBBB",
                "status": "SENT",
                "detail": {
                    "invoice_number": "INV-2026-0002",
                    "total_amount": {"currency_code": "USD", "value": "750.00"},
                },
            },
        ],
    }


# =============================================================================
# DISPUTE FIXTURES
# =============================================================================


@pytest.fixture
def sample_dispute_payload() -> dict[str, Any]:
    """
    Realistic PayPal dispute payload.

    Returns:
        Dictionary matching PayPal Disputes API response format
    """
    return {
        "dispute_id": "PP-D-12345",
        "reason": "Item not received",
        "status": "WAITING_FOR_SELLER_RESPONSE",
        "dispute_amount": {"currency_code": "USD", "value": "250.00"},
        "create_time": "2026-11-01T10:30:00Z",
        "buyer": {"name": "Jane Customer", "email": "jane@example.com"},
        "disputed_transactions": [
            {
                "transaction_id": "TX888888",
                "items": [
                    {
                        "name": "Consulting Service",
                        "quantity": "1",
                        "unit_price": {"currency_code": "USD", "value": "250.00"},
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_dispute_list() -> dict[str, Any]:
    """
    Realistic PayPal dispute list response.

    Returns:
        Dictionary with items array and total count
    """
    return {
        "items": [
            {
                "dispute_id": "PP-D-11111",
                "reason": "Unauthorized transaction",
                "status": "OPEN",
                "dispute_amount": {"currency_code": "USD", "value": "100.00"},
            }
        ],
        "total_items": 1,
    }


# =============================================================================
# ELASTICSEARCH FIXTURES
# =============================================================================


@pytest.fixture
def sample_es_hits() -> list[dict[str, Any]]:
    """
    Realistic Elasticsearch search hits.

    Returns:
        List of hit dictionaries with _source containing transaction data
    """
    return [
        {
            "_index": "payflow_transactions",
            "_id": "adobe_52.99_usd",
            "_source": {
                "description": "Adobe Creative Cloud",
                "ai_category": "Software Subscription",
                "amount": 52.99,
                "amount_formatted": "52.99 USD",
                "currency": "USD",
                "confidence": 0.88,
                "status": "S",
                "indexed_at": "2026-11-06T12:00:00Z",
            },
        },
        {
            "_index": "payflow_transactions",
            "_id": "starbucks_7.50_usd",
            "_source": {
                "description": "Starbucks Coffee",
                "ai_category": "Personal Expense",
                "amount": 7.50,
                "amount_formatted": "7.50 USD",
                "currency": "USD",
                "confidence": 0.78,
                "status": "S",
                "indexed_at": "2026-11-06T11:00:00Z",
            },
        },
    ]


# =============================================================================
# FASTAPI CLIENT FIXTURE
# =============================================================================


@pytest.fixture
def api_client():
    """
    FastAPI TestClient with the classifier mocked at import time.

    The api.py module loads the classifier at import time, so we patch
    the transformers.pipeline BEFORE importing the app.

    Yields:
        TestClient instance for making HTTP requests to the API
    """
    from unittest.mock import patch

    mock_pipeline = MagicMock(
        return_value=MagicMock(
            side_effect=lambda text, cats: {"labels": ["Personal Expense"], "scores": [0.75]}
        )
    )

    with patch("api.pipeline", return_value=mock_pipeline):
        # Force re-import to pick up the mock
        import importlib

        import api as api_module

        importlib.reload(api_module)
        with api_module.TestClient(api_module.app) as client:
            yield client


# =============================================================================
# INTEGRATION TEST FIXTURES
# =============================================================================


@pytest.fixture
def integration_es_client():
    """
    Mock Elasticsearch client that behaves realistically.

    Stores documents in-memory so that bulk index → search flows work
    end-to-end without a running Elasticsearch instance.

    Features:
    - Index creation/deletion
    - Document indexing
    - Multi-match search (simplified)
    - Sorting by indexed_at
    - Count operations

    Yields:
        InMemoryES instance for integration tests
    """

    class InMemoryES:
        """In-memory Elasticsearch mock for integration tests."""

        class _Indices:
            """Mock for ES indices operations."""

            def __init__(self, outer: "InMemoryES"):
                self._outer = outer

            def exists(self, index: str) -> bool:
                return index in self._outer._indices

            def create(self, index: str, mappings: dict = None, settings: dict = None) -> dict:
                self._outer._indices[index] = {"mappings": mappings, "settings": settings}
                self._outer._docs.setdefault(index, {})
                return {"acknowledged": True}

            def delete(self, index: str) -> dict:
                self._outer._indices.pop(index, None)
                self._outer._docs.pop(index, None)
                return {"acknowledged": True}

            def stats(self, index: str) -> dict:
                docs = self._outer._docs.get(index, {})
                return {
                    "indices": {
                        index: {
                            "total": {
                                "docs": {"count": len(docs)},
                                "store": {"size_in_bytes": 1024},
                            }
                        }
                    }
                }

        def __init__(self):
            self._indices: dict[str, dict] = {}
            self._docs: dict[str, dict[str, dict]] = {}
            self.indices = self._Indices(self)

        def index(self, index: str, id: str, document: dict) -> dict:
            """Index a single document."""
            self._docs.setdefault(index, {})[id] = document
            return {"result": "created"}

        def search(self, index: str, body: dict = None, **kwargs) -> dict:
            """Search with simplified query matching."""
            docs = self._docs.get(index, {})
            hits = [
                {"_index": index, "_id": doc_id, "_source": doc}
                for doc_id, doc in docs.items()
            ]

            # Simple query matching for integration tests
            if body and "query" in body:
                query = body["query"]
                if "multi_match" in query:
                    search_text = query["multi_match"]["query"].lower()
                    hits = [h for h in hits if search_text in str(h["_source"]).lower()]

            # Apply sort
            if body and "sort" in body:
                for sort_spec in reversed(body["sort"]):
                    if isinstance(sort_spec, dict):
                        for field, order_spec in sort_spec.items():
                            if field == "_score":
                                continue
                            reverse = order_spec.get("order", "asc") == "desc"
                            hits.sort(
                                key=lambda h: h["_source"].get(field, ""),
                                reverse=reverse,
                            )

            # Apply size limit
            size = body.get("size", 10) if body else 10
            hits = hits[:size]

            return {"hits": {"hits": hits, "total": {"value": len(hits)}}}

        def count(self, index: str) -> dict:
            """Count documents in an index."""
            return {"count": len(self._docs.get(index, {}))}

    es = InMemoryES()
    with patch("elastic_manager.Elasticsearch", return_value=es):
        # Reset the module-level client so it picks up the mock
        import elastic_manager

        elastic_manager._client = None
        yield es
        elastic_manager._client = None


@pytest.fixture
def mock_hf_client():
    """
    Mock Hugging Face InferenceClient that returns deterministic responses.

    Returns different responses based on prompt content:
    - Financial analyst prompts → financial summary
    - Dispute resolution prompts → dispute response
    - Other prompts → generic response

    Returns:
        MagicMock with text_generation method
    """
    mock = MagicMock()

    def fake_text_generation(prompt: str, model: str = None, **kwargs) -> str:
        if "financial analyst" in prompt.lower():
            return (
                "Your financial activity shows strong freelance income dominance, "
                "with software subscriptions representing the primary expense category. "
                "Overall cash flow remains positive with healthy margins."
            )
        if "dispute resolution" in prompt.lower():
            return (
                "Dear Customer, thank you for reaching out regarding your dispute. "
                "We are actively investigating the matter and will respond within 24-48 hours "
                "with a resolution or request for additional information."
            )
        return "AI-generated response."

    mock.text_generation.side_effect = fake_text_generation
    return mock


@pytest.fixture
def mock_zapier():
    """
    Mock Zapier webhook endpoint.

    Patches requests.post in webhook_listener module to capture alert calls.

    Yields:
        MagicMock for verifying Zapier calls
    """
    with patch("webhook_listener.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def test_webhook_id() -> str:
    """Test webhook ID for signature verification tests."""
    return "TEST-WEBHOOK-ID-12345"


@pytest.fixture
def valid_webhook_payload() -> dict[str, Any]:
    """
    Construct a realistic PayPal webhook payload.

    Note: signature verification is mocked in integration tests.
    Real signature tests belong in unit tests for webhook_verifier.

    Returns:
        Dictionary matching PayPal webhook event format
    """
    return {
        "id": "WH-TEST-123",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "transaction_id": "TX-INTEGRATION-001",
            "amount": {"value": "500.00", "currency_code": "USD"},
            "custom_note": "Payment from TechCorp for consulting services",
            "invoice_id": "INV-2026-0001",
        },
    }


@pytest.fixture
def high_risk_webhook_payload() -> dict[str, Any]:
    """
    Webhook payload that should trigger a high-risk alert.

    Returns:
        Dictionary with suspicious transaction details
    """
    return {
        "id": "WH-TEST-999",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "transaction_id": "TX-HIGH-RISK-001",
            "amount": {"value": "50000.00", "currency_code": "USD"},
            "custom_note": "URGENT: Wire transfer to offshore account",
        },
    }


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """
    Set test environment variables for all tests.

    This fixture runs automatically (autouse=True) and ensures that
    tests don't depend on the developer's local .env file.
    """
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("PAYPAL_SECRET", "test_secret")
    monkeypatch.setenv("HF_TOKEN", "test_hf_token")
    monkeypatch.setenv("ES_HOST", "http://localhost:9200")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "test_webhook_id")


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_module_state():
    """
    Reset module-level state between tests.

    Ensures that tests don't leak state through module-level variables
    like Elasticsearch clients or cached tokens.
    """
    yield

    # Reset Elasticsearch client
    try:
        import elastic_manager

        elastic_manager._client = None
    except ImportError:
        pass

    # Reset token manager (if needed)
    try:
        from security import token_manager

        token_manager._default_manager = None
    except ImportError:
        pass