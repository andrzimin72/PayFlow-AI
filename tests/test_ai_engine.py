"""
Tests for the AI Categorisation Engine
======================================

Version: 2.0.0
"""

from __future__ import annotations

import pandas as pd
import pytest

import ai_engine
from ai_engine import (
    CATEGORIES,
    get_categories,
    is_income_category,
    process_transactions,
    validate_category,
)


# =============================================================================
# process_transactions
# =============================================================================

class TestProcessTransactions:
    """Tests for the main categorisation pipeline."""

    def test_returns_dataframe(self, sample_paypal_transactions, mock_classifier):
        result = process_transactions(sample_paypal_transactions, mock_classifier)
        assert isinstance(result, pd.DataFrame)

    def test_row_count_matches_input(self, sample_paypal_transactions, mock_classifier):
        result = process_transactions(sample_paypal_transactions, mock_classifier)
        assert len(result) == len(sample_paypal_transactions)

    def test_required_columns_present(self, sample_paypal_transactions, mock_classifier):
        result = process_transactions(sample_paypal_transactions, mock_classifier)
        expected = {"Amount", "Description", "Status", "AI Category", "Confidence"}
        assert expected.issubset(set(result.columns))

    def test_correct_categorisation_by_keyword(
        self, sample_paypal_transactions, mock_classifier
    ):
        result = process_transactions(sample_paypal_transactions, mock_classifier)
        categories = result["AI Category"].tolist()
        assert categories[0] == "Freelance Income"
        assert categories[1] == "Software Subscription"
        assert categories[2] == "Personal Expense"
        assert categories[3] == "Suspicious Activity"

    def test_confidence_is_float_in_range(
        self, sample_paypal_transactions, mock_classifier
    ):
        result = process_transactions(sample_paypal_transactions, mock_classifier)
        for conf in result["Confidence"]:
            assert isinstance(conf, float)
            assert 0.0 <= conf <= 1.0

    def test_empty_input_returns_empty_dataframe(self, mock_classifier):
        result = process_transactions([], mock_classifier)
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_malformed_transaction_still_produces_row(
        self, malformed_paypal_transaction, mock_classifier
    ):
        result = process_transactions(malformed_paypal_transaction, mock_classifier)
        assert len(result) == 1
        assert "Amount" in result.columns

    def test_description_truncated_to_max_length(
        self, mock_classifier
    ):
        long_description_tx = [
            {
                "transaction_info": {
                    "transaction_id": "TX_LONG",
                    "transaction_subject": "A" * 200,
                    "transaction_amount": {"value": "10.00", "currency_code": "USD"},
                    "transaction_status": "S",
                }
            }
        ]
        result = process_transactions(long_description_tx, mock_classifier)
        assert len(result.iloc[0]["Description"]) <= 43  # 40 + "..."


# =============================================================================
# Helper functions
# =============================================================================

class TestHelpers:
    """Tests for module-level helper functions."""

    def test_get_categories_returns_list(self):
        result = get_categories()
        assert isinstance(result, list)
        assert result == CATEGORIES

    def test_get_categories_returns_copy(self):
        result = get_categories()
        result.append("Hacked Category")
        assert "Hacked Category" not in CATEGORIES

    @pytest.mark.parametrize(
        "category,expected",
        [
            ("Freelance Income", True),
            ("Software Subscription", True),
            ("Personal Expense", True),
            ("Suspicious Activity", True),
            ("Unknown Category", False),
            ("", False),
        ],
    )
    def test_validate_category(self, category, expected):
        assert validate_category(category) is expected

    @pytest.mark.parametrize(
        "category,expected",
        [
            ("Freelance Income", True),
            ("Software Subscription", False),
            ("Personal Expense", False),
            ("Suspicious Activity", False),
        ],
    )
    def test_is_income_category(self, category, expected):
        assert is_income_category(category) is expected


# =============================================================================
# Configuration
# =============================================================================

class TestConfiguration:
    """Tests for module-level configuration constants."""

    def test_categories_has_expected_count(self):
        assert len(CATEGORIES) == 4

    def test_categories_contains_required_labels(self):
        required = {
            "Freelance Income",
            "Software Subscription",
            "Personal Expense",
            "Suspicious Activity",
        }
        assert required == set(CATEGORIES)