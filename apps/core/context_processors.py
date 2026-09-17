from django.conf import settings


def site(request):
    return {
        "AI_MOCK": settings.AI_MOCK,
        "LLM_MODEL": settings.LLM_MODEL,
    }
