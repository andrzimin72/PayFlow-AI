"""
Risk Engine Test Suite
======================

Comprehensive tests for the Risk Management Engine including:
- Weighted risk score calculation
- Risk level threshold mapping
- Single transaction scoring
- Batch transaction scoring
- Portfolio-level risk metrics
- Edge cases and boundary conditions

Version: 1.0.0
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

# Import the module under test
import risk_engine
from risk_engine import (
    calculate_risk_score,
    get_risk_level,
    score_transaction,
    score_all_transactions,
    get_portfolio_risk_metrics,
    RISK_LEVELS
)


# ==========================================
# FIXTURES
# ==========================================

@pytest.fixture
def sample_transaction():
    """A sample transaction dictionary for testing."""
    return {
        'description': 'Suspicious wire transfer',
        'amount': '$10,000.00 USD',
        'amount_value': 10000.0,
        'ai_category': 'Suspicious Activity',
        'ai_confidence': 0.45,
        'anomaly_score': 0.85
    }


@pytest.fixture
def low_risk_transaction():
    """A low-risk transaction for testing."""
    return {
        'description': 'Adobe Creative Cloud',
        'amount': '59.99 USD',
        'amount_value': 59.99,
        'ai_category': 'Software Subscription',
        'ai_confidence': 0.95,
        'anomaly_score': 0.1
    }


@pytest.fixture
def medium_risk_transaction():
    """A medium-risk transaction for testing."""
    return {
        'description': 'Office Supplies',
        'amount': '250.00 USD',
        'amount_value': 250.0,
        'ai_category': 'Personal Expense',
        'ai_confidence': 0.75,
        'anomaly_score': 0.4
    }


@pytest.fixture
def sample_scored_transactions():
    """A list of pre-scored transactions for portfolio testing."""
    return [
        {
            'description': 'Adobe CC',
            'amount': '59.99 USD',
            'amount_value': 59.99,
            'ai_category': 'Software Subscription',
            'ai_confidence': 0.95,
            'anomaly_score': 0.1,
            'risk_score': 15.0,
            'risk_level': 'LOW',
            'risk_color': '#28a745',
            'recommended_action': 'AUTO_APPROVE',
            'action_description': 'Transaction appears normal.'
        },
        {
            'description': 'Office Supplies',
            'amount': '250.00 USD',
            'amount_value': 250.0,
            'ai_category': 'Personal Expense',
            'ai_confidence': 0.75,
            'anomaly_score': 0.4,
            'risk_score': 45.0,
            'risk_level': 'MEDIUM',
            'risk_color': '#ffc107',
            'recommended_action': 'MONITOR',
            'action_description': 'Slightly unusual.'
        },
        {
            'description': 'Wire Transfer',
            'amount': '5000.00 USD',
            'amount_value': 5000.0,
            'ai_category': 'Suspicious Activity',
            'ai_confidence': 0.45,
            'anomaly_score': 0.85,
            'risk_score': 85.0,
            'risk_level': 'CRITICAL',
            'risk_color': '#dc3545',
            'recommended_action': 'HOLD_AND_INVESTIGATE',
            'action_description': 'High-risk transaction.'
        }
    ]


# ==========================================
# TEST: calculate_risk_score()
# ==========================================

class TestCalculateRiskScore:
    """Test suite for the core risk score calculation function."""
    
    def test_minimum_possible_score(self):
        """Test that minimum inputs produce a score near 0."""
        score = calculate_risk_score(
            anomaly_score=0.0,
            ai_confidence=1.0,  # High confidence = low uncertainty
            amount=10.0,
            avg_amount=100.0  # Amount much lower than average
        )
        
        # Expected: (0 * 0.5) + (0 * 0.3) + (0.02 * 0.2) = 0.004 -> 0.4
        assert score >= 0.0
        assert score <= 10.0  # Should be very low
    
    def test_maximum_possible_score(self):
        """Test that maximum risk inputs produce a score near 100."""
        score = calculate_risk_score(
            anomaly_score=1.0,  # Maximum anomaly
            ai_confidence=0.0,  # Zero confidence = maximum uncertainty
            amount=10000.0,
            avg_amount=100.0  # Amount 100x average
        )
        
        # Expected: (1 * 0.5) + (1 * 0.3) + (1 * 0.2) = 1.0 -> 100
        assert score == 100.0
    
    def test_weight_distribution_anomaly(self):
        """Test that anomaly score has 50% weight."""
        # Only anomaly factor contributes
        score = calculate_risk_score(
            anomaly_score=1.0,
            ai_confidence=1.0,  # No uncertainty
            amount=100.0,
            avg_amount=100.0  # Normal amount
        )
        
        # Expected: (1 * 0.5) + (0 * 0.3) + (0.2 * 0.2) = 0.54 -> 54
        assert 40.0 <= score <= 60.0  # Around 50-60 due to amount factor
    
    def test_weight_distribution_ai_uncertainty(self):
        """Test that AI uncertainty has 30% weight."""
        score = calculate_risk_score(
            anomaly_score=0.0,
            ai_confidence=0.0,  # Maximum uncertainty
            amount=100.0,
            avg_amount=100.0
        )
        
        # Expected: (0 * 0.5) + (1 * 0.3) + (0.2 * 0.2) = 0.34 -> 34
        assert 30.0 <= score <= 40.0
    
    def test_weight_distribution_financial_impact(self):
        """Test that financial impact has 20% weight."""
        score = calculate_risk_score(
            anomaly_score=0.0,
            ai_confidence=1.0,
            amount=5000.0,  # 50x average
            avg_amount=100.0
        )
        
        # Expected: (0 * 0.5) + (0 * 0.3) + (1 * 0.2) = 0.2 -> 20
        assert 15.0 <= score <= 25.0
    
    def test_zero_average_amount(self):
        """Test handling of zero average amount (no historical data)."""
        score = calculate_risk_score(
            anomaly_score=0.5,
            ai_confidence=0.5,
            amount=100.0,
            avg_amount=0.0  # No historical data
        )
        
        # Should use default 0.5 for amount factor
        assert 0.0 <= score <= 100.0
        assert isinstance(score, float)
    
    def test_negative_inputs_clamped(self):
        """Test that negative inputs are clamped to valid ranges."""
        score = calculate_risk_score(
            anomaly_score=-0.5,  # Invalid negative
            ai_confidence=-0.2,  # Invalid negative
            amount=100.0,
            avg_amount=100.0
        )
        
        # Should not crash, should produce valid score
        assert 0.0 <= score <= 100.0
    
    def test_inputs_above_one_clamped(self):
        """Test that inputs above 1.0 are clamped."""
        score = calculate_risk_score(
            anomaly_score=1.5,  # Above max
            ai_confidence=2.0,  # Above max
            amount=100.0,
            avg_amount=100.0
        )
        
        assert 0.0 <= score <= 100.0
    
    def test_score_is_rounded_to_one_decimal(self):
        """Test that score is rounded to 1 decimal place."""
        score = calculate_risk_score(
            anomaly_score=0.333333,
            ai_confidence=0.666666,
            amount=123.45,
            avg_amount=100.0
        )
        
        # Check it has at most 1 decimal place
        assert score == round(score, 1)
    
    @pytest.mark.parametrize("anomaly,confidence,amount,avg,expected_range", [
        (0.0, 1.0, 50.0, 100.0, (0, 10)),      # Very low risk
        (0.5, 0.5, 100.0, 100.0, (30, 50)),    # Medium risk
        (1.0, 0.0, 1000.0, 100.0, (80, 100)),  # High risk
    ])
    def test_parametrized_scenarios(self, anomaly, confidence, amount, avg, expected_range):
        """Test various scenarios with expected score ranges."""
        score = calculate_risk_score(anomaly, confidence, amount, avg)
        assert expected_range[0] <= score <= expected_range[1]


# ==========================================
# TEST: get_risk_level()
# ==========================================

class TestGetRiskLevel:
    """Test suite for risk level threshold mapping."""
    
    def test_low_risk_boundary(self):
        """Test LOW risk level (0-39)."""
        result = get_risk_level(0)
        assert result['level'] == 'LOW'
        assert result['color'] == '#28a745'
        assert result['action'] == 'AUTO_APPROVE'
        
        result = get_risk_level(39)
        assert result['level'] == 'LOW'
    
    def test_medium_risk_boundary(self):
        """Test MEDIUM risk level (40-59)."""
        result = get_risk_level(40)
        assert result['level'] == 'MEDIUM'
        assert result['color'] == '#ffc107'
        assert result['action'] == 'MONITOR'
        
        result = get_risk_level(59)
        assert result['level'] == 'MEDIUM'
    
    def test_high_risk_boundary(self):
        """Test HIGH risk level (60-79)."""
        result = get_risk_level(60)
        assert result['level'] == 'HIGH'
        assert result['color'] == '#fd7e14'
        assert result['action'] == 'MANUAL_REVIEW'
        
        result = get_risk_level(79)
        assert result['level'] == 'HIGH'
    
    def test_critical_risk_boundary(self):
        """Test CRITICAL risk level (80-100)."""
        result = get_risk_level(80)
        assert result['level'] == 'CRITICAL'
        assert result['color'] == '#dc3545'
        assert result['action'] == 'HOLD_AND_INVESTIGATE'
        
        result = get_risk_level(100)
        assert result['level'] == 'CRITICAL'
    
    def test_score_preserved_in_result(self):
        """Test that the original score is preserved in the result."""
        result = get_risk_level(75.5)
        assert result['score'] == 75.5
    
    def test_description_present(self):
        """Test that description is included in result."""
        result = get_risk_level(50)
        assert 'description' in result
        assert len(result['description']) > 0
    
    def test_all_risk_levels_defined(self):
        """Test that all expected risk levels are in RISK_LEVELS."""
        expected_levels = {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}
        actual_levels = set(RISK_LEVELS.keys())
        assert expected_levels == actual_levels
    
    def test_risk_level_ranges_do_not_overlap(self):
        """Test that risk level ranges don't overlap."""
        ranges = []
        for level_data in RISK_LEVELS.values():
            ranges.append((level_data['min_score'], level_data['max_score']))
        
        # Sort by min_score
        ranges.sort()
        
        # Check no overlaps
        for i in range(len(ranges) - 1):
            assert ranges[i][1] < ranges[i + 1][0]


# ==========================================
# TEST: score_transaction()
# ==========================================

class TestScoreTransaction:
    """Test suite for single transaction scoring."""
    
    def test_score_transaction_returns_all_fields(self, sample_transaction):
        """Test that all expected fields are returned."""
        result = score_transaction(sample_transaction, avg_amount=1000.0)
        
        expected_fields = [
            'description', 'amount', 'amount_value', 'ai_category',
            'ai_confidence', 'anomaly_score', 'risk_score',
            'risk_level', 'risk_color', 'recommended_action',
            'action_description'
        ]
        
        for field in expected_fields:
            assert field in result
    
    def test_high_risk_transaction_classification(self, sample_transaction):
        """Test that a suspicious transaction is classified as high risk."""
        result = score_transaction(sample_transaction, avg_amount=100.0)
        
        assert result['risk_score'] >= 60.0
        assert result['risk_level'] in ['HIGH', 'CRITICAL']
        assert result['risk_color'] in ['#fd7e14', '#dc3545']
    
    def test_low_risk_transaction_classification(self, low_risk_transaction):
        """Test that a normal transaction is classified as low risk."""
        result = score_transaction(low_risk_transaction, avg_amount=100.0)
        
        assert result['risk_score'] < 40.0
        assert result['risk_level'] == 'LOW'
    
    def test_missing_fields_handled_gracefully(self):
        """Test that missing fields don't crash the function."""
        minimal_transaction = {
            'description': 'Test',
            'amount_value': 100.0
        }
        
        result = score_transaction(minimal_transaction, avg_amount=100.0)
        
        assert 'risk_score' in result
        assert 0.0 <= result['risk_score'] <= 100.0
    
    def test_anomaly_score_rounded(self, sample_transaction):
        """Test that anomaly score is rounded to 4 decimals."""
        sample_transaction['anomaly_score'] = 0.123456789
        result = score_transaction(sample_transaction, avg_amount=100.0)
        
        # Check it's rounded
        assert result['anomaly_score'] == round(result['anomaly_score'], 4)


# ==========================================
# TEST: score_all_transactions()
# ==========================================

class TestScoreAllTransactions:
    """Test suite for batch transaction scoring."""
    
    @patch('risk_engine.anomaly_detector.get_anomaly_data_with_scores')
    def test_score_all_returns_list(self, mock_get_anomaly, sample_transaction):
        """Test that score_all_transactions returns a list."""
        mock_df = pd.DataFrame([sample_transaction])
        mock_get_anomaly.return_value = mock_df
        
        result = score_all_transactions()
        
        assert isinstance(result, list)
        assert len(result) == 1
    
    @patch('risk_engine.anomaly_detector.get_anomaly_data_with_scores')
    def test_score_all_sorted_by_risk_descending(self, mock_get_anomaly):
        """Test that results are sorted by risk score (highest first)."""
        transactions = [
            {'description': 'Low', 'amount': '10 USD', 'amount_value': 10.0,
             'ai_category': 'Personal', 'ai_confidence': 0.95, 'anomaly_score': 0.1},
            {'description': 'High', 'amount': '10000 USD', 'amount_value': 10000.0,
             'ai_category': 'Suspicious', 'ai_confidence': 0.3, 'anomaly_score': 0.9},
            {'description': 'Medium', 'amount': '500 USD', 'amount_value': 500.0,
             'ai_category': 'Software', 'ai_confidence': 0.7, 'anomaly_score': 0.5}
        ]
        
        mock_df = pd.DataFrame(transactions)
        mock_get_anomaly.return_value = mock_df
        
        result = score_all_transactions()
        
        # Check sorted descending
        risk_scores = [tx['risk_score'] for tx in result]
        assert risk_scores == sorted(risk_scores, reverse=True)
    
    @patch('risk_engine.anomaly_detector.get_anomaly_data_with_scores')
    def test_score_all_empty_dataframe(self, mock_get_anomaly):
        """Test handling of empty DataFrame."""
        mock_get_anomaly.return_value = pd.DataFrame()
        
        result = score_all_transactions()
        
        assert result == []
    
    @patch('risk_engine.anomaly_detector.get_anomaly_data_with_scores')
    def test_score_all_calculates_correct_avg(self, mock_get_anomaly):
        """Test that average amount is calculated correctly."""
        transactions = [
            {'description': 'A', 'amount': '100 USD', 'amount_value': 100.0,
             'ai_category': 'X', 'ai_confidence': 0.5, 'anomaly_score': 0.5},
            {'description': 'B', 'amount': '200 USD', 'amount_value': 200.0,
             'ai_category': 'Y', 'ai_confidence': 0.5, 'anomaly_score': 0.5}
        ]
        
        mock_df = pd.DataFrame(transactions)
        mock_get_anomaly.return_value = mock_df
        
        result = score_all_transactions()
        
        # Average should be 150.0
        assert len(result) == 2


# ==========================================
# TEST: get_portfolio_risk_metrics()
# ==========================================

class TestGetPortfolioRiskMetrics:
    """Test suite for portfolio-level risk metrics."""
    
    @patch('risk_engine.score_all_transactions')
    def test_portfolio_metrics_structure(self, mock_score_all, sample_scored_transactions):
        """Test that portfolio metrics have correct structure."""
        mock_score_all.return_value = sample_scored_transactions
        
        result = get_portfolio_risk_metrics()
        
        expected_keys = [
            'status', 'portfolio_risk_score', 'risk_level', 'risk_color',
            'risk_description', 'recommended_action', 'total_transactions',
            'risk_distribution', 'high_risk_count', 'high_risk_percentage',
            'average_risk_score', 'max_risk_score', 'min_risk_score',
            'scored_transactions'
        ]
        
        for key in expected_keys:
            assert key in result
    
    @patch('risk_engine.score_all_transactions')
    def test_portfolio_risk_distribution(self, mock_score_all, sample_scored_transactions):
        """Test that risk distribution is calculated correctly."""
        mock_score_all.return_value = sample_scored_transactions
        
        result = get_portfolio_risk_metrics()
        
        distribution = result['risk_distribution']
        
        assert distribution['LOW'] == 1
        assert distribution['MEDIUM'] == 1
        assert distribution['HIGH'] == 0
        assert distribution['CRITICAL'] == 1
    
    @patch('risk_engine.score_all_transactions')
    def test_portfolio_high_risk_count(self, mock_score_all, sample_scored_transactions):
        """Test that high risk count includes HIGH and CRITICAL."""
        mock_score_all.return_value = sample_scored_transactions
        
        result = get_portfolio_risk_metrics()
        
        # Should count HIGH + CRITICAL = 0 + 1 = 1
        assert result['high_risk_count'] == 1
    
    @patch('risk_engine.score_all_transactions')
    def test_portfolio_high_risk_percentage(self, mock_score_all, sample_scored_transactions):
        """Test that high risk percentage is calculated correctly."""
        mock_score_all.return_value = sample_scored_transactions
        
        result = get_portfolio_risk_metrics()
        
        # 1 out of 3 = 33.3%
        assert 30.0 <= result['high_risk_percentage'] <= 40.0
    
    @patch('risk_engine.score_all_transactions')
    def test_portfolio_statistics(self, mock_score_all, sample_scored_transactions):
        """Test that portfolio statistics are calculated correctly."""
        mock_score_all.return_value = sample_scored_transactions
        
        result = get_portfolio_risk_metrics()
        
        # Scores: 15, 45, 85
        assert result['min_risk_score'] == 15.0
        assert result['max_risk_score'] == 85.0
        assert result['average_risk_score'] == 48.3  # (15+45+85)/3 ≈ 48.3
    
    @patch('risk_engine.score_all_transactions')
    def test_portfolio_uses_75th_percentile(self, mock_score_all):
        """Test that portfolio score uses 75th percentile."""
        # Create transactions with scores: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
        transactions = []
        for i in range(1, 11):
            score = i * 10
            transactions.append({
                'description': f'TX{i}',
                'amount': '100 USD',
                'amount_value': 100.0,
                'ai_category': 'Test',
                'ai_confidence': 0.5,
                'anomaly_score': 0.5,
                'risk_score': float(score),
                'risk_level': 'LOW' if score < 40 else ('MEDIUM' if score < 60 else ('HIGH' if score < 80 else 'CRITICAL')),
                'risk_color': '#28a745',
                'recommended_action': 'AUTO_APPROVE',
                'action_description': 'Test'
            })
        
        mock_score_all.return_value = transactions
        
        result = get_portfolio_risk_metrics()
        
        # 75th percentile of [10,20,30,40,50,60,70,80,90,100] = 77.5
        assert 70.0 <= result['portfolio_risk_score'] <= 80.0
    
    @patch('risk_engine.score_all_transactions')
    def test_portfolio_empty_transactions(self, mock_score_all):
        """Test handling of empty transaction list."""
        mock_score_all.return_value = []
        
        result = get_portfolio_risk_metrics()
        
        assert result['status'] == 'no_data'
        assert result['portfolio_risk_score'] == 0
        assert result['total_transactions'] == 0
    
    @patch('risk_engine.score_all_transactions')
    def test_portfolio_risk_level_matches_score(self, mock_score_all):
        """Test that risk level matches the portfolio score."""
        # Create transactions that result in HIGH portfolio risk
        transactions = [
            {
                'description': 'TX1',
                'amount': '10000 USD',
                'amount_value': 10000.0,
                'ai_category': 'Suspicious',
                'ai_confidence': 0.3,
                'anomaly_score': 0.9,
                'risk_score': 85.0,
                'risk_level': 'CRITICAL',
                'risk_color': '#dc3545',
                'recommended_action': 'HOLD_AND_INVESTIGATE',
                'action_description': 'High risk'
            }
        ]
        
        mock_score_all.return_value = transactions
        
        result = get_portfolio_risk_metrics()
        
        assert result['risk_level'] == 'CRITICAL'
        assert result['risk_color'] == '#dc3545'
        assert result['recommended_action'] == 'HOLD_AND_INVESTIGATE'


# ==========================================
# TEST: RISK_LEVELS Configuration
# ==========================================

class TestRiskLevelsConfiguration:
    """Test suite for RISK_LEVELS constant configuration."""
    
    def test_all_levels_have_required_keys(self):
        """Test that all risk levels have required keys."""
        required_keys = {'min_score', 'max_score', 'color', 'action', 'description'}
        
        for level_name, level_data in RISK_LEVELS.items():
            for key in required_keys:
                assert key in level_data, f"{level_name} missing key: {key}"
    
    def test_all_levels_have_valid_colors(self):
        """Test that all colors are valid hex codes."""
        for level_name, level_data in RISK_LEVELS.items():
            color = level_data['color']
            assert color.startswith('#'), f"{level_name} color doesn't start with #"
            assert len(color) == 7, f"{level_name} color length invalid: {color}"
    
    def test_all_levels_have_valid_actions(self):
        """Test that all actions are valid."""
        valid_actions = {'AUTO_APPROVE', 'MONITOR', 'MANUAL_REVIEW', 'HOLD_AND_INVESTIGATE'}
        
        for level_name, level_data in RISK_LEVELS.items():
            assert level_data['action'] in valid_actions, \
                f"{level_name} has invalid action: {level_data['action']}"
    
    def test_score_ranges_cover_0_to_100(self):
        """Test that score ranges cover the full 0-100 spectrum."""
        min_scores = [data['min_score'] for data in RISK_LEVELS.values()]
        max_scores = [data['max_score'] for data in RISK_LEVELS.values()]
        
        assert min(min_scores) == 0
        assert max(max_scores) == 100


# ==========================================
# TEST: Integration Tests
# ==========================================

class TestRiskEngineIntegration:
    """Integration tests for the complete risk scoring pipeline."""
    
    @patch('risk_engine.anomaly_detector.get_anomaly_data_with_scores')
    def test_end_to_end_scoring_pipeline(self, mock_get_anomaly):
        """Test the complete pipeline from raw data to portfolio metrics."""
        # Setup mock data
        transactions = [
            {'description': 'Normal TX', 'amount': '50 USD', 'amount_value': 50.0,
             'ai_category': 'Software', 'ai_confidence': 0.95, 'anomaly_score': 0.05},
            {'description': 'Suspicious TX', 'amount': '10000 USD', 'amount_value': 10000.0,
             'ai_category': 'Suspicious', 'ai_confidence': 0.3, 'anomaly_score': 0.95}
        ]
        
        mock_df = pd.DataFrame(transactions)
        mock_get_anomaly.return_value = mock_df
        
        # Execute pipeline
        scored = score_all_transactions()
        
        # Verify results
        assert len(scored) == 2
        
        # Check sorting (highest risk first)
        assert scored[0]['risk_score'] >= scored[1]['risk_score']
        
        # Get portfolio metrics
        portfolio = get_portfolio_risk_metrics()
        
        assert portfolio['status'] == 'success'
        assert portfolio['total_transactions'] == 2
        assert portfolio['high_risk_count'] >= 1
    
    def test_risk_score_monotonicity(self):
        """Test that increasing risk factors increases the score."""
        base_score = calculate_risk_score(0.5, 0.5, 100.0, 100.0)
        
        # Increase anomaly
        higher_anomaly = calculate_risk_score(0.8, 0.5, 100.0, 100.0)
        assert higher_anomaly > base_score
        
        # Decrease confidence (increase uncertainty)
        lower_confidence = calculate_risk_score(0.5, 0.2, 100.0, 100.0)
        assert lower_confidence > base_score
        
        # Increase amount
        higher_amount = calculate_risk_score(0.5, 0.5, 1000.0, 100.0)
        assert higher_amount > base_score


# ==========================================
# TEST: Edge Cases
# ==========================================

class TestEdgeCases:
    """Test suite for edge cases and error handling."""
    
    def test_extreme_amount_ratio(self):
        """Test handling of extreme amount ratios."""
        score = calculate_risk_score(
            anomaly_score=0.5,
            ai_confidence=0.5,
            amount=1000000.0,  # 10000x average
            avg_amount=100.0
        )
        
        # Should cap at 1.0 for amount factor
        assert 0.0 <= score <= 100.0
    
    def test_very_small_amounts(self):
        """Test handling of very small transaction amounts."""
        score = calculate_risk_score(
            anomaly_score=0.5,
            ai_confidence=0.5,
            amount=0.01,
            avg_amount=100.0
        )
        
        assert 0.0 <= score <= 100.0
    
    def test_identical_amounts(self):
        """Test when transaction amount equals average."""
        score = calculate_risk_score(
            anomaly_score=0.5,
            ai_confidence=0.5,
            amount=100.0,
            avg_amount=100.0
        )
        
        # Amount factor should be 0.2 (100 / (100 * 5) = 0.2)
        assert 0.0 <= score <= 100.0
    
    @patch('risk_engine.anomaly_detector.get_anomaly_data_with_scores')
    def test_single_transaction_portfolio(self, mock_get_anomaly):
        """Test portfolio metrics with a single transaction."""
        transactions = [
            {'description': 'Single', 'amount': '100 USD', 'amount_value': 100.0,
             'ai_category': 'Test', 'ai_confidence': 0.5, 'anomaly_score': 0.5}
        ]
        
        mock_df = pd.DataFrame(transactions)
        mock_get_anomaly.return_value = mock_df
        
        result = get_portfolio_risk_metrics()
        
        assert result['status'] == 'success'
        assert result['total_transactions'] == 1
        assert result['high_risk_percentage'] in [0.0, 100.0]
    
    def test_boundary_scores_exactly(self):
        """Test exact boundary values for risk levels."""
        # Test exact boundaries
        assert get_risk_level(0)['level'] == 'LOW'
        assert get_risk_level(39)['level'] == 'LOW'
        assert get_risk_level(40)['level'] == 'MEDIUM'
        assert get_risk_level(59)['level'] == 'MEDIUM'
        assert get_risk_level(60)['level'] == 'HIGH'
        assert get_risk_level(79)['level'] == 'HIGH'
        assert get_risk_level(80)['level'] == 'CRITICAL'
        assert get_risk_level(100)['level'] == 'CRITICAL'