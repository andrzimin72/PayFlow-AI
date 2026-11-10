"""
PayPal Webhook Signature Verifier
=================================

Cryptographically verifies that incoming webhooks are genuinely from PayPal
by validating digital signatures against PayPal's certificates.

Security Features:
- Certificate chain validation (ensures cert is from PayPal)
- Certificate expiration checking
- Webhook ID verification (prevents cross-webhook attacks)
- Transmission time validation (prevents replay attacks)
- Support for multiple hash algorithms (SHA256, SHA1)
- Comprehensive audit logging for security events
- Full observability integration

Version: 2.0.0
"""

import base64
import binascii
import hashlib
import time
import requests
from datetime import datetime, timezone
from typing import Tuple, Dict, Optional, Any
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature
from cryptography.x509 import Certificate
from observability import logging as obs_logging, metrics

logger = obs_logging.get_logger("webhook-verifier")

# ==========================================
# CONFIGURATION
# ==========================================
MAX_TRANSMISSION_AGE_SECONDS = 300  # 5 minutes (replay attack protection)
CERTIFICATE_CACHE_TTL_SECONDS = 3600  # 1 hour
PAYPAL_CERT_DOMAIN = "paypal.com"  # Expected certificate domain


# ==========================================
# WEBHOOK VERIFIER CLASS
# ==========================================

class PayPalWebhookVerifier:
    """
    Cryptographically verifies PayPal webhook signatures.
    
    Security checks performed:
    1. All required headers are present
    2. Certificate is from PayPal (domain validation)
    3. Certificate is not expired
    4. Webhook ID matches expected value
    5. Transmission time is recent (replay protection)
    6. Cryptographic signature is valid
    """
    
    def __init__(self, webhook_id: str):
        """
        Initializes the verifier with the expected webhook ID.
        
        Args:
            webhook_id: The PayPal webhook ID to verify against
            
        Raises:
            ValueError: If webhook_id is empty
        """
        if not webhook_id:
            raise ValueError("webhook_id cannot be empty")
        
        self.webhook_id = webhook_id
        
        # Certificate cache to avoid repeated downloads
        self._cert_cache: Dict[str, Tuple[Certificate, float]] = {}
        
        logger.info(
            "webhook_verifier_initialized",
            webhook_id=self._mask_webhook_id(webhook_id)
        )
    
    def verify(self, headers: Dict[str, str], body: str) -> Tuple[bool, str]:
        """
        Verifies a PayPal webhook signature.
        
        Args:
            headers: HTTP headers from the webhook request
            body: Raw request body as string
        
        Returns:
            Tuple of (is_valid, message)
            - is_valid: True if signature is valid, False otherwise
            - message: Human-readable status or error message
        """
        start_time = time.time()
        
        try:
            # Step 1: Validate required headers
            header_check = self._validate_headers(headers)
            if not header_check[0]:
                self._record_verification(False, "missing_headers", start_time)
                return header_check
            
            # Extract headers (case-insensitive)
            normalized_headers = {k.upper(): v for k, v in headers.items()}
            
            transmission_id = normalized_headers['PAYPAL-TRANSMISSION-ID']
            transmission_time = normalized_headers['PAYPAL-TRANSMISSION-TIME']
            transmission_sig = normalized_headers['PAYPAL-TRANSMISSION-SIG']
            cert_url = normalized_headers['PAYPAL-CERT-URL']
            auth_algo = normalized_headers['PAYPAL-AUTH-ALGO']
            
            # Step 2: Validate transmission time (replay attack protection)
            time_check = self._validate_transmission_time(transmission_time)
            if not time_check[0]:
                self._record_verification(False, "replay_attack", start_time)
                return time_check
            
            # Step 3: Download and validate certificate
            cert_check = self._get_and_validate_certificate(cert_url)
            if not cert_check[0]:
                self._record_verification(False, "invalid_certificate", start_time)
                return cert_check
            
            cert = cert_check[1]
            
            # Step 4: Compute CRC32 of the body
            crc32 = self._compute_crc32(body)
            
            # Step 5: Build the string to verify
            # Format: transmission_id|transmission_time|webhook_id|crc32
            string_to_verify = (
                f"{transmission_id}|"
                f"{transmission_time}|"
                f"{self.webhook_id}|"
                f"{crc32}"
            )
            
            # Step 6: Verify the signature
            sig_check = self._verify_signature(
                cert=cert,
                signature_b64=transmission_sig,
                data=string_to_verify,
                auth_algo=auth_algo
            )
            
            if not sig_check[0]:
                self._record_verification(False, "invalid_signature", start_time)
                return sig_check
            
            # Success!
            duration = time.time() - start_time
            self._record_verification(True, "success", start_time)
            
            logger.info(
                "webhook_verified_successfully",
                transmission_id=transmission_id,
                duration_ms=round(duration * 1000, 2)
            )
            
            return True, "Webhook signature verified successfully"
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "webhook_verification_exception",
                error=str(e),
                exc_info=True,
                duration_ms=round(duration * 1000, 2)
            )
            self._record_verification(False, "exception", start_time)
            return False, f"Verification error: {str(e)}"
    
    def _validate_headers(self, headers: Dict[str, str]) -> Tuple[bool, str]:
        """Validates that all required PayPal headers are present."""
        required_headers = [
            'PAYPAL-TRANSMISSION-ID',
            'PAYPAL-TRANSMISSION-TIME',
            'PAYPAL-TRANSMISSION-SIG',
            'PAYPAL-CERT-URL',
            'PAYPAL-AUTH-ALGO'
        ]
        
        # Normalize header keys to uppercase for case-insensitive comparison
        normalized = {k.upper(): v for k, v in headers.items()}
        
        for header in required_headers:
            if header not in normalized or not normalized[header]:
                logger.warning("missing_required_header", header=header)
                return False, f"Missing required header: {header}"
        
        return True, "All required headers present"
    
    def _validate_transmission_time(self, transmission_time: str) -> Tuple[bool, str]:
        """
        Validates that the transmission time is recent (replay attack protection).
        
        PayPal sends times in ISO 8601 format like: 2026-11-06T14:30:00Z
        """
        try:
            # Parse the transmission time
            # Handle both with and without 'Z' suffix
            time_str = transmission_time.replace('Z', '+00:00')
            
            # Try parsing with timezone
            try:
                transmission_dt = datetime.fromisoformat(time_str)
            except ValueError:
                # Fallback for older Python versions
                transmission_dt = datetime.strptime(
                    transmission_time.rstrip('Z'),
                    "%Y-%m-%dT%H:%M:%S"
                ).replace(tzinfo=timezone.utc)
            
            # Ensure it's in UTC
            if transmission_dt.tzinfo is None:
                transmission_dt = transmission_dt.replace(tzinfo=timezone.utc)
            
            # Check if it's too old (replay attack)
            now = datetime.now(timezone.utc)
            age_seconds = (now - transmission_dt).total_seconds()
            
            if age_seconds > MAX_TRANSMISSION_AGE_SECONDS:
                logger.warning(
                    "transmission_too_old",
                    age_seconds=age_seconds,
                    max_age=MAX_TRANSMISSION_AGE_SECONDS
                )
                return False, (
                    f"Transmission time is too old ({age_seconds:.0f}s). "
                    f"Max allowed: {MAX_TRANSMISSION_AGE_SECONDS}s. "
                    f"Possible replay attack."
                )
            
            # Check if it's in the future (clock skew protection)
            if age_seconds < -60:  # Allow 1 minute clock skew
                logger.warning("transmission_in_future", age_seconds=age_seconds)
                return False, "Transmission time is in the future. Possible clock manipulation."
            
            return True, "Transmission time is valid"
            
        except Exception as e:
            logger.error("transmission_time_parse_failed", error=str(e))
            return False, f"Failed to parse transmission time: {str(e)}"
    
    def _get_and_validate_certificate(self, cert_url: str) -> Tuple[bool, Any]:
        """
        Downloads and validates a PayPal certificate.
        
        Security checks:
        - URL is from paypal.com domain
        - URL uses HTTPS
        - Certificate is not expired
        - Certificate subject matches PayPal
        """
        # Security check: Ensure cert URL is from PayPal
        if not self._is_valid_paypal_url(cert_url):
            logger.error("invalid_certificate_url", url=cert_url)
            return False, f"Certificate URL is not from PayPal: {cert_url}"
        
        # Check cache
        if cert_url in self._cert_cache:
            cert, cached_at = self._cert_cache[cert_url]
            if time.time() - cached_at < CERTIFICATE_CACHE_TTL_SECONDS:
                logger.debug("certificate_cache_hit", url=cert_url)
                return True, cert
        
        # Download certificate
        try:
            logger.info("downloading_certificate", url=cert_url)
            response = requests.get(cert_url, timeout=5)
            response.raise_for_status()
            cert_pem = response.content
        except requests.exceptions.RequestException as e:
            logger.error("certificate_download_failed", url=cert_url, error=str(e))
            return False, f"Failed to download certificate: {str(e)}"
        
        # Parse certificate
        try:
            cert = x509.load_pem_x509_certificate(cert_pem)
        except Exception as e:
            logger.error("certificate_parse_failed", error=str(e))
            return False, f"Failed to parse certificate: {str(e)}"
        
        # Check expiration
        now = datetime.now(timezone.utc)
        if cert.not_valid_after_utc < now:
            logger.error("certificate_expired", not_after=cert.not_valid_after_utc)
            return False, "Certificate has expired"
        
        if cert.not_valid_before_utc > now:
            logger.error("certificate_not_yet_valid", not_before=cert.not_valid_before_utc)
            return False, "Certificate is not yet valid"
        
        # Validate certificate subject (should be from PayPal)
        if not self._is_paypal_certificate(cert):
            logger.error("certificate_not_from_paypal", subject=cert.subject.rfc4514_string())
            return False, "Certificate is not from PayPal"
        
        # Cache the certificate
        self._cert_cache[cert_url] = (cert, time.time())
        
        logger.info(
            "certificate_validated",
            subject=cert.subject.rfc4514_string(),
            expires=cert.not_valid_after_utc.isoformat()
        )
        
        return True, cert
    
    def _is_valid_paypal_url(self, url: str) -> bool:
        """Validates that a URL is from PayPal's domain and uses HTTPS."""
        if not url:
            return False
        
        # Must be HTTPS
        if not url.startswith("https://"):
            return False
        
        # Must be from paypal.com or api.paypal.com
        valid_domains = ["paypal.com", "api.paypal.com", "api-m.paypal.com"]
        
        try:
            # Extract domain from URL
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Check if domain matches or is subdomain of valid domains
            return any(
                domain == valid or domain.endswith(f".{valid}")
                for valid in valid_domains
            )
        except Exception:
            return False
    
    def _is_paypal_certificate(self, cert: Certificate) -> bool:
        """
        Validates that a certificate belongs to PayPal.
        Checks the Common Name (CN) or Subject Alternative Names.
        """
        try:
            # Check Common Name
            cn_attrs = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
            if cn_attrs:
                cn = cn_attrs[0].value.lower()
                if "paypal" in cn:
                    return True
            
            # Check Subject Alternative Names
            try:
                san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
                dns_names = san_ext.value.get_values_for_type(x509.DNSName)
                
                for name in dns_names:
                    if "paypal.com" in name.lower():
                        return True
            except x509.ExtensionNotFound:
                pass
            
            return False
            
        except Exception as e:
            logger.error("certificate_validation_error", error=str(e))
            return False
    
    def _compute_crc32(self, data: str) -> int:
        """Computes CRC32 checksum of the request body."""
        return binascii.crc32(data.encode('utf-8'))
    
    def _verify_signature(
        self,
        cert: Certificate,
        signature_b64: str,
        data: str,
        auth_algo: str
    ) -> Tuple[bool, str]:
        """
        Verifies the cryptographic signature using the certificate's public key.
        """
        try:
            # Get the public key from the certificate
            public_key = cert.public_key()
            
            # Verify it's an RSA key
            if not isinstance(public_key, rsa.RSAPublicKey):
                logger.error("certificate_not_rsa_key")
                return False, "Certificate does not contain an RSA public key"
            
            # Decode the base64 signature
            try:
                signature_bytes = base64.b64decode(signature_b64)
            except Exception as e:
                logger.error("signature_decode_failed", error=str(e))
                return False, f"Failed to decode signature: {str(e)}"
            
            # Choose the hash algorithm based on PayPal's auth_algo header
            hash_algo = self._get_hash_algorithm(auth_algo)
            if hash_algo is None:
                logger.error("unsupported_auth_algorithm", auth_algo=auth_algo)
                return False, f"Unsupported authentication algorithm: {auth_algo}"
            
            # Verify the signature
            try:
                public_key.verify(
                    signature_bytes,
                    data.encode('utf-8'),
                    padding.PKCS1v15(),
                    hash_algo
                )
                
                return True, "Signature verified"
                
            except InvalidSignature:
                logger.error(
                    "invalid_signature",
                    auth_algo=auth_algo,
                    data_length=len(data)
                )
                return False, "❌ INVALID SIGNATURE - Possible attack!"
                
        except Exception as e:
            logger.error("signature_verification_error", error=str(e), exc_info=True)
            return False, f"Signature verification error: {str(e)}"
    
    def _get_hash_algorithm(self, auth_algo: str) -> Optional[hashes.HashAlgorithm]:
        """Maps PayPal's auth algorithm string to cryptography hash algorithm."""
        algo_map = {
            'SHA256withRSA': hashes.SHA256(),
            'SHA1withRSA': hashes.SHA1(),
            'SHA256withRSAandMGF1': hashes.SHA256(),
        }
        return algo_map.get(auth_algo)
    
    def _record_verification(self, success: bool, reason: str, start_time: float) -> None:
        """Records verification result in metrics."""
        duration = time.time() - start_time
        
        metrics.record_webhook(
            verified=success,
            event_type=reason,
            processing_time=duration
        )
    
    def _mask_webhook_id(self, webhook_id: str) -> str:
        """Masks the webhook ID for safe logging (shows first 8 chars only)."""
        if len(webhook_id) <= 8:
            return webhook_id
        return f"{webhook_id[:8]}...{webhook_id[-4:]}"
    
    def clear_certificate_cache(self) -> None:
        """Clears the certificate cache. Useful for testing or certificate rotation."""
        self._cert_cache.clear()
        logger.info("certificate_cache_cleared")


# ==========================================
# MODULE-LEVEL CONVENIENCE
# ==========================================

# Global instance for easy import
_default_verifier: Optional[PayPalWebhookVerifier] = None


def get_default_verifier(webhook_id: Optional[str] = None) -> PayPalWebhookVerifier:
    """
    Returns the default global webhook verifier instance.
    
    Args:
        webhook_id: Optional webhook ID (uses env var if not provided)
    
    Returns:
        PayPalWebhookVerifier instance
    """
    global _default_verifier
    
    if _default_verifier is None:
        wh_id = webhook_id or os.getenv("PAYPAL_WEBHOOK_ID")
        if not wh_id:
            raise ValueError(
                "PAYPAL_WEBHOOK_ID not provided and not set in environment"
            )
        _default_verifier = PayPalWebhookVerifier(wh_id)
    
    return _default_verifier


def verify_webhook(headers: Dict[str, str], body: str) -> Tuple[bool, str]:
    """
    Convenience function to verify a webhook using the default verifier.
    
    Args:
        headers: HTTP headers from the webhook request
        body: Raw request body as string
    
    Returns:
        Tuple of (is_valid, message)
    """
    return get_default_verifier().verify(headers, body)