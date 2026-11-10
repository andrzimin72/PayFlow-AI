"""
Structured Logging Module
=========================

Provides JSON-formatted, context-rich logging for the entire application.
Uses structlog for structured, machine-parseable logs that integrate with
modern log aggregation systems (ELK, Datadog, CloudWatch, etc.).

Features:
- JSON-formatted logs for easy parsing
- Automatic timestamp and log level injection
- Context variable support for request tracing
- Environment-aware configuration (dev vs prod)
- Thread-safe and performant

Version: 2.0.0
"""

import logging
import sys
import os
from typing import Optional
import structlog
from structlog.types import Processor

# ==========================================
# CONFIGURATION
# ==========================================

# Determine environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT in ["production", "prod", "staging"]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Track initialization state
_initialized = False


# ==========================================
# CUSTOM PROCESSORS
# ==========================================

def add_service_info(
    logger: logging.Logger, 
    method_name: str, 
    event_dict: dict
) -> dict:
    """
    Adds service metadata to every log entry.
    Useful for multi-service environments.
    """
    event_dict["service"] = "payflow-ai"
    event_dict["version"] = "4.0.0"
    event_dict["environment"] = ENVIRONMENT
    return event_dict


def mask_sensitive_data(
    logger: logging.Logger, 
    method_name: str, 
    event_dict: dict
) -> dict:
    """
    Masks sensitive fields like tokens, secrets, and credentials.
    Prevents accidental leakage in logs.
    """
    sensitive_keys = [
        "password", "secret", "token", "api_key", 
        "authorization", "credit_card", "ssn"
    ]
    
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            event_dict[key] = "***MASKED***"
    
    return event_dict


# ==========================================
# INITIALIZATION
# ==========================================

def setup_logging(level: Optional[str] = None) -> None:
    """
    Configures structured JSON logging for the application.
    
    Args:
        level: Optional log level override (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    global _initialized
    
    if _initialized:
        return
    
    # Determine log level
    log_level = level or LOG_LEVEL
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_service_info,
        mask_sensitive_data,
    ]
    
    # Choose renderer based on environment
    if IS_PRODUCTION:
        # Production: JSON for log aggregation
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development: Pretty console output for readability
        processors.append(structlog.dev.ConsoleRenderer(
            colors=True,
            exception_local_variables=True
        ))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        stream=sys.stdout,
        force=True
    )
    
    # Suppress noisy third-party loggers
    for noisy_logger in ["urllib3", "elasticsearch", "prophet", "transformers"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    
    _initialized = True
    
    # Log initialization
    logger = get_logger("observability.logging")
    logger.info(
        "logging_initialized",
        level=log_level,
        environment=ENVIRONMENT,
        is_production=IS_PRODUCTION
    )


# ==========================================
# LOGGER FACTORY
# ==========================================

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Returns a structured logger bound to a specific name.
    
    Args:
        name: Logger name (typically module name like "paypal-client")
    
    Returns:
        Bound logger instance with structured logging capabilities
    
    Example:
        logger = get_logger("my-module")
        logger.info("operation_started", user_id=123, action="fetch")
    """
    if not _initialized:
        setup_logging()
    
    return structlog.get_logger(name)


# ==========================================
# CONTEXT MANAGEMENT
# ==========================================

def bind_context(**kwargs) -> None:
    """
    Binds context variables that will be included in all subsequent log entries.
    Useful for request-scoped context like user ID, request ID, etc.
    
    Args:
        **kwargs: Key-value pairs to bind to the context
    
    Example:
        bind_context(user_id=123, request_id="abc-xyz")
        # All subsequent logs will include user_id and request_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """
    Clears all bound context variables.
    Should be called at the end of request handling to prevent context leakage.
    """
    structlog.contextvars.clear_contextvars()


def unbind_context(*keys: str) -> None:
    """
    Removes specific keys from the bound context.
    
    Args:
        *keys: Keys to remove from context
    """
    structlog.contextvars.unbind_contextvars(*keys)


# ==========================================
# CONVENIENCE FUNCTIONS
# ==========================================

def log_exception(
    logger: structlog.stdlib.BoundLogger,
    message: str,
    exc_info: bool = True,
    **kwargs
) -> None:
    """
    Logs an exception with full context and stack trace.
    
    Args:
        logger: Logger instance
        message: Error message
        exc_info: Whether to include exception info
        **kwargs: Additional context
    """
    logger.error(
        message,
        exc_info=exc_info,
        **kwargs
    )


def log_timing(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    duration_seconds: float,
    **kwargs
) -> None:
    """
    Logs the duration of an operation.
    
    Args:
        logger: Logger instance
        operation: Name of the operation
        duration_seconds: Duration in seconds
        **kwargs: Additional context
    """
    logger.info(
        "operation_completed",
        operation=operation,
        duration_seconds=round(duration_seconds, 3),
        duration_ms=round(duration_seconds * 1000, 1),
        **kwargs
    )