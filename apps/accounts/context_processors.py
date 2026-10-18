from django.conf import settings


def debug_flag(request):
    return {"debug": settings.DEBUG}


NAV_SECTIONS = (
    ("/appointments", "appointments"),
    ("/files", "files"),
    ("/baby/logs", "logs"),
    ("/baby/kick-counter", "kicks"),
    ("/baby/birth-plan", "birth_plan"),
    ("/notifications", "notifications"),
    ("/accounts/profile", "profile"),
)


def nav_section(request):
    if request.path == "/":
        return {"nav_section": "home"}
    return {"nav_section": next((name for prefix, name in NAV_SECTIONS if request.path.startswith(prefix)), None)}
