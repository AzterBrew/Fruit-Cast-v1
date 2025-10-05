from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def format_weight(value):
    """Format a number with commas and 2 decimal places"""
    if value is None:
        return "0.00"
    try:
        # Convert to float first to handle Decimal objects
        num_value = float(value)
        return f"{num_value:,.2f}"
    except (ValueError, TypeError):
        return "0.00"