"""
Prometheus Metrics Module
=========================

Defines and manages all Prometheus metrics for monitoring application health,
performance, and business KPIs.

Features:
- Request counting and latency tracking
- AI inference metrics (timing, categorization counts)
- Elasticsearch query performance
- Business metrics (transaction counts, anomaly rates)
- Thread-safe metric operations
- Easy-to-use helper functions

Version: 2.0.0
"""

from typing import Optional
from prometheus_client import (
    Counter, 
    Histogram, 
    Gauge, 
    Summary,
    generate_latest, 
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    REGISTRY
)

# ==========================================
# REQUEST METRICS
# ==========================================

REQUEST_COUNT = Counter(
    'payflow_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code', 'service']
)

REQUEST_LATENCY = Histogram(
    'payflow_request_duration_seconds',
    'Request latency in seconds',
    ['method', 'endpoint', 'service'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

REQUESTS_IN_PROGRESS = Gauge(
    'payflow_requests_in_progress',
    'Number of requests currently being processed',
    ['method', 'endpoint', 'service']
)

# ==========================================
# AI METRICS
# ==========================================

AI_CATEGORIZATION_COUNT = Counter(
    'payflow_ai_categorizations_total',
    'Total number of AI categorizations performed',
    ['category', 'service']
)

AI_INFERENCE_TIME = Histogram(
    'payflow_ai_inference_seconds',
    'Time taken for AI model inference in seconds',
    ['model', 'service'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
)

AI_CONFIDENCE_SCORES = Histogram(
    'payflow_ai_confidence_scores',
    'Distribution of AI confidence scores',
    ['category', 'service'],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)

AI_MODEL_LOADED = Gauge(
    'payflow_ai_model_loaded',
    'Whether the AI model is loaded in memory (1 = yes, 0 = no)',
    ['model', 'service']
)

# ==========================================
# ELASTICSEARCH METRICS
# ==========================================

ELASTICSEARCH_QUERY_TIME = Histogram(
    'payflow_elasticsearch_query_seconds',
    'Time taken for Elasticsearch queries in seconds',
    ['operation', 'service'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)

ELASTICSEARCH_QUERY_COUNT = Counter(
    'payflow_elasticsearch_queries_total',
    'Total number of Elasticsearch queries',
    ['operation', 'status', 'service']
)

# ==========================================
# PAYPAL API METRICS
# ==========================================

PAYPAL_API_CALLS = Counter(
    'payflow_paypal_api_calls_total',
    'Total number of PayPal API calls',
    ['endpoint', 'status', 'service']
)

PAYPAL_API_LATENCY = Histogram(
    'payflow_paypal_api_latency_seconds',
    'Latency of PayPal API calls in seconds',
    ['endpoint', 'service'],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# ==========================================
# WEBHOOK METRICS
# ==========================================

WEBHOOK_RECEIVED_COUNT = Counter(
    'payflow_webhooks_total',
    'Total webhooks received from PayPal',
    ['verified', 'event_type', 'service']
)

WEBHOOK_PROCESSING_TIME = Histogram(
    'payflow_webhook_processing_seconds',
    'Time taken to process webhooks in seconds',
    ['event_type', 'service'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)

# ==========================================
# BUSINESS METRICS
# ==========================================

ACTIVE_TRANSACTIONS = Gauge(
    'payflow_transactions_in_elastic',
    'Number of transactions currently stored in Elasticsearch',
    ['service']
)

ANOMALY_DETECTED_COUNT = Counter(
    'payflow_anomalies_total',
    'Total anomalies detected by Isolation Forest',
    ['service']
)

RISK_SCORE_DISTRIBUTION = Histogram(
    'payflow_risk_scores',
    'Distribution of calculated risk scores',
    ['service'],
    buckets=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
)

PORTFOLIO_RISK_SCORE = Gauge(
    'payflow_portfolio_risk_score',
    'Current portfolio-level risk score (0-100)',
    ['service']
)

INVOICE_COUNT = Counter(
    'payflow_invoices_total',
    'Total invoices created',
    ['status', 'service']
)

DISPUTE_COUNT = Counter(
    'payflow_disputes_total',
    'Total disputes handled',
    ['status', 'service']
)

# ==========================================
# ERROR METRICS
# ==========================================

ERROR_COUNT = Counter(
    'payflow_errors_total',
    'Total number of errors by type',
    ['error_type', 'component', 'service']
)

# ==========================================
# HELPER FUNCTIONS
# ==========================================

# Default service name
DEFAULT_SERVICE = "payflow-api"


def record_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration: float,
    service: str = DEFAULT_SERVICE
) -> None:
    """
    Records a complete request with latency and status.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Request endpoint path
        status_code: HTTP status code
        duration: Request duration in seconds
        service: Service name (default: payflow-api)
    """
    REQUEST_COUNT.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
        service=service
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=method,
        endpoint=endpoint,
        service=service
    ).observe(duration)


def record_ai_categorization(
    category: str,
    confidence: Optional[float] = None,
    service: str = DEFAULT_SERVICE
) -> None:
    """
    Records an AI categorization event.
    
    Args:
        category: Predicted category
        confidence: Optional confidence score (0.0 to 1.0)
        service: Service name
    """
    AI_CATEGORIZATION_COUNT.labels(
        category=category,
        service=service
    ).inc()
    
    if confidence is not None:
        AI_CONFIDENCE_SCORES.labels(
            category=category,
            service=service
        ).observe(confidence)


def record_ai_inference(
    duration: float,
    model: str = "bart-large-mnli",
    service: str = DEFAULT_SERVICE
) -> None:
    """
    Records AI inference time.
    
    Args:
        duration: Inference duration in seconds
        model: Model name
        service: Service name
    """
    AI_INFERENCE_TIME.labels(
        model=model,
        service=service
    ).observe(duration)


def record_elasticsearch_query(
    duration: float,
    operation: str = "search",
    status: str = "success",
    service: str = DEFAULT_SERVICE
) -> None:
    """
    Records Elasticsearch query performance.
    
    Args:
        duration: Query duration in seconds
        operation: Type of operation (search, index, etc.)
        status: Query status (success, error)
        service: Service name
    """
    ELASTICSEARCH_QUERY_TIME.labels(
        operation=operation,
        service=service
    ).observe(duration)
    
    ELASTICSEARCH_QUERY_COUNT.labels(
        operation=operation,
        status=status,
        service=service
    ).inc()


def record_webhook(
    verified: bool,
    event_type: str,
    processing_time: Optional[float] = None,
    service: str = DEFAULT_SERVICE
) -> None:
    """
    Records a webhook event.
    
    Args:
        verified: Whether the webhook signature was verified
        event_type: Type of webhook event
        processing_time: Optional processing time in seconds
        service: Service name
    """
    WEBHOOK_RECEIVED_COUNT.labels(
        verified=str(verified).lower(),
        event_type=event_type,
        service=service
    ).inc()
    
    if processing_time is not None:
        WEBHOOK_PROCESSING_TIME.labels(
            event_type=event_type,
            service=service
        ).observe(processing_time)


def record_anomaly(service: str = DEFAULT_SERVICE) -> None:
    """Records that an anomaly was detected."""
    ANOMALY_DETECTED_COUNT.labels(service=service).inc()


def record_risk_score(score: float, service: str = DEFAULT_SERVICE) -> None:
    """
    Records a risk score for distribution tracking.
    
    Args:
        score: Risk score (0-100)
        service: Service name
    """
    RISK_SCORE_DISTRIBUTION.labels(service=service).observe(score)


def record_error(
    error_type: str,
    component: str,
    service: str = DEFAULT_SERVICE
) -> None:
    """
    Records an error event.
    
    Args:
        error_type: Type of error (e.g., "timeout", "validation", "auth")
        component: Component where error occurred
        service: Service name
    """
    ERROR_COUNT.labels(
        error_type=error_type,
        component=component,
        service=service
    ).inc()


def set_transaction_count(count: int, service: str = DEFAULT_SERVICE) -> None:
    """Updates the active transaction count gauge."""
    ACTIVE_TRANSACTIONS.labels(service=service).set(count)


def set_model_loaded(
    loaded: bool,
    model: str = "bart-large-mnli",
    service: str = DEFAULT_SERVICE
) -> None:
    """Updates the AI model loaded gauge."""
    AI_MODEL_LOADED.labels(model=model, service=service).set(1 if loaded else 0)


def set_portfolio_risk_score(score: float, service: str = DEFAULT_SERVICE) -> None:
    """Updates the portfolio risk score gauge."""
    PORTFOLIO_RISK_SCORE.labels(service=service).set(score)


def record_invoice(status: str, service: str = DEFAULT_SERVICE) -> None:
    """Records an invoice creation event."""
    INVOICE_COUNT.labels(status=status, service=service).inc()


def record_dispute(status: str, service: str = DEFAULT_SERVICE) -> None:
    """Records a dispute handling event."""
    DISPUTE_COUNT.labels(status=status, service=service).inc()


def record_paypal_api_call(
    endpoint: str,
    status: str,
    duration: float,
    service: str = DEFAULT_SERVICE
) -> None:
    """
    Records a PayPal API call.
    
    Args:
        endpoint: API endpoint called
        status: Call status (success, error)
        duration: Call duration in seconds
        service: Service name
    """
    PAYPAL_API_CALLS.labels(
        endpoint=endpoint,
        status=status,
        service=service
    ).inc()
    
    PAYPAL_API_LATENCY.labels(
        endpoint=endpoint,
        service=service
    ).observe(duration)


def get_metrics_output() -> tuple[str, str]:
    """
    Returns the current metrics in Prometheus format.
    
    Returns:
        Tuple of (metrics_content, content_type)
    """
    return generate_latest(REGISTRY).decode('utf-8'), CONTENT_TYPE_LATEST