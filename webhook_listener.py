"""
Webhook Listener
================

FastAPI service that receives real-time PayPal payment events, verifies
their cryptographic signatures, categorises them with the AI engine,
scores their risk, and raises alerts for suspicious activity.

Security posture:
    - Every request is verified against PayPal's signing certificate
      BEFORE any processing occurs.
    - Transmission timestamps are checked to prevent replay attacks.
    - All verification outcomes (success and failure) are logged for audit.

Version: 3.0.0
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pyngrok import ngrok
from transformers import pipeline

from observability import logging as obs_logging, metrics, tracing
from security.webhook_verifier import PayPalWebhookVerifier

load_dotenv()
logger = obs_logging.get_logger("webhook-listener")

# =============================================================================
# CONFIGURATION
# =============================================================================

ZAPIER_WEBHOOK_URL: str = os.getenv("ZAPIER_WEBHOOK_URL", "")
NGROK_AUTH_TOKEN: str = os.getenv("NGROK_AUTH_TOKEN", "")
PAYPAL_WEBHOOK_ID: str = os.getenv("PAYPAL_WEBHOOK_ID", "")

if not PAYPAL_WEBHOOK_ID:
    raise ValueError("PAYPAL_WEBHOOK_ID must be set in the environment")

CATEGORIES: list[str] = [
    "Freelance Income",
    "Software Subscription",
    "Personal Expense",
    "Suspicious Activity",
]

RISK_SCORE_THRESHOLD: float = 60.0
CONFIDENCE_THRESHOLD: float = 0.60

# =============================================================================
# APPLICATION BOOTSTRAP
# =============================================================================

app = FastAPI(
    title="PayFlow AI Webhook Listener",
    description="Secure real-time PayPal webhook processor with AI categorisation.",
    version="3.0.0",
)

tracing.setup_tracing(app, service_name="payflow-webhook")
tracer = tracing.get_tracer("payflow-webhook")

webhook_verifier = PayPalWebhookVerifier(PAYPAL_WEBHOOK_ID)

logger.info("loading_ai_model", model="facebook/bart-large-mnli")
print("🧠 Loading AI categorisation model...")
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
print("✅ AI model loaded.")
logger.info("ai_model_loaded")
metrics.set_model_loaded(True)

# =============================================================================
# WEBHOOK ENDPOINT
# =============================================================================

@app.post("/paypal-webhook")
async def receive_paypal_event(request: Request) -> JSONResponse:
    """
    Receive, verify, and process a PayPal webhook event.

    The response is always 2xx on successful processing so PayPal does not
    retry. Signature failures return 401 to signal the rejection clearly.
    """
    start = time.perf_counter()

    with tracer.start_as_current_span("receive_paypal_webhook") as span:
        try:
            body = await request.body()
            body_str = body.decode("utf-8")
            headers = dict(request.headers)

            logger.info(
                "webhook_received",
                content_length=len(body_str),
                headers_count=len(headers),
            )

            # ---- Step 1: Cryptographic verification ----
            is_valid, message = webhook_verifier.verify(headers, body_str)

            if not is_valid:
                duration = time.perf_counter() - start
                logger.warning(
                    "webhook_verification_failed",
                    reason=message,
                    duration_ms=round(duration * 1000, 2),
                )
                metrics.record_webhook(
                    verified=False,
                    event_type="verification_failed",
                    processing_time=duration,
                )
                span.set_attribute("verification", "failed")
                span.set_attribute("failure_reason", message)
                return JSONResponse(
                    status_code=401,
                    content={"status": "rejected", "reason": message},
                )

            logger.info("webhook_verified", message=message)
            span.set_attribute("verification", "success")

            # ---- Step 2: Parse payload ----
            try:
                payload = await request.json()
            except ValueError as exc:
                logger.error("payload_parse_failed", error=str(exc))
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "reason": "Invalid JSON payload"},
                )

            event_type = payload.get("event_type", "UNKNOWN")
            resource = payload.get("resource", {}) or {}

            amount = resource.get("amount", {}).get("value", "0.00")
            currency = resource.get("amount", {}).get("currency_code", "USD")
            description = (
                resource.get("custom_note")
                or resource.get("invoice_id")
                or resource.get("transaction_id")
                or "Standard Transfer"
            )
            transaction_id = resource.get("transaction_id", "N/A")

            span.set_attribute("event_type", event_type)
            span.set_attribute("transaction_id", transaction_id)

            logger.info(
                "processing_webhook",
                event_type=event_type,
                transaction_id=transaction_id,
                amount=f"{amount} {currency}",
            )

            # ---- Step 3: AI categorisation ----
            category, confidence, ai_duration = _categorise(description)
            span.set_attribute("ai_category", category)
            span.set_attribute("ai_confidence", confidence)

            # ---- Step 4: Risk scoring ----
            risk_score = _compute_risk_score(category, confidence)
            span.set_attribute("risk_score", risk_score)
            metrics.record_risk_score(risk_score)

            # ---- Step 5: Alert if high-risk ----
            if risk_score >= RISK_SCORE_THRESHOLD:
                _raise_alert(
                    transaction_id=transaction_id,
                    amount=amount,
                    currency=currency,
                    description=description,
                    category=category,
                    confidence=confidence,
                    risk_score=risk_score,
                    event_type=event_type,
                )

            # ---- Step 6: Return success ----
            duration = time.perf_counter() - start
            logger.info(
                "webhook_processed_successfully",
                transaction_id=transaction_id,
                category=category,
                risk_score=risk_score,
                total_duration_ms=round(duration * 1000, 2),
            )
            metrics.record_webhook(
                verified=True,
                event_type=event_type,
                processing_time=duration,
            )

            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "transaction_id": transaction_id,
                    "ai_category": category,
                    "confidence": f"{confidence:.1%}",
                    "risk_score": risk_score,
                    "message": "Webhook processed successfully",
                },
            )

        except Exception as exc:
            duration = time.perf_counter() - start
            logger.error(
                "webhook_processing_exception",
                error=str(exc),
                exc_info=True,
                duration_ms=round(duration * 1000, 2),
            )
            metrics.record_webhook(
                verified=False,
                event_type="exception",
                processing_time=duration,
            )
            return JSONResponse(
                status_code=500,
                content={"status": "error", "reason": f"Processing error: {exc}"},
            )


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================

@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Liveness probe for container orchestrators."""
    return {
        "status": "healthy",
        "service": "PayFlow AI Webhook Listener",
        "version": "3.0.0",
        "ai_model": "facebook/bart-large-mnli",
        "webhook_id_configured": bool(PAYPAL_WEBHOOK_ID),
    }


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _categorise(description: str) -> tuple[str, float, float]:
    """
    Run the AI classifier on a description.

    Returns:
        Tuple of ``(category, confidence, duration_seconds)``.
    """
    start = time.perf_counter()
    try:
        result = classifier(description, CATEGORIES)
        category = result["labels"][0]
        confidence = float(result["scores"][0])
        duration = time.perf_counter() - start

        metrics.record_ai_categorization(category, confidence=confidence)
        metrics.record_ai_inference(duration, model="bart-large-mnli")

        logger.info(
            "ai_categorisation_completed",
            category=category,
            confidence=f"{confidence:.1%}",
            duration_ms=round(duration * 1000, 2),
        )
        return category, confidence, duration

    except Exception as exc:
        duration = time.perf_counter() - start
        metrics.record_ai_inference(duration, model="bart-large-mnli")
        logger.error("ai_categorisation_failed", error=str(exc), exc_info=True)
        return "Unknown", 0.0, duration


def _compute_risk_score(category: str, confidence: float) -> float:
    """
    Heuristic risk score for webhook events.

    Full weighted scoring lives in ``risk_engine``; webhooks use a simpler
    rule-based approach because they lack the portfolio context needed for
    the weighted formula.
    """
    if category == "Suspicious Activity":
        return 90.0
    if confidence < CONFIDENCE_THRESHOLD:
        return 70.0
    if category == "Personal Expense":
        return 30.0
    return 10.0


def _raise_alert(
    *,
    transaction_id: str,
    amount: str,
    currency: str,
    description: str,
    category: str,
    confidence: float,
    risk_score: float,
    event_type: str,
) -> None:
    """Post a risk alert to Zapier if configured."""
    if not ZAPIER_WEBHOOK_URL:
        logger.warning("zapier_webhook_url_not_configured")
        return

    alert = {
        "transaction_id": transaction_id,
        "amount": f"{amount} {currency}",
        "description": description,
        "ai_category": category,
        "confidence": f"{confidence:.1%}",
        "risk_score": risk_score,
        "event_type": event_type,
        "alert_reason": "High-risk transaction detected",
    }

    logger.warning(
        "high_risk_transaction_detected",
        risk_score=risk_score,
        category=category,
        confidence=f"{confidence:.1%}",
    )

    start = time.perf_counter()
    try:
        requests.post(ZAPIER_WEBHOOK_URL, json=alert, timeout=5)
        duration = time.perf_counter() - start
        logger.info("zapier_alert_sent", duration_ms=round(duration * 1000, 2))
    except Exception as exc:
        logger.error("zapier_alert_failed", error=str(exc))


# =============================================================================
# SERVER ENTRYPOINT
# =============================================================================

def start_server() -> None:
    """Start the FastAPI server, optionally behind an ngrok tunnel."""
    if not NGROK_AUTH_TOKEN:
        logger.warning("ngrok_auth_token_not_set")
        print("⚠️ NGROK_AUTH_TOKEN not set. Running without tunnel.")
        print("🌐 Local webhook URL: http://localhost:8001/paypal-webhook")
        uvicorn.run(app, host="0.0.0.0", port=8001)
        return

    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    public_url = ngrok.connect(8001).public_url
    webhook_url = f"{public_url}/paypal-webhook"

    logger.info("ngrok_tunnel_created", public_url=webhook_url)

    print("=" * 70)
    print("🔔 PayFlow AI Webhook Listener v3.0.0")
    print("=" * 70)
    print(f"🌐 Public Webhook URL: {webhook_url}")
    print("👉 Paste this URL into the PayPal Developer Dashboard.")
    print("=" * 70)
    print("\nPress CTRL+C to stop the server.\n")

    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    start_server()