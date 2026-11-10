"""
Data Formatting Utilities Module
================================

Provides reusable formatting functions for:
- Currency amounts
- Dates and timestamps
- Percentages and confidence scores
- Text truncation
- Risk levels and colors

All functions are pure (no side effects) and thread-safe.

Version: 2.0.0
"""

from datetime import datetime
from typing import Optional, Union


# ==========================================
# CURRENCY FORMATTING
# ==========================================

def format_currency(
    amount: Union[float, int, str],
    currency_code: str = "USD",
    include_symbol: bool = False
) -> str:
    """
    Formats a numeric amount into a clean currency string.
    
    Args:
        amount: Numeric amount (float, int, or string)
        currency_code: ISO currency code (default: USD)
        include_symbol: Whether to include currency symbol (default: False)
    
    Returns:
        Formatted currency string (e.g., "1,234.56 USD" or "$1,234.56")
    
    Examples:
        >>> format_currency(1234.56, "USD")
        '1,234.56 USD'
        >>> format_currency(1234.56, "USD", include_symbol=True)
        '$1,234.56'
        >>> format_currency("invalid", "EUR")
        '0.00 EUR'
    """
    try:
        # Convert to float
        if isinstance(amount, str):
            # Handle strings like "1234.56 USD"
            amount = float(amount.split()[0])
        else:
            amount = float(amount)
        
        # Format with thousands separator and 2 decimal places
        formatted = f"{amount:,.2f}"
        
        if include_symbol:
            symbols = {
                "USD": "$",
                "EUR": "€",
                "GBP": "£",
                "JPY": "¥",
                "CAD": "C$",
                "AUD": "A$"
            }
            symbol = symbols.get(currency_code.upper(), "")
            return f"{symbol}{formatted}"
        else:
            return f"{formatted} {currency_code}"
            
    except (ValueError, TypeError, AttributeError):
        # Fallback for invalid input
        if include_symbol:
            return "$0.00"
        return f"0.00 {currency_code}"


def parse_currency_string(currency_str: str) -> tuple[float, str]:
    """
    Parses a currency string into amount and currency code.
    
    Args:
        currency_str: String like "1,234.56 USD" or "$1,234.56"
    
    Returns:
        Tuple of (amount, currency_code)
    
    Examples:
        >>> parse_currency_string("1,234.56 USD")
        (1234.56, 'USD')
        >>> parse_currency_string("$1,234.56")
        (1234.56, 'USD')
    """
    try:
        # Remove currency symbols
        cleaned = currency_str.replace('$', '').replace('€', '').replace('£', '').strip()
        
        # Split into parts
        parts = cleaned.split()
        
        if len(parts) == 2:
            # Format: "1234.56 USD"
            amount_str = parts[0].replace(',', '')
            currency = parts[1]
        elif len(parts) == 1:
            # Format: "1234.56" (assume USD)
            amount_str = parts[0].replace(',', '')
            currency = "USD"
        else:
            return 0.0, "USD"
        
        amount = float(amount_str)
        return amount, currency
        
    except (ValueError, IndexError):
        return 0.0, "USD"


# ==========================================
# DATE FORMATTING
# ==========================================

def format_date(
    date_input: Union[str, datetime],
    format_str: str = "%b %d, %Y"
) -> str:
    """
    Formats a date into a human-readable string.
    
    Args:
        date_input: Date string (ISO format) or datetime object
        format_str: Output format (default: "Nov 06, 2026")
    
    Returns:
        Formatted date string
    
    Examples:
        >>> format_date("2026-11-06T14:30:00Z")
        'Nov 06, 2026'
        >>> format_date("2026-11-06", "%Y-%m-%d")
        '2026-11-06'
    """
    if not date_input:
        return "N/A"
    
    try:
        # If it's already a datetime object
        if isinstance(date_input, datetime):
            return date_input.strftime(format_str)
        
        # Parse ISO format string
        date_str = str(date_input).strip()
        
        # Handle various ISO formats
        if 'T' in date_str:
            # ISO 8601 with time
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            # Date only
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        return dt.strftime(format_str)
        
    except (ValueError, AttributeError):
        # Return original string if parsing fails
        return str(date_input)


def format_relative_time(date_input: Union[str, datetime]) -> str:
    """
    Formats a date as relative time (e.g., "2 hours ago", "yesterday").
    
    Args:
        date_input: Date string or datetime object
    
    Returns:
        Relative time string
    """
    try:
        if isinstance(date_input, str):
            if 'T' in date_input:
                if date_input.endswith('Z'):
                    date_input = date_input[:-1] + '+00:00'
                dt = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(date_input, "%Y-%m-%d")
        else:
            dt = date_input
        
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt
        
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            return format_date(dt)
            
    except Exception:
        return "unknown"


# ==========================================
# PERCENTAGE FORMATTING
# ==========================================

def format_percentage(
    value: Union[float, int],
    decimals: int = 1,
    multiply_by_100: bool = True
) -> str:
    """
    Formats a decimal value as a percentage string.
    
    Args:
        value: Decimal value (0.0 to 1.0) or percentage (0 to 100)
        decimals: Number of decimal places (default: 1)
        multiply_by_100: Whether to multiply by 100 (default: True)
    
    Returns:
        Formatted percentage string
    
    Examples:
        >>> format_percentage(0.895)
        '89.5%'
        >>> format_percentage(89.5, multiply_by_100=False)
        '89.5%'
        >>> format_percentage(0.895, decimals=2)
        '89.50%'
    """
    try:
        value = float(value)
        
        if multiply_by_100:
            value = value * 100
        
        return f"{value:.{decimals}f}%"
        
    except (ValueError, TypeError):
        return "0.0%"


def format_confidence(confidence: float) -> str:
    """
    Formats an AI confidence score with color-coded indicator.
    
    Args:
        confidence: Confidence score (0.0 to 1.0)
    
    Returns:
        Formatted string with emoji indicator
    """
    try:
        percentage = confidence * 100
        
        if percentage >= 80:
            return f"🟢 {percentage:.1f}%"
        elif percentage >= 60:
            return f"🟡 {percentage:.1f}%"
        else:
            return f"🔴 {percentage:.1f}%"
            
    except (ValueError, TypeError):
        return "🔴 0.0%"


# ==========================================
# TEXT FORMATTING
# ==========================================

def truncate_text(
    text: str,
    max_length: int = 50,
    suffix: str = "..."
) -> str:
    """
    Truncates text to a maximum length with optional suffix.
    
    Args:
        text: Input text
        max_length: Maximum length (default: 50)
        suffix: Suffix to append if truncated (default: "...")
    
    Returns:
        Truncated text
    
    Examples:
        >>> truncate_text("This is a very long description", max_length=20)
        'This is a very lo...'
        >>> truncate_text("Short text", max_length=50)
        'Short text'
    """
    if not text:
        return ""
    
    text = str(text)
    
    if len(text) <= max_length:
        return text
    
    # Calculate available space for text (accounting for suffix)
    available_length = max_length - len(suffix)
    
    if available_length <= 0:
        return suffix[:max_length]
    
    return text[:available_length] + suffix


def clean_text(text: str) -> str:
    """
    Cleans text by removing extra whitespace and normalizing.
    
    Args:
        text: Input text
    
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


# ==========================================
# RISK LEVEL FORMATTING
# ==========================================

def get_risk_color(risk_score: float) -> str:
    """
    Returns a color code based on risk score.
    
    Args:
        risk_score: Risk score (0-100)
    
    Returns:
        Hex color code
    """
    try:
        risk_score = float(risk_score)
        
        if risk_score >= 80:
            return "#dc3545"  # Red - Critical
        elif risk_score >= 60:
            return "#fd7e14"  # Orange - High
        elif risk_score >= 40:
            return "#ffc107"  # Yellow - Medium
        else:
            return "#28a745"  # Green - Low
            
    except (ValueError, TypeError):
        return "#6c757d"  # Gray - Unknown


def get_risk_emoji(risk_score: float) -> str:
    """
    Returns an emoji based on risk score.
    
    Args:
        risk_score: Risk score (0-100)
    
    Returns:
        Emoji string
    """
    try:
        risk_score = float(risk_score)
        
        if risk_score >= 80:
            return "🔴"
        elif risk_score >= 60:
            return "🟠"
        elif risk_score >= 40:
            return "🟡"
        else:
            return "🟢"
            
    except (ValueError, TypeError):
        return "⚪"


def format_risk_level(risk_score: float) -> str:
    """
    Formats a risk score with emoji and level name.
    
    Args:
        risk_score: Risk score (0-100)
    
    Returns:
        Formatted string like "🟢 LOW (25.5)"
    """
    try:
        risk_score = float(risk_score)
        emoji = get_risk_emoji(risk_score)
        
        if risk_score >= 80:
            level = "CRITICAL"
        elif risk_score >= 60:
            level = "HIGH"
        elif risk_score >= 40:
            level = "MEDIUM"
        else:
            level = "LOW"
        
        return f"{emoji} {level} ({risk_score:.1f})"
        
    except (ValueError, TypeError):
        return "⚪ UNKNOWN (0.0)"


# ==========================================
# NUMBER FORMATTING
# ==========================================

def format_large_number(number: Union[int, float]) -> str:
    """
    Formats large numbers with K, M, B suffixes.
    
    Args:
        number: Number to format
    
    Returns:
        Formatted string
    
    Examples:
        >>> format_large_number(1234)
        '1.2K'
        >>> format_large_number(1234567)
        '1.2M'
        >>> format_large_number(1234567890)
        '1.2B'
    """
    try:
        number = float(number)
        
        if number >= 1_000_000_000:
            return f"{number / 1_000_000_000:.1f}B"
        elif number >= 1_000_000:
            return f"{number / 1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number / 1_000:.1f}K"
        else:
            return f"{number:.0f}"
            
    except (ValueError, TypeError):
        return "0"