"""
Observability Package for PayFlow AI
====================================

Provides comprehensive monitoring and observability capabilities:
- Structured JSON logging with context variables
- Prometheus metrics collection and exposure
- OpenTelemetry distributed tracing
- Environment-aware configuration (dev vs prod)

This package enables full-stack visibility into the PayFlow AI platform,
from individual API requests to AI model inference performance.

Example Usage:
    from observability import logging, metrics, tracing
    
    # Structured logging
    logger = logging.get_logger("my-module")
    logger.info("operation_started", user_id=123)
    
    # Record metrics
    metrics.record_request("GET", "/api/data", 200, 0.123)
    
    # Distributed tracing
    tracer = tracing.get_tracer("my-module")
    with tracer.start_as_current_span("operation") as span:
        span.set_attribute("key", "value")
"""

# Import submodules for convenient access
from observability import logging
from observability import metrics
from observability import tracing

# Package metadata
__version__ = "2.0.0"
__author__ = "Andre Zimin"
__license__ = "Apache-2.0"

# Public API
__all__ = [
    "logging",
    "metrics",
    "tracing",
    "__version__",
    "__author__",
    "__license__",
]
