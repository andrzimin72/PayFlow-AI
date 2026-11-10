"""
PayFlow AI Test Suite
=====================

Comprehensive test suite covering unit tests, integration tests, and
end-to-end validation of the PayFlow AI platform.

Test Organization
-----------------

Unit Tests (tests/):
    test_ai_engine.py          - AI categorization engine
    test_paypal_client.py      - PayPal API client
    test_api.py                - FastAPI REST API endpoints
    test_forecasting.py        - Cash flow forecasting
    test_elastic_manager.py    - Elasticsearch operations
    test_invoice_manager.py    - Invoice management
    test_dispute_manager.py    - Dispute resolution
    test_risk_engine.py        - Risk scoring engine

Integration Tests (tests/integration/):
    test_data_pipelines.py     - PayPal → AI → ES → Search flows
    test_risk_pipeline.py      - ES → Anomaly → Risk → Portfolio flows
    test_api_integration.py    - Full API flows with real modules
    test_webhook_integration.py - Webhook → Verify → AI → Alert flows

Running Tests
-------------

    # Run all tests
    pytest

    # Run with coverage
    pytest --cov=. --cov-report=html

    # Run only unit tests
    pytest tests/ -m "not integration"

    # Run only integration tests
    pytest tests/integration/

    # Run specific test file
    pytest tests/test_risk_engine.py -v

    # Run tests matching a pattern
    pytest -k "risk"

    # Run with verbose output
    pytest -v --tb=short

Test Markers
------------

    @pytest.mark.unit          - Unit tests (fast, isolated)
    @pytest.mark.integration   - Integration tests (may require mocks)
    @pytest.mark.slow          - Slow-running tests
    @pytest.mark.security      - Security-related tests
    @pytest.mark.ai            - AI/ML related tests
    @pytest.mark.requires_es   - Requires Elasticsearch (mocked in tests)

Coverage Requirements
---------------------

Minimum coverage threshold: 70% (configured in pytest.ini)
Target coverage: 85%+

Fixtures
--------

Shared fixtures are defined in conftest.py and automatically available
to all test files. Key fixtures include:

    - sample_paypal_transactions: Realistic PayPal API payloads
    - mock_classifier: Mock zero-shot NLP classifier
    - integration_es_client: In-memory Elasticsearch mock
    - api_client: FastAPI TestClient with mocked dependencies
    - sample_categorized_df: Pre-categorized transaction DataFrame
"""

# Package metadata
__version__ = "2.0.0"
__author__ = "Andre Zimin"
__license__ = "Apache-2.0"

# Test suite doesn't expose a public API
__all__: list[str] = []

# =============================================================================
# TEST UTILITIES (Optional helpers for test files)
# =============================================================================


def assert_dataframe_columns(df, required_columns: list[str]) -> None:
    """
    Assert that a DataFrame contains all required columns.

    Args:
        df: Pandas DataFrame to check
        required_columns: List of column names that must be present

    Raises:
        AssertionError: If any required column is missing
    """
    missing = set(required_columns) - set(df.columns)
    assert not missing, f"Missing columns: {missing}"


def assert_risk_score_in_range(score: float, min_val: float = 0.0, max_val: float = 100.0) -> None:
    """
    Assert that a risk score is within the valid range.

    Args:
        score: Risk score to validate
        min_val: Minimum valid value (default: 0.0)
        max_val: Maximum valid value (default: 100.0)

    Raises:
        AssertionError: If score is out of range
    """
    assert min_val <= score <= max_val, f"Risk score {score} out of range [{min_val}, {max_val}]"


def assert_confidence_in_range(confidence: float) -> None:
    """
    Assert that an AI confidence score is between 0 and 1.

    Args:
        confidence: Confidence score to validate

    Raises:
        AssertionError: If confidence is out of range
    """
    assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} out of range [0.0, 1.0]"


def assert_http_status(response, expected_status: int) -> None:
    """
    Assert that an HTTP response has the expected status code.

    Args:
        response: HTTP response object (from TestClient)
        expected_status: Expected HTTP status code

    Raises:
        AssertionError: If status code doesn't match
    """
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. "
        f"Response: {response.text}"
    )
