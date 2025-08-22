from django.utils import timezone
from dashboard.models import Notification

def unread_notifications(request):
    if not request.user.is_authenticated:
        return {}
    account_id = request.session.get('account_id')
    if not account_id:
        return {}
    notifications_qs = Notification.objects.filter(
        account__account_id=account_id,
        scheduled_for__lte=timezone.now()
    ).order_by('-created_at')
    notifications = notifications_qs[:10]
    unread_count = notifications_qs.filter(is_read=False).count()
    return {
        'notifications': notifications,
        'unread_count': unread_count,
    }