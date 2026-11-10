"""
Data Layer Performance Tests
============================

Benchmarks Elasticsearch operations and data transformations.

Version: 1.0.0
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import elastic_manager


pytestmark = [pytest.mark.performance, pytest.mark.slow]


# =============================================================================
# ELASTICSEARCH INDEXING PERFORMANCE
# =============================================================================


class TestElasticsearchIndexingPerformance:
    """Benchmark Elasticsearch bulk indexing."""

    def test_bulk_index_small_batch(self, benchmark, integration_es_client, small_categorized_df):
        """
        Bulk index 10 documents.

        Threshold: < 100ms
        """

        def index_batch():
            return elastic_manager.index_transactions(small_categorized_df)

        result = benchmark(index_batch)
        assert result == 10
        assert benchmark.stats.mean < 0.100

    def test_bulk_index_medium_batch(self, benchmark, integration_es_client, medium_categorized_df):
        """
        Bulk index 100 documents.

        Threshold: < 500ms
        """

        def index_batch():
            return elastic_manager.index_transactions(medium_categorized_df)

        result = benchmark(index_batch)
        assert result == 100
        assert benchmark.stats.mean < 0.500

    def test_bulk_index_large_batch(self, benchmark, integration_es_client, large_categorized_df):
        """
        Bulk index 1000 documents.

        Threshold: < 3s
        """

        def index_batch():
            return elastic_manager.index_transactions(large_categorized_df)

        result = benchmark(index_batch)
        assert result == 1000
        assert benchmark.stats.mean < 3.0


# =============================================================================
# ELASTICSEARCH SEARCH PERFORMANCE
# =============================================================================


class TestElasticsearchSearchPerformance:
    """Benchmark Elasticsearch search operations."""

    def test_search_empty_index(self, benchmark, integration_es_client):
        """
        Search on empty index.

        Threshold: < 50ms
        """

        def search():
            return elastic_manager.search_transactions("test")

        result = benchmark(search)
        assert result.empty
        assert benchmark.stats.mean < 0.050

    def test_search_small_index(self, benchmark, integration_es_client, small_categorized_df):
        """
        Search on index with 10 documents.

        Threshold: < 100ms
        """
        elastic_manager.index_transactions(small_categorized_df)

        def search():
            return elastic_manager.search_transactions("Adobe")

        result = benchmark(search)
        assert benchmark.stats.mean < 0.100

    def test_search_medium_index(self, benchmark, integration_es_client, medium_categorized_df):
        """
        Search on index with 100 documents.

        Threshold: < 200ms
        """
        elastic_manager.index_transactions(medium_categorized_df)

        def search():
            return elastic_manager.search_transactions("Adobe")

        result = benchmark(search)
        assert benchmark.stats.mean < 0.200

    def test_search_large_index(self, benchmark, integration_es_client, large_categorized_df):
        """
        Search on index with 1000 documents.

        Threshold: < 500ms
        """
        elastic_manager.index_transactions(large_categorized_df)

        def search():
            return elastic_manager.search_transactions("Adobe")

        result = benchmark(search)
        assert benchmark.stats.mean < 0.500

    def test_get_all_transactions_medium_index(
        self, benchmark, integration_es_client, medium_categorized_df
    ):
        """
        Retrieve all documents from medium index.

        Threshold: < 300ms
        """
        elastic_manager.index_transactions(medium_categorized_df)

        def get_all():
            return elastic_manager.get_all_transactions()

        result = benchmark(get_all)
        assert len(result) == 100
        assert benchmark.stats.mean < 0.300


# =============================================================================
# DATA TRANSFORMATION PERFORMANCE
# =============================================================================


class TestDataTransformationPerformance:
    """Benchmark data transformation operations."""

    def test_dataframe_creation_small(self, benchmark):
        """
        Create DataFrame from 100 rows.

        Threshold: < 50ms
        """

        def create_df():
            data = [{"col1": i, "col2": f"value_{i}"} for i in range(100)]
            return pd.DataFrame(data)

        result = benchmark(create_df)
        assert len(result) == 100
        assert benchmark.stats.mean < 0.050

    def test_dataframe_creation_large(self, benchmark):
        """
        Create DataFrame from 10000 rows.

        Threshold: < 500ms
        """

        def create_df():
            data = [{"col1": i, "col2": f"value_{i}"} for i in range(10000)]
            return pd.DataFrame(data)

        result = benchmark(create_df)
        assert len(result) == 10000
        assert benchmark.stats.mean < 0.500

    def test_amount_parsing_performance(self, benchmark):
        """
        Parse 1000 amount strings.

        Threshold: < 200ms
        """
        amounts = [f"{100.0 + i:.2f} USD" for i in range(1000)]

        def parse_amounts():
            return [float(a.split()[0]) for a in amounts]

        result = benchmark(parse_amounts)
        assert len(result) == 1000
        assert benchmark.stats.mean < 0.200