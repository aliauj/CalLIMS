from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def module_enabled(context, module_name):
    """Returns True if the module is included in the current license."""
    return module_name in context.get('enabled_modules', [])


@register.filter
def days_label(n):
    """Return a human label for days remaining."""
    if n < 0:
        return 'Expired'
    if n == 0:
        return 'Expires today'
    if n == 1:
        return '1 day remaining'
    return f'{n} days remaining'
