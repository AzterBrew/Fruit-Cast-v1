from .models import AccountsInformation
from django.utils import timezone

def user_role_id(request):
    user_role_id = None
    account_id = request.session.get('account_id')
    if request.user.is_authenticated and account_id:
        try:
            accinfo = AccountsInformation.objects.get(account_id=account_id)
            user_role_id = accinfo.account_type_id.account_type_id
        except AccountsInformation.DoesNotExist:
            pass
    return {'user_role_id': user_role_id}

def current_year(request):
    """Add current year to template context for footer copyright"""
    return {'current_year': timezone.now().year}