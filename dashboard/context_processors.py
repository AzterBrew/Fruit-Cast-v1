from django.utils import timezone
from dashboard.models import Notification

def unread_notifications(request):
    if not request.user.is_authenticated:
        return {}
    account_id = request.session.get('account_id')
    if not account_id:
        return {}
    notifications = Notification.objects.filter(
        account__account_id=account_id,
        is_read=False,
        scheduled_for__lte=timezone.now()
    ).order_by('-created_at')[:10]
    unread_count = notifications.count()
    return {
        'notifications': notifications,
        'unread_count': unread_count,
    }