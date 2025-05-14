from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from base.models import AuthUser, UserInformation, AdminInformation
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from base.models import AccountsInformation, ItemStatus
from django.utils import timezone
from django.utils.timezone import now

def admin_login(request):
    if request.method == 'POST':
        email_or_contact = request.POST.get('email_or_contact')
        password = request.POST.get('password')

        # Authenticate with Django's auth_user
        user = authenticate(request, username=email_or_contact, password=password)

        if user is not None:
            # Allow superuser immediately
            if user.is_superuser:
                login(request, user)
                return redirect('administrator:dashboard')

            # Otherwise, try to validate via UserInformation + AdminInformation
            try:
                user_info = UserInformation.objects.get(auth_user=user)

                if AdminInformation.objects.filter(userinfo_id=user_info).exists():
                    login(request, user)
                    return redirect('administrator:dashboard')
                else:
                    messages.error(request, "Unauthorized: This account is not an admin.")
            except UserInformation.DoesNotExist:
                messages.error(request, "No user profile found for this account.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'admin_login/login.html')


@login_required
def admin_dashboard(request):
    user = request.user

    if user.is_superuser:
        return render(request, 'admin_panel/admin_dashboard.html')  # or something similar

    try:
        user_info = UserInformation.objects.get(auth_user=user)
        admin_info = AdminInformation.objects.get(userinfo_id=user_info)
    except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
        return HttpResponseForbidden("You are not authorized to access this page.")

    return render(request, 'admin_panel/admin_dashboard.html')

# @login_required
# def verify_accounts(request):
#     # Show only accounts with status = 3 (Pending)
#     pending_accounts = AccountsInformation.objects.filter(item_status_id=3)

#     status_choices = ItemStatus.objects.all()

#     return render(request, 'admin_panel/verify_accounts.html', {
#         'pending_accounts': pending_accounts,
#         'status_choices': status_choices,
#     })

@login_required
def update_account_status(request, account_id):
    if request.method == 'POST':
        account = get_object_or_404(AccountsInformation, pk=account_id)
        new_status_id = int(request.POST.get('status'))

        account.item_status_id_id = new_status_id
        account.account_isverified = new_status_id == 1  # If Active
        account.account_verified_date = timezone.now()

        # Link the admin who verified
        try:
            user_info = UserInformation.objects.get(auth_user=request.user)
            admin = AdminInformation.objects.get(userinfo_id=user_info)
            account.account_verified_by = admin
        except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
            pass  # Skip linking if not a recognized admin

        account.save()
        return redirect('administrator:verify_accounts')
    
def verify_accounts(request):
    pending_accounts = AccountsInformation.objects.filter(item_status_id=3).select_related('userinfo_id', 'account_type_id', 'item_status_id')    
    print(pending_accounts)
    return render(request, 'admin_panel/verify_accounts.html', {'accounts': pending_accounts})


def verify_account_action(request, account_id):
    if request.method == 'POST':
        account = get_object_or_404(AccountsInformation, pk=account_id)
        active_status = get_object_or_404(ItemStatus, pk=1)  # 1 = Active
        admin_user = AdminInformation.objects.get(admin_user=request.user)  # Assuming this links to auth user

        account.item_status_id = active_status
        account.account_verified_date = now()
        account.account_isverified = True
        account.account_verified_by = admin_user
        account.save()

        return redirect('verify_accounts')

def show_allaccounts(request):
    allAccounts = AccountsInformation.objects.get()  # 3 = Pending
    return render(request, 'admin_panel/verify_accounts.html', {'allAccounts': allAccounts})