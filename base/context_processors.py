from .models import AccountsInformation

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