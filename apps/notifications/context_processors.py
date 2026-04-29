from .services import unresolved_count


def notifications_badge(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"unresolved_notifications_count": 0}
    return {"unresolved_notifications_count": unresolved_count(user=user)}
