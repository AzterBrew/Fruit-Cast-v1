from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def format_number(value):
    """Format a number with commas and 2 decimal places"""
    if value is None:
        return '0'
    try:
        # Convert to float first to handle various input types
        num = float(value)
        # Format with commas, no decimal places for integers, 2 for floats
        if num == int(num):
            return f"{int(num):,}"
        else:
            return f"{num:,.2f}"
    except (ValueError, TypeError):
        return str(value)

@register.filter 
def raw_number(value):
    """Return raw number without comma formatting - for CSV exports"""
    if value is None:
        return '0'
    try:
        num = float(value)
        if num == int(num):
            return str(int(num))
        else:
            return f"{num:.2f}"
    except (ValueError, TypeError):
        return str(value)