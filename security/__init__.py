"""
Security Package for PayFlow AI
===============================

Provides enterprise-grade security components for:
- OAuth 2.0 token lifecycle management with intelligent caching
- Cryptographic webhook signature verification
- Protection against replay attacks and credential leakage

This package is the security foundation of the PayFlow AI platform,
ensuring all external communications are authenticated and verified.

Example Usage:
    from security import PayPalTokenManager, PayPalWebhookVerifier
    
    # Get a cached PayPal token
    manager = PayPalTokenManager()
    token = manager.get_token()
    
    # Verify a webhook signature
    verifier = PayPalWebhookVerifier(webhook_id="your_id")
    is_valid, message = verifier.verify(headers, body)
"""

from security.token_manager import (
    PayPalTokenManager,
    get_default_token_manager,
    get_token
)

from security.webhook_verifier import (
    PayPalWebhookVerifier,
    get_default_verifier,
    verify_webhook
)

# Package metadata
__version__ = "2.0.0"
__author__ = "Andre Zimin"
__license__ = "Apache-2.0"

# Public API - defines what gets imported with "from security import *"
__all__ = [
    # Classes
    "PayPalTokenManager",
    "PayPalWebhookVerifier",
    
    # Convenience functions
    "get_default_token_manager",
    "get_token",
    "get_default_verifier",
    "verify_webhook",
    
    # Metadata
    "__version__",
    "__author__",
    "__license__",
]
