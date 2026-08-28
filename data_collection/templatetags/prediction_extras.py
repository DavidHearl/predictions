from django import template

register = template.Library()


@register.filter
def percent(value, decimals=0):
    """0.614 -> '61%'"""
    try:
        return f"{float(value) * 100:.{int(decimals)}f}%"
    except (TypeError, ValueError):
        return "–"


@register.filter
def signed_percent(value, decimals=1):
    """0.083 -> '+8.3%', -0.02 -> '-2.0%'"""
    try:
        v = float(value) * 100
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.{int(decimals)}f}%"
    except (TypeError, ValueError):
        return "–"


@register.filter
def times100(value):
    try:
        return float(value) * 100
    except (TypeError, ValueError):
        return 0
