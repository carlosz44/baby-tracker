from django.conf import settings


def debug_flag(request):
    return {"debug": settings.DEBUG}
