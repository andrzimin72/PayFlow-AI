"""
Distributed Tracing Module
==========================

Uses OpenTelemetry to trace requests across the entire system, providing
end-to-end visibility into request flows, latency bottlenecks, and errors.

Features:
- Automatic FastAPI instrumentation
- Automatic requests library instrumentation
- Environment-aware exporters (console for dev, OTLP for prod)
- Custom span creation helpers
- Resource attributes for service identification
- Thread-safe tracing operations

Version: 2.0.0
"""

import os
from typing import Optional
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# ==========================================
# CONFIGURATION
# ==========================================

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT in ["production", "prod", "staging"]

# Service metadata
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "payflow-api")
SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "4.0.0")

# OTLP exporter configuration (for production)
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

# Track initialization state
_initialized = False
_tracer_provider: Optional[TracerProvider] = None


# ==========================================
# INITIALIZATION
# ==========================================

def setup_tracing(
    app: Optional[FastAPI] = None,
    service_name: Optional[str] = None,
    enable_console_export: bool = True
) -> TracerProvider:
    """
    Sets up OpenTelemetry tracing for the application.
    
    Args:
        app: Optional FastAPI app to instrument
        service_name: Optional service name override
        enable_console_export: Whether to export spans to console (dev mode)
    
    Returns:
        Configured TracerProvider instance
    """
    global _initialized, _tracer_provider
    
    if _initialized:
        return _tracer_provider
    
    # Determine service name
    svc_name = service_name or SERVICE_NAME
    
    # Create a resource that identifies this service
    resource = Resource.create({
        "service.name": svc_name,
        "service.version": SERVICE_VERSION,
        "deployment.environment": ENVIRONMENT,
        "telemetry.sdk.language": "python",
        "telemetry.sdk.name": "opentelemetry",
    })
    
    # Set up the tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure exporters based on environment
    if IS_PRODUCTION:
        # Production: Export to OTLP collector (Jaeger, Zipkin, etc.)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            
            otlp_exporter = OTLPSpanExporter(
                endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
                insecure=True  # Set to False in production with TLS
            )
            
            provider.add_span_processor(
                BatchSpanProcessor(
                    otlp_exporter,
                    max_queue_size=2048,
                    schedule_delay_millis=5000,
                    max_export_batch_size=512,
                )
            )
            
            print(f"✅ OpenTelemetry OTLP exporter configured: {OTEL_EXPORTER_OTLP_ENDPOINT}")
            
        except ImportError:
            print("⚠️ OTLP exporter not available, falling back to console")
            provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )
    else:
        # Development: Export to console for visibility
        if enable_console_export:
            provider.add_span_processor(
                SimpleSpanProcessor(ConsoleSpanExporter())
            )
    
    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    
    # Auto-instrument FastAPI (tracks all HTTP requests)
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
        print(f"✅ FastAPI auto-instrumented for tracing")
    
    # Auto-instrument requests library (tracks outgoing HTTP calls)
    RequestsInstrumentor().instrument()
    print(f"✅ Requests library auto-instrumented for tracing")
    
    _initialized = True
    
    print(f"✅ OpenTelemetry tracing initialized for {svc_name} ({ENVIRONMENT})")
    
    return provider


def shutdown_tracing() -> None:
    """
    Gracefully shuts down the tracer provider.
    Should be called on application shutdown to flush pending spans.
    """
    global _tracer_provider
    
    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
            print("✅ OpenTelemetry tracing shut down")
        except Exception as e:
            print(f"⚠️ Error shutting down tracer: {e}")


# ==========================================
# TRACER ACCESS
# ==========================================

def get_tracer(name: Optional[str] = None) -> trace.Tracer:
    """
    Returns a tracer for creating custom spans.
    
    Args:
        name: Optional tracer name (defaults to service name)
    
    Returns:
        OpenTelemetry Tracer instance
    
    Example:
        tracer = get_tracer("my-module")
        with tracer.start_as_current_span("my-operation") as span:
            span.set_attribute("key", "value")
            # ... do work ...
    """
    if not _initialized:
        setup_tracing()
    
    tracer_name = name or SERVICE_NAME
    return trace.get_tracer(tracer_name)


# ==========================================
# SPAN HELPERS
# ==========================================

def start_span(
    name: str,
    tracer_name: Optional[str] = None,
    attributes: Optional[dict] = None
) -> Span:
    """
    Starts a new span with optional attributes.
    
    Args:
        name: Span name
        tracer_name: Optional tracer name
        attributes: Optional initial attributes
    
    Returns:
        Started Span instance
    
    Example:
        span = start_span("process-transaction", attributes={"tx_id": "123"})
        # ... do work ...
        span.end()
    """
    tracer = get_tracer(tracer_name)
    span = tracer.start_span(name)
    
    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)
    
    return span


def record_exception_on_span(
    span: Span,
    exception: Exception,
    status_code: StatusCode = StatusCode.ERROR
) -> None:
    """
    Records an exception on a span and sets error status.
    
    Args:
        span: Span to record exception on
        exception: Exception instance
        status_code: Status code (default: ERROR)
    """
    span.record_exception(exception)
    span.set_status(Status(status_code, str(exception)))


def set_span_attributes(span: Span, attributes: dict) -> None:
    """
    Sets multiple attributes on a span.
    
    Args:
        span: Span to update
        attributes: Dictionary of attributes
    """
    for key, value in attributes.items():
        span.set_attribute(key, value)


# ==========================================
# CONTEXT MANAGERS
# ==========================================

class TracedOperation:
    """
    Context manager for tracing operations with automatic error handling.
    
    Example:
        with TracedOperation("process-payment", {"amount": 100}) as span:
            # ... do work ...
            span.set_attribute("result", "success")
    """
    
    def __init__(
        self,
        operation_name: str,
        attributes: Optional[dict] = None,
        tracer_name: Optional[str] = None
    ):
        self.operation_name = operation_name
        self.attributes = attributes or {}
        self.tracer_name = tracer_name
        self.span: Optional[Span] = None
        self.tracer = get_tracer(tracer_name)
    
    def __enter__(self) -> Span:
        self.span = self.tracer.start_span(self.operation_name)
        
        # Set initial attributes
        for key, value in self.attributes.items():
            self.span.set_attribute(key, value)
        
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.span is None:
            return
        
        if exc_type is not None:
            # An exception occurred
            self.span.record_exception(exc_val)
            self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))
        else:
            # Success
            self.span.set_status(Status(StatusCode.OK))
        
        self.span.end()


# ==========================================
# DECORATORS
# ==========================================

def traced(operation_name: Optional[str] = None):
    """
    Decorator for automatically tracing function calls.
    
    Args:
        operation_name: Optional operation name (defaults to function name)
    
    Example:
        @traced("process-transaction")
        def process_transaction(tx_id: str):
            # ... do work ...
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            tracer = get_tracer(func.__module__)
            
            with tracer.start_as_current_span(op_name) as span:
                # Add function metadata
                span.set_attribute("code.function", func.__name__)
                span.set_attribute("code.module", func.__module__)
                
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        
        return wrapper
    
    return decorator