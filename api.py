"""
PayFlow AI REST API
===================

FastAPI application exposing the full platform over HTTPS:

    /health, /metrics           — operational endpoints
    /transactions, /search      — data retrieval
    /analyze                    — trigger the AI pipeline
    /risk/*                     — risk scoring (single, portfolio, list)
    /invoices, /invoices/create — invoice management
    /disputes, /disputes/{id}/generate-response — dispute handling

All endpoints are rate-limited, validated with Pydantic v2, traced with
OpenTelemetry, and logged with structured JSON.

Version: 4.1.0
"""

from __future__ import annotations

import time
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, constr
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from transformers import pipeline

import ai_engine
import dispute_manager
import elastic_manager
import invoice_manager
import paypal_client
import risk_engine
from observability import logging as obs_logging, metrics, tracing

logger = obs_logging.get_logger("payflow-api")

# =============================================================================
# BOOTSTRAP
# =============================================================================

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="PayFlow AI Financial API",
    description=(
        "Enterprise-grade API for PayPal transaction management with AI-powered "
        "categorisation, risk scoring, invoicing and dispute resolution."
    ),
    version="4.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter

tracing.setup_tracing(app, service_name="payflow-api")
tracer = tracing.get_tracer("payflow-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning("rate_limit_exceeded", endpoint=request.url.path)
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "message": "Please try again later."},
    )


@app.exception_handler(Exception)
async def _general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", endpoint=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": "An unexpected error occurred."},
    )

# =============================================================================
# AI MODEL
# =============================================================================

logger.info("loading_ai_model", model="facebook/bart-large-mnli")
print("🧠 Loading AI categorisation model for API...")
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
print("✅ AI model loaded.")
logger.info("ai_model_loaded")
metrics.set_model_loaded(True)

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class TransactionResponse(BaseModel):
    description: constr(min_length=1, max_length=500)
    ai_category: str
    amount: float = Field(..., ge=0)
    confidence: float = Field(..., ge=0, le=1)
    status: str = "Unknown"


class SearchResponse(BaseModel):
    total_results: int = Field(..., ge=0)
    transactions: list[TransactionResponse]


class AnalyzeResponse(BaseModel):
    message: str
    transactions_processed: int
    categories_found: int


class InvoiceItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., ge=1, le=1000)
    unit_price: float = Field(..., ge=0, le=1_000_000)
    description: str | None = Field(None, max_length=500)


class CreateInvoiceRequest(BaseModel):
    merchant_email: str = Field(..., min_length=5, max_length=100)
    client_email: str = Field(..., min_length=5, max_length=100)
    client_name: str = Field(..., min_length=1, max_length=200)
    items: list[InvoiceItem] = Field(..., min_length=1, max_length=50)
    note: str | None = Field(None, max_length=1000)
    payment_terms: str = Field("NET_30", pattern="^(NET_10|NET_15|NET_30|DUE_ON_RECEIPT)$")


class InvoiceResponse(BaseModel):
    success: bool
    invoice_id: str | None = None
    invoice_number: str | None = None
    status: str | None = None
    message: str


class RiskScoreRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    amount: float = Field(..., ge=0)
    ai_category: str
    ai_confidence: float = Field(..., ge=0, le=1)


class RiskScoreResponse(BaseModel):
    description: str
    amount: float
    ai_category: str
    ai_confidence: float
    risk_score: float
    risk_level: str
    risk_color: str
    recommended_action: str
    action_description: str


class PortfolioRiskResponse(BaseModel):
    status: str
    portfolio_risk_score: float
    risk_level: str
    risk_color: str
    risk_description: str
    recommended_action: str
    total_transactions: int
    risk_distribution: dict[str, int]
    high_risk_count: int
    high_risk_percentage: float
    average_risk_score: float
    max_risk_score: float
    min_risk_score: float


class RiskTransactionResponse(BaseModel):
    description: str
    amount: str
    amount_value: float
    ai_category: str
    ai_confidence: float
    anomaly_score: float
    risk_score: float
    risk_level: str
    risk_color: str
    recommended_action: str
    action_description: str


class RiskTransactionsResponse(BaseModel):
    total_transactions: int
    high_risk_count: int
    transactions: list[RiskTransactionResponse]

# =============================================================================
# HEALTH & MONITORING
# =============================================================================

@app.get("/", tags=["Health"])
@limiter.limit("60/minute")
async def root(request: Request) -> dict[str, Any]:
    logger.info("root_endpoint_called")
    return {
        "status": "healthy",
        "service": "PayFlow AI Financial API",
        "version": "4.1.0",
        "features": ["transactions", "search", "ai", "risk", "invoices", "disputes"],
    }


@app.get("/health", tags=["Health"])
@limiter.limit("60/minute")
async def health(request: Request) -> dict[str, Any]:
    logger.info("health_endpoint_called")
    return {
        "status": "healthy",
        "service": "PayFlow AI Financial API",
        "version": "4.1.0",
        "ai_model": "facebook/bart-large-mnli",
        "risk_engine": "enabled",
        "observability": {"metrics": "enabled", "tracing": "enabled", "logging": "structured"},
    }


@app.get("/metrics", tags=["Monitoring"])
async def metrics_endpoint() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# =============================================================================
# DATA ENDPOINTS
# =============================================================================

@app.get("/transactions", response_model=SearchResponse, tags=["Data"])
@limiter.limit("30/minute")
async def get_all_transactions(request: Request) -> dict[str, Any]:
    with tracer.start_as_current_span("get_all_transactions") as span:
        logger.info("get_all_transactions_called")
        start = time.perf_counter()
        try:
            df = elastic_manager.get_all_transactions()
            duration = time.perf_counter() - start
            metrics.record_elasticsearch_query(duration, operation="get_all")
            if df.empty:
                span.set_attribute("result_count", 0)
                return {"total_results": 0, "transactions": []}
            records = df.to_dict(orient="records")
            metrics.set_transaction_count(len(records))
            span.set_attribute("result_count", len(records))
            return {"total_results": len(records), "transactions": records}
        except Exception as exc:
            logger.error("get_transactions_failed", error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch transactions")


@app.get("/search", response_model=SearchResponse, tags=["Data"])
@limiter.limit("30/minute")
async def search_transactions(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    with tracer.start_as_current_span("search_transactions") as span:
        logger.info("search_transactions_called", query=q, limit=limit)
        start = time.perf_counter()
        try:
            df = elastic_manager.search_transactions(q)
            duration = time.perf_counter() - start
            metrics.record_elasticsearch_query(duration, operation="search")
            if df.empty:
                span.set_attribute("result_count", 0)
                return {"total_results": 0, "transactions": []}
            limited = df.head(limit).to_dict(orient="records")
            span.set_attribute("result_count", len(limited))
            return {"total_results": len(df), "transactions": limited}
        except Exception as exc:
            logger.error("search_failed", query=q, error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to search transactions")


@app.get("/categories", tags=["Data"])
@limiter.limit("60/minute")
async def get_categories(request: Request) -> dict[str, Any]:
    categories = ai_engine.get_categories()
    return {"categories": categories, "count": len(categories)}

# =============================================================================
# AI ENDPOINTS
# =============================================================================

@app.post("/analyze", response_model=AnalyzeResponse, tags=["AI"])
@limiter.limit("5/minute")
async def analyze_new_transactions(request: Request) -> dict[str, Any]:
    with tracer.start_as_current_span("analyze_transactions") as span:
        logger.info("analyze_endpoint_called")
        try:
            token = paypal_client.get_access_token()
            if not token:
                raise HTTPException(status_code=500, detail="PayPal authentication failed")

            raw = paypal_client.fetch_transactions(token)
            if not raw:
                span.set_attribute("transactions_processed", 0)
                return {"message": "No new transactions found", "transactions_processed": 0, "categories_found": 0}

            start = time.perf_counter()
            df = ai_engine.process_transactions(raw, classifier)
            inference_time = time.perf_counter() - start
            metrics.record_ai_inference(inference_time)
            span.set_attribute("inference_time_seconds", inference_time)

            elastic_manager.index_transactions(df)
            total_tx = elastic_manager.get_all_transactions()
            metrics.set_transaction_count(len(total_tx))

            categories_found = int(df["AI Category"].nunique()) if not df.empty else 0
            span.set_attribute("transactions_processed", len(df))
            span.set_attribute("categories_found", categories_found)

            logger.info(
                "analyze_completed",
                transactions_processed=len(df),
                categories_found=categories_found,
                inference_time=f"{inference_time:.3f}s",
            )
            return {
                "message": f"Successfully analyzed {len(df)} transactions",
                "transactions_processed": len(df),
                "categories_found": categories_found,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("analyze_failed", error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Analysis pipeline failed: {exc}")

# =============================================================================
# RISK ENDPOINTS
# =============================================================================

@app.post("/risk/score", response_model=RiskScoreResponse, tags=["Risk Management"])
@limiter.limit("30/minute")
async def score_single_transaction(
    request: Request, transaction: RiskScoreRequest
) -> dict[str, Any]:
    with tracer.start_as_current_span("score_single_transaction") as span:
        logger.info("score_transaction_called", amount=transaction.amount)
        try:
            all_tx = elastic_manager.get_all_transactions()
            if not all_tx.empty:
                amounts = all_tx["amount"].apply(
                    lambda v: float(str(v).split()[0]) if isinstance(v, str) else float(v)
                )
                avg_amount = float(amounts.mean())
            else:
                avg_amount = transaction.amount

            if avg_amount > 0:
                ratio = transaction.amount / avg_amount
                estimated_anomaly = min(1.0, max(0.0, (ratio - 1.0) / 4.0))
            else:
                estimated_anomaly = 0.5

            risk_score = risk_engine.calculate_risk_score(
                anomaly_score=estimated_anomaly,
                ai_confidence=transaction.ai_confidence,
                amount=transaction.amount,
                avg_amount=avg_amount,
            )
            level = risk_engine.get_risk_level(risk_score)
            metrics.record_risk_score(risk_score)

            span.set_attribute("risk_score", risk_score)
            span.set_attribute("risk_level", level["level"])

            return {
                "description": transaction.description,
                "amount": transaction.amount,
                "ai_category": transaction.ai_category,
                "ai_confidence": transaction.ai_confidence,
                "risk_score": risk_score,
                "risk_level": level["level"],
                "risk_color": level["color"],
                "recommended_action": level["action"],
                "action_description": level["description"],
            }
        except Exception as exc:
            logger.error("score_transaction_failed", error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to score transaction: {exc}")


@app.get("/risk/portfolio", response_model=PortfolioRiskResponse, tags=["Risk Management"])
@limiter.limit("10/minute")
async def get_portfolio_risk(request: Request) -> dict[str, Any]:
    with tracer.start_as_current_span("get_portfolio_risk") as span:
        logger.info("portfolio_risk_called")
        try:
            m = risk_engine.get_portfolio_risk_metrics()
            if m["status"] != "success":
                return {
                    "status": m["status"],
                    "portfolio_risk_score": 0.0,
                    "risk_level": "LOW",
                    "risk_color": "#28a745",
                    "risk_description": m.get("message", "No data available"),
                    "recommended_action": "AUTO_APPROVE",
                    "total_transactions": 0,
                    "risk_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
                    "high_risk_count": 0,
                    "high_risk_percentage": 0.0,
                    "average_risk_score": 0.0,
                    "max_risk_score": 0.0,
                    "min_risk_score": 0.0,
                }
            span.set_attribute("portfolio_risk_score", m["portfolio_risk_score"])
            span.set_attribute("risk_level", m["risk_level"])
            return {
                "status": m["status"],
                "portfolio_risk_score": m["portfolio_risk_score"],
                "risk_level": m["risk_level"],
                "risk_color": m["risk_color"],
                "risk_description": m["risk_description"],
                "recommended_action": m["recommended_action"],
                "total_transactions": m["total_transactions"],
                "risk_distribution": m["risk_distribution"],
                "high_risk_count": m["high_risk_count"],
                "high_risk_percentage": m["high_risk_percentage"],
                "average_risk_score": m["average_risk_score"],
                "max_risk_score": m["max_risk_score"],
                "min_risk_score": m["min_risk_score"],
            }
        except Exception as exc:
            logger.error("portfolio_risk_failed", error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get portfolio risk: {exc}")


@app.get("/risk/transactions", response_model=RiskTransactionsResponse, tags=["Risk Management"])
@limiter.limit("10/minute")
async def get_risk_scored_transactions(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    min_risk_score: float = Query(0, ge=0, le=100),
) -> dict[str, Any]:
    with tracer.start_as_current_span("get_risk_transactions") as span:
        logger.info("risk_transactions_called", limit=limit, min_risk_score=min_risk_score)
        try:
            scored = risk_engine.score_all_transactions()
            filtered = [t for t in scored if t["risk_score"] >= min_risk_score][:limit]
            high_risk_count = sum(1 for t in filtered if t["risk_score"] >= 60)
            span.set_attribute("total_returned", len(filtered))
            span.set_attribute("high_risk_count", high_risk_count)
            return {
                "total_transactions": len(filtered),
                "high_risk_count": high_risk_count,
                "transactions": filtered,
            }
        except Exception as exc:
            logger.error("risk_transactions_failed", error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get risk transactions: {exc}")

# =============================================================================
# INVOICE ENDPOINTS
# =============================================================================

@app.post("/invoices/create", response_model=InvoiceResponse, tags=["Invoicing"])
@limiter.limit("10/minute")
async def create_invoice(request: Request, data: CreateInvoiceRequest) -> dict[str, Any]:
    with tracer.start_as_current_span("create_invoice") as span:
        logger.info("create_invoice_called", client_email=data.client_email)
        try:
            token = paypal_client.get_access_token()
            if not token:
                raise HTTPException(status_code=500, detail="PayPal authentication failed")

            items = [item.model_dump() for item in data.items]
            invoice = invoice_manager.create_invoice(
                token=token,
                merchant_email=data.merchant_email,
                client_email=data.client_email,
                client_name=data.client_name,
                items=items,
                note=data.note or "",
                payment_terms=data.payment_terms,
            )
            if not invoice:
                raise HTTPException(status_code=500, detail="Failed to create invoice")

            invoice_id = invoice.get("id")
            sent = invoice_manager.send_invoice(token, invoice_id)
            span.set_attribute("invoice_id", invoice_id)
            span.set_attribute("sent", sent)

            return {
                "success": True,
                "invoice_id": invoice_id,
                "invoice_number": invoice.get("invoice_number"),
                "status": invoice.get("status"),
                "message": "Invoice created and sent successfully" if sent else "Invoice created but failed to send",
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("create_invoice_failed", error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create invoice: {exc}")


@app.get("/invoices", tags=["Invoicing"])
@limiter.limit("30/minute")
async def list_invoices(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    logger.info("list_invoices_called", page=page, page_size=page_size)
    try:
        token = paypal_client.get_access_token()
        if not token:
            raise HTTPException(status_code=500, detail="PayPal authentication failed")
        result = invoice_manager.list_invoices(token, page, page_size)
        return result or {"invoices": [], "total_pages": 0, "total_items": 0}
    except Exception as exc:
        logger.error("list_invoices_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list invoices: {exc}")

# =============================================================================
# DISPUTE ENDPOINTS
# =============================================================================

@app.get("/disputes", tags=["Disputes"])
@limiter.limit("30/minute")
async def list_disputes(
    request: Request, page_size: int = Query(10, ge=1, le=50)
) -> dict[str, Any]:
    logger.info("list_disputes_called", page_size=page_size)
    try:
        token = paypal_client.get_access_token()
        if not token:
            raise HTTPException(status_code=500, detail="PayPal authentication failed")
        result = dispute_manager.list_disputes(token, page_size)
        return result or {"disputes": [], "total_items": 0}
    except Exception as exc:
        logger.error("list_disputes_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list disputes: {exc}")


@app.get("/disputes/{dispute_id}/generate-response", tags=["Disputes"])
@limiter.limit("5/minute")
async def generate_dispute_response(request: Request, dispute_id: str) -> dict[str, Any]:
    with tracer.start_as_current_span("generate_dispute_response") as span:
        logger.info("generate_dispute_response_called", dispute_id=dispute_id)
        try:
            token = paypal_client.get_access_token()
            if not token:
                raise HTTPException(status_code=500, detail="PayPal authentication failed")
            dispute = dispute_manager.get_dispute(token, dispute_id)
            if not dispute:
                raise HTTPException(status_code=404, detail="Dispute not found")
            ai_response = dispute_manager.generate_dispute_response(dispute)
            span.set_attribute("dispute_id", dispute_id)
            return {
                "dispute_id": dispute_id,
                "dispute_details": dispute,
                "ai_response": ai_response,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("generate_dispute_response_failed", dispute_id=dispute_id, error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to generate response: {exc}")

# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 PayFlow AI Financial API v4.1.0")
    print("=" * 60)
    print("📖 Docs:    http://localhost:8000/docs")
    print("📚 ReDoc:   http://localhost:8000/redoc")
    print("📊 Metrics: http://localhost:8000/metrics")
    print("=" * 60)
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, log_level="info")