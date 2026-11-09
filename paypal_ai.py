"""
PayPal AI - Standalone Demo Script
===================================

A simplified, self-contained script that demonstrates the core concept:
Fetching PayPal transactions and categorizing them with AI.

This is a standalone version for quick testing and demonstration.
For production use, refer to the modular architecture (paypal_client.py + ai_engine.py).

Version: 1.0.0
"""

import requests
import base64
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from transformers import pipeline
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================
CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
SECRET = os.getenv("PAYPAL_SECRET")
BASE_URL = 'https://api-m.sandbox.paypal.com'

# AI Categories for classification
CATEGORIES = [
    'Freelance Income', 
    'Software Subscription', 
    'Personal Expense', 
    'Suspicious Activity'
]

# ==========================================
# PAYPAL AUTHENTICATION
# ==========================================
def get_access_token() -> Optional[str]:
    """
    Authenticates with PayPal and returns an OAuth 2.0 access token.
    
    Returns:
        str: Access token, or None if authentication failed.
    """
    if not CLIENT_ID or not SECRET:
        print("❌ Error: PAYPAL_CLIENT_ID and PAYPAL_SECRET must be set in .env file")
        return None
    
    url = f"{BASE_URL}/v1/oauth2/token"
    
    # PayPal requires Basic Auth: base64 encode "client_id:secret"
    auth_str = f"{CLIENT_ID}:{SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {b64_auth}"
    }
    
    data = "grant_type=client_credentials"
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        return token_data.get('access_token')
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Authentication failed: {e}")
        return None
    except ValueError as e:
        print(f"❌ Failed to parse response: {e}")
        return None


# ==========================================
# FETCH TRANSACTIONS
# ==========================================
def fetch_transactions(token: str, days_back: int = 30) -> List[Dict[str, Any]]:
    """
    Fetches transaction history from the PayPal Reporting API.
    
    Args:
        token: Valid PayPal access token
        days_back: Number of days to look back (default: 30)
    
    Returns:
        List of transaction dictionaries, or empty list on error.
    """
    url = f"{BASE_URL}/v1/reporting/transactions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # Calculate date range (ISO 8601 format)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    
    params = {
        "start_date": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_date": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fields": "all",
        "page_size": 100
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        transactions = data.get('transaction_details', [])
        
        print(f"✅ Fetched {len(transactions)} transactions from PayPal")
        return transactions
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ API error: {e}")
        return []
    except ValueError as e:
        print(f"❌ Failed to parse response: {e}")
        return []


# ==========================================
# AI CATEGORIZATION
# ==========================================
def categorize_transaction(description: str, classifier) -> Dict[str, Any]:
    """
    Uses zero-shot NLP to categorize a transaction description.
    
    Args:
        description: Transaction description text
        classifier: Hugging Face zero-shot classification pipeline
    
    Returns:
        Dictionary with 'category' and 'confidence' keys.
    """
    # Fallback for empty descriptions
    if not description or description.strip() == "":
        description = "Standard PayPal transfer"
    
    try:
        result = classifier(description, CATEGORIES)
        
        return {
            "category": result['labels'][0],
            "confidence": result['scores'][0]
        }
    except Exception as e:
        print(f"⚠️ AI categorization failed: {e}")
        return {
            "category": "Unknown",
            "confidence": 0.0
        }


# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    """Main execution flow."""
    print("=" * 60)
    print("PayPal AI - Standalone Demo")
    print("=" * 60)
    
    # Step 1: Load AI model
    print("\n🧠 Loading AI NLP Model...")
    try:
        classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        print("✅ AI Model loaded successfully!\n")
    except Exception as e:
        print(f"❌ Failed to load AI model: {e}")
        return
    
    # Step 2: Authenticate with PayPal
    print("🔐 Authenticating with PayPal Sandbox...")
    access_token = get_access_token()
    
    if not access_token:
        print("❌ Authentication failed. Please check your .env file.")
        return
    
    print("✅ Authentication successful!\n")
    
    # Step 3: Fetch transactions
    print("🔍 Fetching transactions...")
    transactions = fetch_transactions(access_token)
    
    if not transactions:
        print("⚠️ No transactions found in the last 30 days.")
        print("Did you make a test payment in the PayPal Sandbox?")
        return
    
    print(f"✅ Found {len(transactions)} transaction(s)\n")
    
    # Step 4: Process and categorize
    print("🤖 Running AI categorization...")
    print("-" * 80)
    print(f"{'AMOUNT':<15} | {'DESCRIPTION':<35} | {'AI CATEGORY':<25} | {'CONFIDENCE'}")
    print("-" * 80)
    
    for tx in transactions:
        tx_info = tx.get('transaction_info', {})
        
        # Extract data
        amount = tx_info.get('transaction_amount', {}).get('value', '0.00')
        currency = tx_info.get('transaction_amount', {}).get('currency_code', 'USD')
        description = (
            tx_info.get('transaction_subject') or 
            tx_info.get('transaction_note') or 
            "Standard PayPal transfer"
        )
        
        # Run AI categorization
        ai_result = categorize_transaction(description, classifier)
        category = ai_result['category']
        confidence = ai_result['confidence']
        
        # Format for display
        amount_display = f"{amount} {currency}"
        desc_display = (description[:32] + '...') if len(description) > 35 else description
        
        # Print result
        print(f"{amount_display:<15} | {desc_display:<35} | {category:<25} | {confidence:.1%}")
    
    print("-" * 80)
    print("\n✅ Processing complete!")
    
    # Optional: Save results to JSON
    if input("\nWould you like to save results to JSON? (y/n): ").lower() == 'y':
        results = []
        for tx in transactions:
            tx_info = tx.get('transaction_info', {})
            description = (
                tx_info.get('transaction_subject') or 
                tx_info.get('transaction_note') or 
                "Standard PayPal transfer"
            )
            ai_result = categorize_transaction(description, classifier)
            
            results.append({
                "transaction_id": tx_info.get('transaction_id'),
                "amount": tx_info.get('transaction_amount', {}).get('value'),
                "currency": tx_info.get('transaction_amount', {}).get('currency_code'),
                "description": description,
                "ai_category": ai_result['category'],
                "confidence": ai_result['confidence'],
                "status": tx_info.get('transaction_status')
            })
        
        with open('paypal_ai_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print("✅ Results saved to paypal_ai_results.json")


if __name__ == "__main__":
    main()