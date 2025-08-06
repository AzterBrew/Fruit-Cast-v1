from django import template
from django.utils.html import format_html
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag
def sort_header(field, label, current_sort, current_order, current_status=None):
    new_order = 'desc' if current_sort == field and current_order == 'asc' else 'asc'
    
    query_params = {'sort': field, 'order': new_order}
    if current_status:
        query_params['status'] = current_status

    arrow = ''
    if current_sort == field:
        arrow = '▲' if current_order == 'asc' else '▼'

    url = '?' + urlencode(query_params)
    return format_html('<a href="{}">{} {}</a>', url, label, arrow)
