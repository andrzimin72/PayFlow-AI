"""
Generative AI Module
====================

Wraps Mistral-7B (via Hugging Face Inference API) for two narrative tasks:

    1. **Financial summaries** — synthesise a categorised transaction ledger
       into a short, professional analyst-style commentary.
    2. **Dispute responses** — draft empathetic, solution-oriented replies
       to customer disputes (called by ``dispute_manager``).

Prompt construction is the core value here. The models are stateless; the
prompts are what make the output useful.

Version: 3.0.0
"""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from observability import logging as obs_logging, metrics

load_dotenv()
logger = obs_logging.get_logger("generative-ai")

# =============================================================================
# CONFIGURATION
# =============================================================================

HF_TOKEN: str | None = os.getenv("HF_TOKEN")
MODEL_NAME: str = os.getenv("GENERATIVE_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")

# Generation parameters — tuned for concise, professional output
SUMMARY_MAX_TOKENS: int = 150
SUMMARY_TEMPERATURE: float = 0.7

DISPUTE_MAX_TOKENS: int = 300
DISPUTE_TEMPERATURE: float = 0.7

# =============================================================================
# CLIENT INITIALISATION
# =============================================================================

_client: InferenceClient | None = None


def _get_client() -> InferenceClient | None:
    """Lazily initialise the Hugging Face Inference client."""
    global _client
    if _client is None:
        if not HF_TOKEN:
            logger.warning("hf_token_not_configured")
            return None
        try:
            _client = InferenceClient(token=HF_TOKEN)
            logger.info("huggingface_client_initialised", model=MODEL_NAME)
        except Exception as exc:
            logger.error("huggingface_client_init_failed", error=str(exc), exc_info=True)
            return None
    return _client


# =============================================================================
# FINANCIAL SUMMARY
# =============================================================================

def generate_financial_summary(df: pd.DataFrame) -> str:
    """
    Synthesise a categorised transaction ledger into a short analyst-style summary.

    Args:
        df: DataFrame with columns ``Amount``, ``Description``, ``AI Category``,
            ``Confidence``.

    Returns:
        A 2-3 sentence financial summary, or an error message if generation fails.
    """
    if df.empty:
        logger.warning("generate_summary_called_with_empty_dataframe")
        return "No transaction data available to analyse."

    client = _get_client()
    if client is None:
        return "⚠️ AI summary generation unavailable: Hugging Face client not initialised."

    context = _build_transaction_context(df)
    prompt = _build_summary_prompt(context)

    start = time.perf_counter()
    try:
        response = client.text_generation(
            prompt,
            model=MODEL_NAME,
            max_new_tokens=SUMMARY_MAX_TOKENS,
            temperature=SUMMARY_TEMPERATURE,
            do_sample=True,
        )
        duration = time.perf_counter() - start
        summary = response.strip()

        metrics.record_ai_inference(duration, model="mistral-7b-summary")
        logger.info(
            "financial_summary_generated",
            transaction_count=len(df),
            summary_length=len(summary),
            duration_ms=round(duration * 1000, 2),
        )
        return summary

    except Exception as exc:
        duration = time.perf_counter() - start
        metrics.record_ai_inference(duration, model="mistral-7b-summary")
        logger.error(
            "financial_summary_generation_failed",
            error=str(exc),
            exc_info=True,
            duration_ms=round(duration * 1000, 2),
        )
        return f"⚠️ AI summary generation failed: {exc}"


def _build_transaction_context(df: pd.DataFrame) -> str:
    """Format the DataFrame into a readable text block for the LLM."""
    lines = []
    for _, row in df.iterrows():
        category = row.get("AI Category", "Unknown")
        amount = row.get("Amount", "0.00")
        description = row.get("Description", "")
        lines.append(f"- {category}: {amount} (Note: {description})")
    return "\n".join(lines)


def _build_summary_prompt(context: str) -> str:
    """Construct the analyst-style summary prompt."""
    return (
        "You are an expert AI financial analyst. "
        "Analyse the following categorised PayPal transactions and provide a brief, "
        "2-3 sentence summary of the user's financial activity. "
        "Highlight the dominant spending or income category and the overall cash flow trend. "
        "Keep the tone professional, insightful, and encouraging.\n\n"
        f"Recent Transactions:\n{context}\n\n"
        "Summary:"
    )


# =============================================================================
# DISPUTE RESPONSE
# =============================================================================

def generate_dispute_response(dispute_details: dict[str, Any]) -> str:
    """
    Draft a professional, empathetic response to a customer dispute.

    Note: timing and metrics are recorded by the caller
    (``dispute_manager.generate_dispute_response``) to avoid double-counting.

    Args:
        dispute_details: PayPal dispute payload.

    Returns:
        AI-generated response text, or an error message on failure.
    """
    client = _get_client()
    if client is None:
        return "⚠️ AI response generation unavailable: Hugging Face client not initialised."

    dispute_id = dispute_details.get("dispute_id", "unknown")
    prompt = _build_dispute_prompt(dispute_details)

    try:
        response = client.text_generation(
            prompt,
            model=MODEL_NAME,
            max_new_tokens=DISPUTE_MAX_TOKENS,
            temperature=DISPUTE_TEMPERATURE,
            do_sample=True,
        )
        result = response.strip()
        logger.info("dispute_response_generated", dispute_id=dispute_id, length=len(result))
        return result

    except Exception as exc:
        logger.error(
            "dispute_response_generation_failed",
            dispute_id=dispute_id,
            error=str(exc),
            exc_info=True,
        )
        return f"⚠️ Unable to generate response: {exc}"


def _build_dispute_prompt(dispute_details: dict[str, Any]) -> str:
    """Construct the dispute-response prompt from the PayPal payload."""
    dispute_id = dispute_details.get("dispute_id", "Unknown")
    reason = dispute_details.get("reason", "Unknown")
    status = dispute_details.get("status", "Unknown")
    amount_info = dispute_details.get("dispute_amount", {})
    amount = amount_info.get("value", "0.00")
    currency = amount_info.get("currency_code", "USD")
    create_time = dispute_details.get("create_time", "Unknown")

    buyer_name = dispute_details.get("buyer", {}).get("name", "Customer")

    transaction_info = _extract_transaction_info(dispute_details, currency)

    return (
        "You are a professional dispute resolution specialist for a fintech company. "
        "A customer has filed a dispute with the following details:\n\n"
        f"Dispute ID: {dispute_id}\n"
        f"Reason: {reason}\n"
        f"Status: {status}\n"
        f"Amount: {amount} {currency}\n"
        f"Date Filed: {create_time}\n"
        f"Customer Name: {buyer_name}\n"
        f"{transaction_info}\n"
        "Generate a professional, empathetic, and solution-oriented response to this dispute. "
        "The response should:\n"
        "1. Acknowledge the customer's concern\n"
        "2. Request any additional information needed\n"
        "3. Outline the next steps in the resolution process\n"
        "4. Maintain a professional and courteous tone\n"
        "5. Be concise (150-200 words)\n\n"
        "Response:"
    )


def _extract_transaction_info(dispute_details: dict[str, Any], currency: str) -> str:
    """Pull the first disputed transaction's item details into a readable block."""
    disputed = dispute_details.get("disputed_transactions", [])
    if not disputed:
        return ""

    items = disputed[0].get("items", [])
    if not items:
        return ""

    item = items[0]
    unit_price = item.get("unit_price", {}).get("value", "0.00")
    return (
        "\nTransaction Details:\n"
        f"- Item: {item.get('name', 'Unknown')}\n"
        f"- Quantity: {item.get('quantity', '1')}\n"
        f"- Unit Price: {unit_price} {currency}\n"
    )