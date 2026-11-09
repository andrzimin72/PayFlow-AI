"""
Synthetic Data Generator for PayFlow AI Demo
=============================================

Generates realistic PayPal-like transaction data, invoices, and disputes
for demonstration purposes without requiring external API access.

Features:
- Realistic transaction patterns (subscriptions, one-time payments, etc.)
- Intentional anomalies for detection testing
- Sample invoices and disputes
- Configurable data volume and characteristics

Version: 1.0.0
"""

import random
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
import numpy as np


class SyntheticDataGenerator:
    """Generates realistic synthetic financial data for demonstrations."""
    
    def __init__(self, seed: int = 42):
        """
        Initialize the generator with a random seed for reproducibility.
        
        Args:
            seed: Random seed for reproducible data generation
        """
        random.seed(seed)
        np.random.seed(seed)
        
        # Transaction templates
        self.transaction_templates = {
            'freelance_income': [
                {'desc': 'Payment from {client} for web development', 'amount_range': (500, 5000)},
                {'desc': 'Consulting fee - {client}', 'amount_range': (200, 2000)},
                {'desc': 'Project milestone payment - {project}', 'amount_range': (1000, 10000)},
                {'desc': 'Freelance design work - {client}', 'amount_range': (300, 3000)},
                {'desc': 'AI model development - {project}', 'amount_range': (2000, 15000)},
            ],
            'software_subscription': [
                {'desc': 'Adobe Creative Cloud', 'amount_range': (52.99, 52.99)},
                {'desc': 'GitHub Pro subscription', 'amount_range': (4, 4)},
                {'desc': 'AWS monthly bill', 'amount_range': (50, 500)},
                {'desc': 'Slack Business+', 'amount_range': (12.5, 12.5)},
                {'desc': 'Figma Professional', 'amount_range': (12, 12)},
                {'desc': 'Notion Team Plan', 'amount_range': (8, 8)},
                {'desc': 'Zoom Pro', 'amount_range': (14.99, 14.99)},
            ],
            'personal_expense': [
                {'desc': 'Starbucks Coffee', 'amount_range': (5, 15)},
                {'desc': 'Amazon.com purchase', 'amount_range': (20, 200)},
                {'desc': 'Uber ride', 'amount_range': (10, 50)},
                {'desc': 'Grocery store', 'amount_range': (50, 150)},
                {'desc': 'Restaurant - {restaurant}', 'amount_range': (30, 100)},
                {'desc': 'Netflix subscription', 'amount_range': (15.99, 15.99)},
            ],
            'suspicious_activity': [
                {'desc': 'Wire transfer to offshore account', 'amount_range': (5000, 50000)},
                {'desc': 'URGENT: International payment', 'amount_range': (10000, 100000)},
                {'desc': 'Cryptocurrency exchange deposit', 'amount_range': (1000, 20000)},
                {'desc': 'Unknown merchant - HIGH RISK', 'amount_range': (500, 5000)},
            ]
        }
        
        # Client and project names
        self.clients = ['TechCorp Inc.', 'StartupXYZ', 'Global Solutions', 'InnovateCo', 'DataDriven Ltd.']
        self.projects = ['Website Redesign', 'Mobile App', 'AI Chatbot', 'Data Pipeline', 'Cloud Migration']
        self.restaurants = ['Italian Bistro', 'Sushi Palace', 'Mexican Grill', 'Thai Garden', 'Burger Joint']
    
    def generate_transactions(
        self,
        count: int = 100,
        days_back: int = 90,
        anomaly_ratio: float = 0.1
    ) -> pd.DataFrame:
        """
        Generate synthetic PayPal transactions.
        
        Args:
            count: Number of transactions to generate
            days_back: How many days back to start
            anomaly_ratio: Percentage of transactions that should be anomalous
        
        Returns:
            DataFrame with synthetic transaction data
        """
        transactions = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Calculate how many of each type
        n_anomalies = int(count * anomaly_ratio)
        n_normal = count - n_anomalies
        
        # Generate normal transactions
        for i in range(n_normal):
            tx = self._generate_normal_transaction(start_date, end_date)
            transactions.append(tx)
        
        # Generate anomalous transactions
        for i in range(n_anomalies):
            tx = self._generate_anomalous_transaction(start_date, end_date)
            transactions.append(tx)
        
        # Shuffle to mix anomalies throughout
        random.shuffle(transactions)
        
        # Create DataFrame
        df = pd.DataFrame(transactions)
        
        # Sort by date
        df = df.sort_values('timestamp', ascending=False).reset_index(drop=True)
        
        return df
    
    def _generate_normal_transaction(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate a single normal transaction."""
        # Choose category with realistic distribution
        category_weights = {
            'freelance_income': 0.3,
            'software_subscription': 0.4,
            'personal_expense': 0.3,
        }
        
        category = random.choices(
            list(category_weights.keys()),
            weights=list(category_weights.values())
        )[0]
        
        # Select a template
        template = random.choice(self.transaction_templates[category])
        
        # Generate description
        description = template['desc']
        if '{client}' in description:
            description = description.format(client=random.choice(self.clients))
        if '{project}' in description:
            description = description.format(project=random.choice(self.projects))
        if '{restaurant}' in description:
            description = description.format(restaurant=random.choice(self.restaurants))
        
        # Generate amount
        min_amount, max_amount = template['amount_range']
        amount = round(random.uniform(min_amount, max_amount), 2)
        
        # Generate timestamp
        random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
        timestamp = start_date + timedelta(seconds=random_seconds)
        
        # Generate transaction ID
        tx_id = f"TX{random.randint(100000, 999999)}"
        
        return {
            'transaction_id': tx_id,
            'timestamp': timestamp.isoformat(),
            'description': description,
            'amount': f"{amount} USD",
            'amount_value': amount,
            'currency': 'USD',
            'status': 'S',  # Success
            'ai_category': self._infer_category(category),
            'confidence': round(random.uniform(0.75, 0.99), 2)
        }
    
    def _generate_anomalous_transaction(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate a single anomalous transaction."""
        # Select a suspicious template
        template = random.choice(self.transaction_templates['suspicious_activity'])
        description = template['desc']
        
        # Generate unusually large amount
        min_amount, max_amount = template['amount_range']
        amount = round(random.uniform(min_amount, max_amount), 2)
        
        # Generate timestamp
        random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
        timestamp = start_date + timedelta(seconds=random_seconds)
        
        # Generate transaction ID
        tx_id = f"TX{random.randint(100000, 999999)}"
        
        return {
            'transaction_id': tx_id,
            'timestamp': timestamp.isoformat(),
            'description': description,
            'amount': f"{amount} USD",
            'amount_value': amount,
            'currency': 'USD',
            'status': 'S',
            'ai_category': 'Suspicious Activity',
            'confidence': round(random.uniform(0.4, 0.7), 2)  # Lower confidence
        }
    
    def _infer_category(self, template_category: str) -> str:
        """Map template category to AI category."""
        mapping = {
            'freelance_income': 'Freelance Income',
            'software_subscription': 'Software Subscription',
            'personal_expense': 'Personal Expense',
            'suspicious_activity': 'Suspicious Activity'
        }
        return mapping.get(template_category, 'Unknown')
    
    def generate_invoices(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Generate synthetic invoice data.
        
        Args:
            count: Number of invoices to generate
        
        Returns:
            List of invoice dictionaries
        """
        invoices = []
        
        for i in range(count):
            invoice = {
                'invoice_id': f"INV{random.randint(10000, 99999)}",
                'invoice_number': f"INV-2026-{i+1:04d}",
                'client_name': random.choice(self.clients),
                'client_email': f"client{i}@example.com",
                'amount': round(random.uniform(1000, 10000), 2),
                'status': random.choice(['PAID', 'SENT', 'UNPAID']),
                'created_date': (datetime.now() - timedelta(days=random.randint(1, 60))).isoformat(),
                'due_date': (datetime.now() + timedelta(days=random.randint(1, 30))).isoformat(),
                'items': [
                    {
                        'name': random.choice(['Web Development', 'Consulting', 'Design Work', 'AI Implementation']),
                        'quantity': random.randint(1, 10),
                        'unit_price': round(random.uniform(100, 1000), 2)
                    }
                ]
            }
            invoices.append(invoice)
        
        return invoices
    
    def generate_disputes(self, count: int = 3) -> List[Dict[str, Any]]:
        """
        Generate synthetic dispute data.
        
        Args:
            count: Number of disputes to generate
        
        Returns:
            List of dispute dictionaries
        """
        disputes = []
        reasons = [
            'Item not received',
            'Unauthorized transaction',
            'Product not as described',
            'Duplicate charge',
            'Cancelled subscription still charged'
        ]
        
        for i in range(count):
            dispute = {
                'dispute_id': f"DSP{random.randint(10000, 99999)}",
                'reason': random.choice(reasons),
                'status': random.choice(['OPEN', 'WAITING_FOR_SELLER_RESPONSE', 'RESOLVED']),
                'amount': round(random.uniform(50, 500), 2),
                'currency': 'USD',
                'create_time': (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                'buyer': {
                    'name': f"Customer {i+1}",
                    'email': f"customer{i}@example.com"
                },
                'disputed_transactions': [
                    {
                        'transaction_id': f"TX{random.randint(100000, 999999)}",
                        'items': [
                            {
                                'name': random.choice(['Software License', 'Consulting Service', 'Digital Product']),
                                'quantity': '1',
                                'unit_price': {'value': str(round(random.uniform(50, 500), 2))}
                            }
                        ]
                    }
                ]
            }
            disputes.append(dispute)
        
        return disputes


# Convenience function for quick generation
def generate_demo_data(
    transactions: int = 100,
    invoices: int = 5,
    disputes: int = 3
) -> Dict[str, Any]:
    """
    Generate complete demo dataset.
    
    Args:
        transactions: Number of transactions
        invoices: Number of invoices
        disputes: Number of disputes
    
    Returns:
        Dictionary with all synthetic data
    """
    generator = SyntheticDataGenerator(seed=42)
    
    return {
        'transactions': generator.generate_transactions(transactions),
        'invoices': generator.generate_invoices(invoices),
        'disputes': generator.generate_disputes(disputes)
    }