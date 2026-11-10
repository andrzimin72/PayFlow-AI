"""
Tests for the Elasticsearch Manager
===================================

Version: 2.0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from elasticsearch.exceptions import NotFoundError

import elastic_manager


@pytest.fixture(autouse=True)
def reset_es_client():
    """Reset the module-level ES client between tests."""
    elastic_manager._client = None
    yield
    elastic_manager._client = None


# =============================================================================
# Client initialisation
# =============================================================================

class TestClientInitialisation:

    @patch("elastic_manager.Elasticsearch")
    def test_client_created_lazily(self, mock_es_class):
        mock_es_class.return_value = MagicMock()
        client = elastic_manager.get_client()
        mock_es_class.assert_called_once()
        assert client is not None

    @patch("elastic_manager.Elasticsearch")
    def test_client_reused_on_subsequent_calls(self, mock_es_class):
        mock_es_class.return_value = MagicMock()
        elastic_manager.get_client()
        elastic_manager.get_client()
        mock_es_class.assert_called_once()


# =============================================================================
# Index lifecycle
# =============================================================================

class TestIndexLifecycle:

    @patch("elastic_manager.get_client")
    def test_setup_index_creates_when_missing(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = False
        mock_get_client.return_value = mock_es

        assert elastic_manager.setup_index() is True
        mock_es.indices.create.assert_called_once()

    @patch("elastic_manager.get_client")
    def test_setup_index_skips_when_exists(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = True
        mock_get_client.return_value = mock_es

        assert elastic_manager.setup_index() is True
        mock_es.indices.create.assert_not_called()

    @patch("elastic_manager.get_client")
    def test_delete_index_when_exists(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = True
        mock_get_client.return_value = mock_es

        assert elastic_manager.delete_index() is True
        mock_es.indices.delete.assert_called_once()

    @patch("elastic_manager.get_client")
    def test_delete_index_when_missing(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.indices.exists.return_value = False
        mock_get_client.return_value = mock_es

        assert elastic_manager.delete_index() is False


# =============================================================================
# Ingestion
# =============================================================================

class TestIngestion:

    @patch("elastic_manager.setup_index")
    @patch("elastic_manager.get_client")
    def test_index_transactions_returns_zero_for_empty_df(self, mock_get_client, mock_setup):
        result = elastic_manager.index_transactions(pd.DataFrame())
        assert result == 0

    @patch("elastic_manager.helpers.bulk")
    @patch("elastic_manager.setup_index")
    @patch("elastic_manager.get_client")
    def test_index_transactions_bulk_success(self, mock_get_client, mock_setup, mock_bulk):
        mock_bulk.return_value = (3, [])  # 3 successes, 0 errors
        df = pd.DataFrame({
            "Amount": ["100.00 USD", "200.00 USD", "300.00 USD"],
            "Description": ["A", "B", "C"],
            "AI Category": ["X", "Y", "Z"],
            "Confidence": [0.9, 0.8, 0.7],
            "Status": ["S", "S", "S"],
        })

        result = elastic_manager.index_transactions(df)
        assert result == 3

    @patch("elastic_manager.setup_index")
    @patch("elastic_manager.get_client")
    def test_index_single_transaction_success(self, mock_get_client, mock_setup):
        mock_es = MagicMock()
        mock_get_client.return_value = mock_es

        doc = {"description": "Test", "amount": 100.0}
        assert elastic_manager.index_single_transaction(doc) is True
        mock_es.index.assert_called_once()


# =============================================================================
# Search & retrieval
# =============================================================================

class TestSearchAndRetrieval:

    @patch("elastic_manager.get_client")
    def test_search_returns_dataframe(self, mock_get_client, sample_es_hits):
        mock_es = MagicMock()
        mock_es.search.return_value = {"hits": {"hits": sample_es_hits}}
        mock_get_client.return_value = mock_es

        result = elastic_manager.search_transactions("Adobe")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "Description" in result.columns

    @patch("elastic_manager.get_client")
    def test_search_returns_empty_on_no_results(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.search.return_value = {"hits": {"hits": []}}
        mock_get_client.return_value = mock_es

        result = elastic_manager.search_transactions("nonexistent")
        assert result.empty

    @patch("elastic_manager.get_client")
    def test_search_handles_missing_index(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.search.side_effect = NotFoundError(404, "index_not_found")
        mock_get_client.return_value = mock_es

        result = elastic_manager.search_transactions("test")
        assert result.empty

    @patch("elastic_manager.get_client")
    def test_get_all_transactions(self, mock_get_client, sample_es_hits):
        mock_es = MagicMock()
        mock_es.search.return_value = {"hits": {"hits": sample_es_hits}}
        mock_get_client.return_value = mock_es

        result = elastic_manager.get_all_transactions()
        assert len(result) == 2

    @patch("elastic_manager.get_client")
    def test_get_transaction_count(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.count.return_value = {"count": 42}
        mock_get_client.return_value = mock_es

        assert elastic_manager.get_transaction_count() == 42

    @patch("elastic_manager.get_client")
    def test_get_transaction_count_handles_missing_index(self, mock_get_client):
        mock_es = MagicMock()
        mock_es.count.side_effect = NotFoundError(404, "index_not_found")
        mock_get_client.return_value = mock_es

        assert elastic_manager.get_transaction_count() == 0


# =============================================================================
# Internal helpers
# =============================================================================

class TestHelpers:

    def test_parse_amount_with_currency(self):
        amount, currency = elastic_manager._parse_amount("1,234.56 USD")
        assert amount == 1234.56
        assert currency == "USD"

    def test_parse_amount_without_currency(self):
        amount, currency = elastic_manager._parse_amount("100.00")
        assert amount == 100.0
        assert currency == "USD"

    def test_parse_amount_invalid(self):
        amount, currency = elastic_manager._parse_amount("not a number")
        assert amount == 0.0
        assert currency == "USD"