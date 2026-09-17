from django import template

from apps.inquiry.matching import METHOD_LABELS

register = template.Library()


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def score_class(score):
    score = score or 0
    if score >= 90:
        return "bg-emerald-100 text-emerald-800"
    if score >= 75:
        return "bg-sky-100 text-sky-800"
    if score >= 60:
        return "bg-amber-100 text-amber-800"
    return "bg-rose-100 text-rose-800"


@register.filter
def method_label(method):
    return METHOD_LABELS.get(method, {"new": "新建", "": "未匹配"}.get(method, method))


@register.filter
def severity_class(severity):
    return {"high": "bg-rose-100 text-rose-700", "medium": "bg-amber-100 text-amber-700", "low": "bg-slate-100 text-slate-600"}.get(severity, "")
