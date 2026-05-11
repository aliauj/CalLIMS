from .models import Notification


def notifications(request):
    if not request.user.is_authenticated:
        return {}
    qs = Notification.objects.filter(recipient=request.user, is_read=False)
    return {
        'unread_notification_count': qs.count(),
        'recent_notifications': qs[:5],
    }
