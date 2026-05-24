from django import template

register = template.Library()


@register.filter
def get_attr(obj, attr):
    value = getattr(obj, attr, '')
    if callable(value):
        try:
            return value()
        except TypeError:
            return value
    return value
