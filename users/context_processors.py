from .models import Notification


def notifications(request):
    """
    Makes notification data available in all templates.
    Keep it lightweight: unread count + latest few notifications.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "notifications_unread_count": 0,
            "notifications_latest": [],
        }

    qs = Notification.objects.filter(recipient=user).only(
        "id", "title", "message", "target_url", "is_read", "created_at"
    )

    return {
        "notifications_unread_count": qs.filter(is_read=False).count(),
        "notifications_latest": list(qs[:5]),
    }

