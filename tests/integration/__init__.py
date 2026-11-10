"""
Integration Tests for PayFlow AI
================================

These tests verify that multiple modules work correctly together.
Unlike unit tests (which mock all dependencies), integration tests
let internal modules interact for real while mocking only external
services (PayPal API, Hugging Face, Zapier, Elasticsearch transport).

Marked with @pytest.mark.integration so they can be run separately:
    pytest tests/integration/ -v
    pytest -m integration -v
"""