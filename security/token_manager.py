"""
PayPal OAuth Token Manager
==========================

Manages the complete lifecycle of PayPal OAuth 2.0 tokens with:
- Intelligent caching to minimize API calls
- Thread-safe token refresh with race condition protection
- Automatic refresh before expiration (with configurable buffer)
- Comprehensive error handling and retry logic
- Full observability integration (logging + metrics)
- Configurable via environment variables

Version: 2.0.0
"""

import time
import base64
import threading
import requests
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from observability import logging as obs_logging, metrics

load_dotenv()
logger = obs_logging.get_logger("token-manager")

# ==========================================
# CONFIGURATION
# ==========================================
PAYPAL_BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
TOKEN_REFRESH_BUFFER_SECONDS = int(os.getenv("TOKEN_REFRESH_BUFFER_SECONDS", "300"))  # 5 minutes
MAX_RETRY_ATTEMPTS = int(os.getenv("TOKEN_MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = float(os.getenv("TOKEN_RETRY_DELAY", "1.0"))


# ==========================================
# TOKEN MANAGER CLASS
# ==========================================

class PayPalTokenManager:
    """
    Thread-safe OAuth 2.0 token manager for PayPal API.
    
    Features:
    - Caches tokens to avoid unnecessary auth calls
    - Refreshes tokens before they expire (with configurable buffer)
    - Thread-safe with lock protection against race conditions
    - Retry logic for transient failures
    - Full observability integration
    """
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        secret: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initializes the token manager.
        
        Args:
            client_id: PayPal Client ID (defaults to env var)
            secret: PayPal Secret (defaults to env var)
            base_url: PayPal API base URL (defaults to env var)
        """
        self.client_id = client_id or os.getenv("PAYPAL_CLIENT_ID")
        self.secret = secret or os.getenv("PAYPAL_SECRET")
        self.base_url = base_url or PAYPAL_BASE_URL
        
        # Validate credentials
        if not self.client_id or not self.secret:
            logger.error(
                "missing_credentials",
                client_id_present=bool(self.client_id),
                secret_present=bool(self.secret)
            )
            raise ValueError(
                "PayPal credentials not configured. "
                "Set PAYPAL_CLIENT_ID and PAYPAL_SECRET in .env file."
            )
        
        # Token cache
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._token_type: str = "Bearer"
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self._total_requests = 0
        self._cache_hits = 0
        self._refreshes = 0
        
        logger.info(
            "token_manager_initialized",
            base_url=self.base_url,
            refresh_buffer_seconds=TOKEN_REFRESH_BUFFER_SECONDS
        )
    
    def get_token(self) -> str:
        """
        Returns a valid access token, refreshing if needed.
        Thread-safe and includes retry logic.
        
        Returns:
            str: Valid access token
            
        Raises:
            Exception: If token refresh fails after all retries
        """
        with self._lock:
            self._total_requests += 1
            
            # Check if we have a valid cached token
            if self._is_token_valid():
                self._cache_hits += 1
                logger.debug(
                    "token_cache_hit",
                    expires_in_seconds=round(self._expires_at - time.time(), 1)
                )
                return self._token
            
            # Token is invalid or expired, refresh it
            return self._refresh_token_with_retry()
    
    def _is_token_valid(self) -> bool:
        """
        Checks if the current token is still valid.
        Includes a buffer to refresh before actual expiration.
        
        Returns:
            bool: True if token is valid, False otherwise
        """
        if not self._token:
            return False
        
        # Check if token expires within the buffer period
        time_until_expiry = self._expires_at - time.time()
        return time_until_expiry > TOKEN_REFRESH_BUFFER_SECONDS
    
    def _refresh_token_with_retry(self) -> str:
        """
        Refreshes the token with retry logic for transient failures.
        
        Returns:
            str: Fresh access token
            
        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                logger.info(
                    "refreshing_token",
                    attempt=attempt,
                    max_attempts=MAX_RETRY_ATTEMPTS
                )
                
                start_time = time.time()
                token_data = self._fetch_new_token()
                duration = time.time() - start_time
                
                # Update cache
                self._token = token_data['access_token']
                self._expires_at = time.time() + token_data.get('expires_in', 32400)
                self._token_type = token_data.get('token_type', 'Bearer')
                self._refreshes += 1
                
                # Record metrics
                metrics.record_paypal_api_call(
                    endpoint="/v1/oauth2/token",
                    status="success",
                    duration=duration
                )
                
                logger.info(
                    "token_refreshed",
                    expires_in=token_data.get('expires_in'),
                    token_type=self._token_type,
                    duration=f"{duration:.3f}s"
                )
                
                return self._token
                
            except Exception as e:
                last_exception = e
                logger.warning(
                    "token_refresh_failed",
                    attempt=attempt,
                    error=str(e)
                )
                
                # Record error metric
                metrics.record_error(
                    error_type="token_refresh",
                    component="token_manager"
                )
                
                # Wait before retry (exponential backoff)
                if attempt < MAX_RETRY_ATTEMPTS:
                    delay = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.info("retrying_after_delay", delay_seconds=delay)
                    time.sleep(delay)
        
        # All retries failed
        logger.error(
            "token_refresh_exhausted",
            attempts=MAX_RETRY_ATTEMPTS,
            last_error=str(last_exception)
        )
        raise Exception(
            f"Failed to refresh PayPal token after {MAX_RETRY_ATTEMPTS} attempts: {last_exception}"
        )
    
    def _fetch_new_token(self) -> Dict[str, Any]:
        """
        Makes the actual HTTP request to PayPal to get a new token.
        
        Returns:
            Dict containing access_token, expires_in, token_type
            
        Raises:
            Exception: If the request fails or returns invalid data
        """
        url = f"{self.base_url}/v1/oauth2/token"
        
        # PayPal requires Basic Auth: base64 encode "client_id:secret"
        auth_str = f"{self.client_id}:{self.secret}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {b64_auth}"
        }
        
        data = "grant_type=client_credentials"
        
        try:
            response = requests.post(
                url,
                headers=headers,
                data=data,
                timeout=10
            )
            
            # Check HTTP status
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error("token_request_failed", status_code=response.status_code)
                raise Exception(f"PayPal token request failed: {error_msg}")
            
            # Parse response
            try:
                token_data = response.json()
            except ValueError as e:
                logger.error("token_response_parse_failed", error=str(e))
                raise Exception(f"Failed to parse PayPal token response: {e}")
            
            # Validate required fields
            if 'access_token' not in token_data:
                logger.error("token_response_missing_access_token")
                raise Exception("PayPal token response missing 'access_token' field")
            
            return token_data
            
        except requests.exceptions.Timeout:
            logger.error("token_request_timeout")
            raise Exception("PayPal token request timed out")
        except requests.exceptions.ConnectionError as e:
            logger.error("token_request_connection_error", error=str(e))
            raise Exception(f"Failed to connect to PayPal: {e}")
        except requests.exceptions.RequestException as e:
            logger.error("token_request_error", error=str(e))
            raise Exception(f"PayPal token request failed: {e}")
    
    def invalidate_token(self) -> None:
        """
        Manually invalidates the cached token.
        Useful for testing or when you know the token is compromised.
        """
        with self._lock:
            if self._token:
                logger.info("token_manually_invalidated")
                self._token = None
                self._expires_at = 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Returns token manager statistics for monitoring.
        
        Returns:
            Dict with cache hit rate, refresh count, etc.
        """
        with self._lock:
            cache_hit_rate = (
                (self._cache_hits / self._total_requests * 100)
                if self._total_requests > 0 else 0.0
            )
            
            return {
                "total_requests": self._total_requests,
                "cache_hits": self._cache_hits,
                "cache_hit_rate": f"{cache_hit_rate:.1f}%",
                "refreshes": self._refreshes,
                "token_valid": self._is_token_valid(),
                "expires_in_seconds": round(self._expires_at - time.time(), 1) if self._token else None
            }
    
    def __repr__(self) -> str:
        return (
            f"PayPalTokenManager("
            f"base_url='{self.base_url}', "
            f"token_valid={self._is_token_valid()}, "
            f"refreshes={self._refreshes})"
        )


# ==========================================
# MODULE-LEVEL CONVENIENCE
# ==========================================

# Global instance for easy import (singleton pattern)
_default_manager: Optional[PayPalTokenManager] = None
_default_manager_lock = threading.Lock()


def get_default_token_manager() -> PayPalTokenManager:
    """
    Returns the default global token manager instance.
    Thread-safe singleton initialization.
    
    Returns:
        PayPalTokenManager instance
    """
    global _default_manager
    
    if _default_manager is None:
        with _default_manager_lock:
            # Double-check locking pattern
            if _default_manager is None:
                _default_manager = PayPalTokenManager()
    
    return _default_manager


def get_token() -> str:
    """
    Convenience function to get a token from the default manager.
    
    Returns:
        str: Valid access token
    """
    return get_default_token_manager().get_token()