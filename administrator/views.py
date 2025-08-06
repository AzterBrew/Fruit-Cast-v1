from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from base.models import AuthUser, UserInformation, AdminInformation, AccountsInformation, AccountStatus, AccountType, MunicipalityName, BarangayName
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from base.forms import EditUserInformation
from django.utils import timezone
from django.utils.timezone import now
from .forms import AssignAdminAgriForm
from django.db import transaction
from django.core.mail import send_mail
from django.contrib import messages
from django.utils.crypto import get_random_string


def admin_login(request):
    if request.method == 'POST':
        email_or_contact = request.POST.get('email_or_contact')
        password = request.POST.get('password')

        # Authenticate with Django's auth_user
        user = authenticate(request, username=email_or_contact, password=password)

        if user is not None:
            # THESIS1
            # # Allow superuser immediately
            # if user.is_superuser:
            #     login(request, user)
            #     return redirect('administrator:dashboard')

            # # Otherwise, try to validate via UserInformation + AdminInformation
            # try:
            #     user_info = UserInformation.objects.get(auth_user=user)

            #     if AdminInformation.objects.filter(userinfo_id=user_info).exists():
            #         login(request, user)
            #         return redirect('administrator:dashboard')
            #     else:
            #         messages.error(request, "Unauthorized: This account is not an admin.")
            # except UserInformation.DoesNotExist:
            #     messages.error(request, "No user profile found for this account.")
            
            # THESIS2
            if user.is_superuser:
                login(request, user)
                return redirect('administrator:dashboard')

            try:
                user_info = UserInformation.objects.get(auth_user=user)
                account_info = AccountsInformation.objects.get(userinfo_id=user_info)

                if account_info.account_type_id.account_type.lower() in ['administrator', 'agriculturist']:
                    login(request, user)
                    return redirect('administrator:dashboard')
                else:
                    messages.error(request, "Unauthorized: Your account does not have admin privileges.")
            except (UserInformation.DoesNotExist, AccountsInformation.DoesNotExist):
                messages.error(request, "User profile or account info not found.")
                
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
        account_info = AccountsInformation.objects.get(userinfo_id=user_info)

        if account_info.account_type_id.account_type.lower() in ['administrator', 'agriculturist']:
            return render(request, 'admin_panel/admin_dashboard.html')
        else:
            return HttpResponseForbidden("You are not authorized to access this page.")
        
    except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
        return HttpResponseForbidden("You are not authorized to access this page.")

    return render(request, 'admin_panel/admin_dashboard.html')

# @login_required
# def verify_accounts(request):
#     # Show only accounts with status = 3 (Pending)
#     pending_accounts = AccountsInformation.objects.filter(item_status_id=3)

#     status_choices = AccountStatus.objects.all()

#     return render(request, 'admin_panel/verify_accounts.html', {
#         'pending_accounts': pending_accounts,
#         'status_choices': status_choices,
#     })

@login_required
def update_account_status(request, account_id):
    if request.method == 'POST':
        account = get_object_or_404(AccountsInformation, pk=account_id)
        new_status_id = int(request.POST.get('status'))

        account.acc_status_id = new_status_id
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
    # this is the view for the verify accounts page which is the farmers list
    pending_accounts = AccountsInformation.objects.filter(acc_status_id=2).select_related('userinfo_id', 'account_type_id', 'acc_status_id')    
    print(pending_accounts)
    
    
    status_filter = request.GET.get('status')
    municipality_filter = request.GET.get('municipality')
    sort_by = request.GET.get('sort', 'account_register_date')  # Default sort by date
    order = request.GET.get('order', 'asc')  # 'asc' or 'desc'

    accounts_query = AccountsInformation.objects.filter(account_type_id=1).select_related('userinfo_id', 'account_type_id', 'acc_status_id')

    if status_filter:
        accounts_query = accounts_query.filter(acc_status_id=status_filter)
        
    if municipality_filter:
        accounts_query = accounts_query.filter(userinfo_id__municipality_id__municipality=municipality_filter)

    # Determine sort field and order
    if sort_by == 'name':
        sort_field = 'userinfo_id__lastname'
    elif sort_by == 'date':
        sort_field = 'account_register_date'
    else:
        sort_field = sort_by

    if order == 'desc':
        sort_field = '-' + sort_field

    all_accounts = accounts_query.order_by(sort_field)

    # Pass status choices for filter dropdown
    status_choices = AccountStatus.objects.all()
    municipalities = MunicipalityName.objects.all()

    return render(request, 'admin_panel/verify_accounts.html', {
        'accounts': all_accounts,
        'status_choices': status_choices,
        'municipalities': municipalities,
        'current_status': status_filter,
        'current_municipality': municipality_filter,
        'current_sort': sort_by,
        'current_order': order,
    })


def verify_account_action(request, account_id):
    if request.method == 'POST':
        account = get_object_or_404(AccountsInformation, pk=account_id)
        active_status = get_object_or_404(AccountStatus, pk=3)  # 3 = Pending
        admin_user = AdminInformation.objects.get(admin_user=request.user)  # Assuming this links to auth user

        account.acc_status_id = active_status
        account.account_verified_date = now()
        account.account_isverified = True
        account.account_verified_by = admin_user
        account.save()

        return redirect('verify_accounts')

def show_allaccounts(request):
    user_info = request.user.userinformation
    account_info = AccountsInformation.objects.get(userinfo_id=user_info)
    if account_info.account_type_id.account_type != 'Administrator':
        return HttpResponseForbidden("You don't have access to this page.")
        
    status_filter = request.GET.get('status')
    sort_by = request.GET.get('sort', 'account_register_date')  # Default sort by date
    order = request.GET.get('order', 'asc')  # 'asc' or 'desc'

    accounts_query = AccountsInformation.objects.select_related(
    'userinfo_id', 'account_type_id', 'acc_status_id').filter(account_type_id__account_type__in=["Administrator", "Agriculturist"])

    if status_filter:
        accounts_query = accounts_query.filter(acc_status_id=status_filter)

    account_type_filter = request.GET.get('acctype')  # name from the new dropdown

    if account_type_filter:
        accounts_query = accounts_query.filter(account_type_id=account_type_filter)

    municipality_filter = request.GET.get('municipality')

    if municipality_filter:
        accounts_query = accounts_query.filter(userinfo_id__municipality_id__municipality=municipality_filter)
        
    # Determine sort field and order
    if sort_by == 'name':
        sort_field = 'userinfo_id__lastname'
    elif sort_by == 'date':
        sort_field = 'account_register_date'
    else:
        sort_field = sort_by

    if order == 'desc':
        sort_field = '-' + sort_field

    all_accounts = accounts_query.order_by(sort_field)

    # Pass status choices for filter dropdown
    status_choices = AccountStatus.objects.all()
    municipalities = MunicipalityName.objects.all()

    return render(request, 'admin_panel/show_allaccounts.html', {
        'allAccounts': all_accounts,
        'account_types': AccountType.objects.exclude(account_type='Farmer'),
        'status_choices': status_choices,
        'municipalities': municipalities,
        'current_municipality': municipality_filter,
        'current_status': status_filter,
        'current_acctype': account_type_filter,
        'current_sort': sort_by,
        'current_order': order,
    })

@require_POST
def change_account_type(request, account_id):
    user_info = request.user.userinformation
    account_info = AccountsInformation.objects.get(userinfo_id=user_info)
    if account_info.account_type_id.account_type != 'Administrator':
        return HttpResponseForbidden("You don't have permission to perform this action.")

    account = get_object_or_404(AccountsInformation, pk=account_id)
    new_type_id = request.POST.get('new_type')

    if account.account_type_id.account_type == "Agriculturist":
        new_type = get_object_or_404(AccountType, pk=new_type_id)
        account.account_type_id = new_type
        account.save()
        messages.success(request, "Account type updated successfully.")
    else:
        messages.warning(request, "Only Agriculturist accounts can be updated.")

    return redirect('administrator:show_allaccounts')  # or wherever the list view lives


def assign_account(request):
    user = request.user

    if not user.is_superuser:
        return HttpResponseForbidden("Only superusers may assign accounts.")

    if request.method == 'POST':
        form = AssignAdminAgriForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            first_name = form.cleaned_data['first_name']
            middle_name = form.cleaned_data['middle_name']
            last_name = form.cleaned_data['last_name']
            sex = form.cleaned_data['sex']
            account_type = form.cleaned_data['account_type']
            municipality = form.cleaned_data.get('municipality')  # Required only for agriculturist

            # Check if email already exists
            if AuthUser.objects.filter(email=email).exists():
                form.add_error('email', 'Email already exists in the system.')
            else:
                try:
                    with transaction.atomic():
                        # Generate a strong password
                        generated_password = get_random_string(length=12)

                        # This is for creating records, itesting ko muna emailing
                        
                        # Create AuthUser
                        new_auth = AuthUser.objects.create_user(email=email, password=generated_password)

                        # Create UserInformation
                        userinfo = UserInformation.objects.create(
                            auth_user=new_auth,
                            lastname=last_name,
                            firstname=first_name,
                            middlename=middle_name,
                            nameextension="",
                            sex=sex,
                            contact_number="",  # placeholder, can be updated later
                            user_email=email,
                            birthdate="2000-01-01",  # placeholder, adjust based on form
                            emergency_contact_person="",
                            emergency_contact_number="",
                            address_details="",
                            barangay_id=BarangayName.objects.first(),  # or make user pick
                            municipality_id=municipality,
                            religion="",
                            civil_status="",
                        )

                        # Create AccountsInformation
                        acct_type = AccountType.objects.get(account_type=account_type)
                        acct_status = AccountStatus.objects.get(acc_status="Pending")
                        account_info = AccountsInformation.objects.create(
                            userinfo_id=userinfo,
                            account_type_id=acct_type,
                            acc_status_id=acct_status,
                            account_register_date=timezone.now()
                        )

                        # Create AdminInformation (even for agriculturist)
                        AdminInformation.objects.create(
                            userinfo_id=userinfo,
                            municipality_incharge=municipality
                        )

                        # Send email with credentials
                        
                        # EMAIL TESTING
                        
                        
                        email_sent = send_mail(
                            subject="Fruit Cast Admin Account Created",
                            message=f"Hello {first_name},\n\nYour admin account has been created.\nEmail: {email}\nPassword: {generated_password}\n\nPlease log in and change your password.",
                            from_email="eloisamariemsumbad@gmail.com",
                            recipient_list=[email],
                            fail_silently=False,
                        )

                        if email_sent:
                            messages.success(request, f"Admin/Agriculturist account for {email} created successfully.")
                            return redirect('administrator:assign_account')
                        else:
                            raise Exception("Failed to send email. Account creation aborted.")

                except Exception as e:
                    form.add_error(None, f"Something went wrong: {e}")
    else:
        form = AssignAdminAgriForm()

    return render(request, 'admin_panel/assign_admin_agriculturist.html', {
        'form': form
    })

    


def accinfo(request):
    print("🔥 DEBUG: account view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            account_id = request.session.get('account_id')
            userinfo_id = request.session.get('userinfo_id')
            if userinfo_id and account_id:
                userinfo = UserInformation.objects.get(pk=userinfo_id)
                account_info = AccountsInformation.objects.get(pk=account_id)
                context = {
                    'user_firstname': userinfo.firstname,
                    # ...other fields...
                    'user_role_id': accinfo.account_type_id.account_type_id,
                }
                return render(request, 'loggedin/account_info.html', context)
            else:
                return redirect('administrator:dashboard')
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home') #dapat redirect si user sa guest home
    else :
        return render(request, 'home.html', {})   
    
    

def editacc(request):
    print("🔥 DEBUG: editacc view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        userinfo_id = request.session.get('userinfo_id')
        userinfo = UserInformation.objects.get(pk=userinfo_id)
        
        context = {
                'user_firstname' : userinfo.firstname,
            } 
        
        if request.method == "POST":
            form = EditUserInformation(request.POST,instance=userinfo)
            if form.is_valid():
                updated_info = form.save(commit=False)
                updated_info.auth_user = request.user
                updated_info.save()
                
                request.user.email = updated_info.user_email
                request.user.save()
                
                return redirect('administrator:accinfo')                
        
        else:
            form = EditUserInformation(instance=userinfo)

        return render(request, 'loggedin/account_edit.html', {'form': form})
    else :
        return render(request, 'home.html', {})  