from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from base.models import AccountsInformation, UserInformation

def admin_or_agriculturist_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('base:login')
        try:
            user_info = UserInformation.objects.get(auth_user=request.user)
            account_info = AccountsInformation.objects.get(userinfo_id=user_info)
            role = account_info.account_type_id.account_type.lower()
            if role in ['administrator', 'agriculturist'] or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
        except (UserInformation.DoesNotExist, AccountsInformation.DoesNotExist):
            pass
        return HttpResponseForbidden("You do not have permission to access this page.")
    return _wrapped_view

def superuser_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        print("User is not a superuser.")
        return HttpResponseForbidden("You do not have permission to access this page.")
    return _wrapped_view