
from django import template

register = template.Library()

@register.filter
def split(value, delimiter=" "):
    """Splits the string by the given delimiter."""
    return value.split(delimiter)

@register.filter
def get_commodity_id(commodity_types, name):
    for c in commodity_types:
        if c.name == name:
            return c.commodity_id
    return ''