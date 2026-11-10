"""
Webhook Integration Tests
=========================

Tests the full webhook processing flow:
    HTTP Request → Signature Verification → AI Categorization → Risk Scoring → Zapier Alert

Version: 1.0.0
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


@pytest.fixture
def webhook_app():
    """
    Webhook listener app with mocked signature verification.

    For integration tests, we mock the verifier to simulate valid/invalid
    signatures. Real signature verification is tested in unit tests.
    """
    with patch("webhook_listener.PayPalWebhookVerifier") as mock_verifier_class:
        mock_verifier = MagicMock()
        mock_verifier.verify.return_value = (True, "Signature verified")
        mock_verifier_class.return_value = mock_verifier

        # Mock the classifier to avoid loading real ML models
        with patch("webhook_listener.pipeline") as mock_pipeline:
            mock_classifier = MagicMock()
            mock_classifier.side_effect = lambda text, cats: {
                "labels": ["Personal Expense"], "scores": [0.75]
            }
            mock_pipeline.return_value = mock_classifier

            import importlib
            import webhook_listener as webhook_module
            importlib.reload(webhook_module)

            # Override the verifier and classifier
            webhook_module.webhook_verifier = mock_verifier
            webhook_module.classifier = mock_classifier

            yield webhook_module, mock_verifier, mock_classifier


@pytest.fixture
def webhook_client(webhook_app):
    """TestClient for the webhook listener."""
    webhook_module, _, _ = webhook_app
    with TestClient(webhook_module.app) as client:
        yield client


# =============================================================================
# HAPPY PATH
# =============================================================================

class TestWebhookHappyPath:
    """Test successful webhook processing."""

    def test_valid_webhook_processed_successfully(
        self, webhook_client, valid_webhook_payload
    ):
        """Verify a valid webhook is processed end-to-end."""
        response = webhook_client.post(
            "/paypal-webhook",
            json=valid_webhook_payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["transaction_id"] == "TX-INTEGRATION-001"
        assert "ai_category" in data
        assert "risk_score" in data

    def test_webhook_triggers_ai_categorization(
        self, webhook_client, webhook_app, valid_webhook_payload
    ):
        """Verify that the webhook triggers AI categorization."""
        _, _, mock_classifier = webhook_app

        webhook_client.post(
            "/paypal-webhook",
            json=valid_webhook_payload,
        )

        # Verify classifier was called with the transaction description
        mock_classifier.assert_called()
        call_args = mock_classifier.call_args
        assert "consulting" in call_args[0][0].lower() or "payment" in call_args[0][0].lower()


# =============================================================================
# SECURITY PATH
# =============================================================================

class TestWebhookSecurityPath:
    """Test webhook security verification."""

    def test_invalid_signature_rejected(self, webhook_client, webhook_app, valid_webhook_payload):
        """Verify that invalid signatures are rejected with 401."""
        _, mock_verifier, _ = webhook_app
        mock_verifier.verify.return_value = (False, "Invalid signature")

        response = webhook_client.post(
            "/paypal-webhook",
            json=valid_webhook_payload,
        )

        assert response.status_code == 401
        data = response.json()
        assert data["status"] == "rejected"
        assert "Invalid signature" in data["reason"]

    def test_replay_attack_rejected(self, webhook_client, webhook_app, valid_webhook_payload):
        """Verify that old transmission times are rejected."""
        _, mock_verifier, _ = webhook_app
        mock_verifier.verify.return_value = (False, "Transmission time is too old")

        response = webhook_client.post(
            "/paypal-webhook",
            json=valid_webhook_payload,
        )

        assert response.status_code == 401


# =============================================================================
# RISK ALERT PATH
# =============================================================================

class TestWebhookRiskAlertPath:
    """Test that high-risk webhooks trigger Zapier alerts."""

    def test_high_risk_transaction_triggers_alert(
        self, webhook_client, webhook_app, high_risk_webhook_payload, mock_zapier
    ):
        """Verify that high-risk transactions trigger Zapier alerts."""
        _, _, mock_classifier = webhook_app

        # Make the classifier return "Suspicious Activity" with low confidence
        mock_classifier.side_effect = lambda text, cats: {
            "labels": ["Suspicious Activity"], "scores": [0.45]
        }

        response = webhook_client.post(
            "/paypal-webhook",
            json=high_risk_webhook_payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] >= 60.0

        # Verify Zapier was called
        mock_zapier.assert_called()
        call_kwargs = mock_zapier.call_args.kwargs
        assert "json" in call_kwargs
        alert_data = call_kwargs["json"]
        assert alert_data["risk_score"] >= 60.0
        assert alert_data["ai_category"] == "Suspicious Activity"

    def test_low_risk_transaction_no_alert(
        self, webhook_client, webhook_app, valid_webhook_payload, mock_zapier
    ):
        """Verify that low-risk transactions don't trigger alerts."""
        _, _, mock_classifier = webhook_app

        # Make the classifier return a safe category with high confidence
        mock_classifier.side_effect = lambda text, cats: {
            "labels": ["Software Subscription"], "scores": [0.95]
        }

        response = webhook_client.post(
            "/paypal-webhook",
            json=valid_webhook_payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] < 60.0

        # Verify Zapier was NOT called
        mock_zapier.assert_not_called()


# =============================================================================
# ERROR PATH
# =============================================================================

class TestWebhookErrorPath:
    """Test webhook error handling."""

    def test_invalid_json_returns_400(self, webhook_client):
        """Verify that invalid JSON returns 400."""
        response = webhook_client.post(
            "/paypal-webhook",
            content="not valid json{{{",
            headers={"Content-Type": "application/json"},
        )
        # Note: FastAPI may return 422 for malformed JSON before our handler runs
        assert response.status_code in [400, 422]

    def test_missing_resource_fields_handled_gracefully(
        self, webhook_client, webhook_app
    ):
        """Verify that missing resource fields are handled gracefully."""
        payload = {
            "id": "WH-MINIMAL",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {},  # Empty resource
        }

        response = webhook_client.post(
            "/paypal-webhook",
            json=payload,
        )

        # Should still succeed with defaults
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


# =============================================================================
# HEALTH CHECK
# =============================================================================

class TestWebhookHealth:
    """Test webhook listener health endpoint."""

    def test_health_endpoint(self, webhook_client):
        """Verify health endpoint returns expected structure."""
        response = webhook_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "PayFlow AI Webhook Listener"
        assert "ai_model" in data