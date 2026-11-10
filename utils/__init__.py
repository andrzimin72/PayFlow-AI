"""
Utilities Package for PayFlow AI
=================================

Provides reusable utility functions for:
- Currency formatting and parsing
- Date and timestamp formatting
- Percentage and confidence score formatting
- Text truncation and cleaning
- Risk level visualization (colors, emojis)
- Large number formatting (K, M, B)

All functions are pure (no side effects), thread-safe, and include
comprehensive error handling with sensible fallbacks.

Example Usage:
    from utils import format_currency, format_percentage, truncate_text
    
    # Format currency
    print(format_currency(1234.56, "USD"))  # "1,234.56 USD"
    
    # Format percentage
    print(format_percentage(0.895))  # "89.5%"
    
    # Truncate text
    print(truncate_text("Long description...", max_length=20))
"""

from utils.formatters import (
    # Currency formatting
    format_currency,
    parse_currency_string,
    
    # Date formatting
    format_date,
    format_relative_time,
    
    # Percentage formatting
    format_percentage,
    format_confidence,
    
    # Text formatting
    truncate_text,
    clean_text,
    
    # Risk level formatting
    get_risk_color,
    get_risk_emoji,
    format_risk_level,
    
    # Number formatting
    format_large_number,
)

# Package metadata
__version__ = "2.0.0"
__author__ = "Andre Zimin"
__license__ = "Apache-2.0"

# Public API
__all__ = [
    # Currency
    "format_currency",
    "parse_currency_string",
    
    # Date
    "format_date",
    "format_relative_time",
    
    # Percentage
    "format_percentage",
    "format_confidence",
    
    # Text
    "truncate_text",
    "clean_text",
    
    # Risk
    "get_risk_color",
    "get_risk_emoji",
    "format_risk_level",
    
    # Numbers
    "format_large_number",
    
    # Metadata
    "__version__",
    "__author__",
    "__license__",
]
