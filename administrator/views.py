from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from base.models import AuthUser, UserInformation, AdminInformation, AccountsInformation, AccountStatus, AccountType, MunicipalityName, BarangayName, CommodityType, Month, initHarvestRecord, initPlantRecord, FarmLand, RecordTransaction
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from base.forms import EditUserInformation
from django.utils import timezone
from django.utils.timezone import now
from .forms import AssignAdminAgriForm, CommodityTypeForm, VerifiedHarvestRecordForm
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from .decorators import admin_or_agriculturist_required, superuser_required
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from dashboard.models import ForecastBatch, ForecastResult, VerifiedHarvestRecord, VerifiedPlantRecord
from prophet import Prophet
import pandas as pd
from django.db.models import Q, Count
from datetime import datetime, date
from calendar import monthrange
from shapely.geometry import shape
import csv, io, joblib, json, os, logging
from django.core.paginator import Paginator
from collections import OrderedDict
from pathlib import Path
from django.core.management import call_command
from .tasks import retrain_and_generate_forecasts_task
from django.core.files.storage import default_storage
from django.contrib.contenttypes.models import ContentType
from base.models import AdminUserManagement

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from dateutil.relativedelta import relativedelta 

def get_admin_context(request):
    """Helper function to get admin context data"""
    context = {}
    if request.user.is_authenticated:
        try:
            user_info = UserInformation.objects.get(auth_user=request.user)
            account_info = AccountsInformation.objects.get(userinfo_id=user_info)
            context.update({
                'user_firstname': user_info.firstname,
                'user_role_id': account_info.account_type_id.account_type_id,
            })
        except (UserInformation.DoesNotExist, AccountsInformation.DoesNotExist):
            pass
    return context 

def admin_login(request):
    if request.method == 'POST':
        
        email_or_contact = request.POST.get('email_or_contact')
        password = request.POST.get('password')

        # Authenticate with Django's auth_user
        user = authenticate(request, username=email_or_contact, password=password)

        if user is not None:    
            if user.is_superuser:
                login(request, user)
                # Set session variables for context processor
                try:
                    user_info = UserInformation.objects.get(auth_user=user)
                    account_info = AccountsInformation.objects.get(userinfo_id=user_info)
                    request.session['userinfo_id'] = user_info.pk
                    request.session['account_id'] = account_info.pk
                except (UserInformation.DoesNotExist, AccountsInformation.DoesNotExist):
                    pass
                return redirect('administrator:dashboard')

            try:
                user_info = UserInformation.objects.get(auth_user=user)
                account_info = AccountsInformation.objects.get(userinfo_id=user_info)
                if account_info.account_type_id.account_type.lower() in ['administrator', 'agriculturist']:
                    login(request, user)
                    # Set session variables for context processor
                    request.session['userinfo_id'] = user_info.pk
                    request.session['account_id'] = account_info.pk
                    return redirect('administrator:dashboard')
                else:
                    messages.error(request, "Unauthorized: Your account does not have admin privileges.")
            except (UserInformation.DoesNotExist, AccountsInformation.DoesNotExist):
                messages.error(request, "User profile or account info not found.")
                
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'admin_login/login.html')


@login_required
@admin_or_agriculturist_required
def admin_dashboard(request):
    user = request.user
    context = get_admin_context(request)

    if user.is_superuser:
        return render(request, 'admin_panel/admin_dashboard.html', context)

    try:
        user_info = UserInformation.objects.get(auth_user=user)
        account_info = AccountsInformation.objects.get(userinfo_id=user_info)

        if account_info.account_type_id.account_type.lower() in ['administrator', 'agriculturist']:
            return render(request, 'admin_panel/admin_dashboard.html', context)
        else:
            return HttpResponseForbidden("You are not authorized to access this page.")
        
    except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
        return HttpResponseForbidden("You are not authorized to access this page.")

    return render(request, 'admin_panel/admin_dashboard.html', context)

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

@admin_or_agriculturist_required    
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


    accounts_query = accounts_query.annotate(record_count=Count('recordtransaction'))

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
    
    if request.method == 'POST':
        selected_ids = [sid for sid in request.POST.getlist('selected_records') if sid]
        new_status_id = request.POST.get('new_status')
        admin_info = AdminInformation.objects.filter(userinfo_id=request.user.userinformation).first()
        if selected_ids and new_status_id and admin_info:
            for acc in AccountsInformation.objects.filter(pk__in=selected_ids):
                acc.acc_status_id_id = new_status_id
                acc.account_verified_by = admin_info
                if int(new_status_id) == 2:  # 2 = Verified
                    acc.account_isverified = True
                else:
                    acc.account_isverified = False
                acc.save()
            messages.success(request, f"Updated {len(selected_ids)} account(s).")
            return redirect('administrator:verify_accounts')
    
    # Pass status choices for filter dropdown
    status_choices = AccountStatus.objects.all()
    municipalities = MunicipalityName.objects.all()
    
    context = get_admin_context(request)
    context.update({
        'accounts': all_accounts,
        'status_choices': status_choices,
        'municipalities': municipalities,
        'current_status': status_filter,
        'current_municipality': municipality_filter,
        'current_sort': sort_by,
        'current_order': order,
    })

    return render(request, 'admin_panel/verify_accounts.html', context)

# @admin_or_agriculturist_required
# def verify_account_action(request, account_id):
#     if request.method == 'POST':
#         account = get_object_or_404(AccountsInformation, pk=account_id)
#         active_status = get_object_or_404(AccountStatus, pk=3)  # 3 = Pending
#         admin_user = AdminInformation.objects.get(admin_user=request.user)  # Assuming this links to auth user

#         account.acc_status_id = active_status
#         account.account_verified_date = now()
#         account.account_isverified = True
#         account.account_verified_by = admin_user
#         account.save()

#         return redirect('verify_accounts')

@admin_or_agriculturist_required
def show_allaccounts(request):
    user_info = request.user.userinformation
    account_info = AccountsInformation.objects.get(userinfo_id=user_info)
        
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
    
    if request.method == 'POST':
        selected_ids = [sid for sid in request.POST.getlist('selected_records') if sid]
        new_status_id = request.POST.get('new_status')
        admin_info = AdminInformation.objects.filter(userinfo_id=request.user.userinformation).first()
        if selected_ids and new_status_id and admin_info:
            for acc in AccountsInformation.objects.filter(pk__in=selected_ids):
                acc.acc_status_id_id = new_status_id
                acc.account_verified_by = admin_info
                if int(new_status_id) == 2:  # 2 = Verified
                    acc.account_isverified = True
                else:
                    acc.account_isverified = False
                acc.save()
            messages.success(request, f"Updated {len(selected_ids)} account(s).")
            return redirect('administrator:show_allaccounts')

    # Pass status choices for filter dropdown
    status_choices = AccountStatus.objects.all()
    municipalities = MunicipalityName.objects.all()
    
    context = get_admin_context(request)
    context.update({
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

    return render(request, 'admin_panel/show_allaccounts.html', context)

@admin_or_agriculturist_required
@require_POST
def change_account_type(request, account_id):
    user_info = request.user.userinformation
    account_info = AccountsInformation.objects.get(userinfo_id=user_info)

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

@admin_or_agriculturist_required
def farmer_transaction_history(request, account_id):
    """View to display transaction history for a specific farmer account"""
    context = get_admin_context(request)
    
    try:
        # Get the farmer's account information
        farmer_account = AccountsInformation.objects.get(
            pk=account_id, 
            account_type_id=1  # Ensure it's a farmer account
        )
        
        # Get all transactions for this farmer
        transactions = RecordTransaction.objects.filter(
            account_id=farmer_account
        ).order_by('-transaction_date')
        
        # Get farmer's farm lands
        farm_lands = FarmLand.objects.filter(
            userinfo_id=farmer_account.userinfo_id
        ).select_related('municipality', 'barangay')
        
        # Calculate age from birthdate
        today = date.today()
        birthdate = farmer_account.userinfo_id.birthdate
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        
        context.update({
            'farmer_account': farmer_account,
            'transactions': transactions,
            'farmer_name': f"{farmer_account.userinfo_id.firstname} {farmer_account.userinfo_id.lastname}",
            'farmer_info': farmer_account.userinfo_id,
            'farm_lands': farm_lands,
            'farmer_age': age
        })
        
    except AccountsInformation.DoesNotExist:
        messages.error(request, "Farmer account not found.")
        return redirect('administrator:verify_accounts')
    
    return render(request, 'admin_panel/farmer_transaction_history.html', context)

@admin_or_agriculturist_required
def farmer_transaction_detail(request, transaction_id):
    """View to display detailed information for a specific transaction"""
    context = get_admin_context(request)
    
    try:
        # Get the transaction with related data
        transaction = RecordTransaction.objects.select_related(
            'account_id__userinfo_id',
            'farm_land__municipality',
            'farm_land__barangay',
            'manual_municipality',
            'manual_barangay'
        ).get(pk=transaction_id)
        
        # Ensure the transaction belongs to a farmer account
        if transaction.account_id.account_type_id.pk != 1:
            messages.error(request, "Transaction not found or access denied.")
            return redirect('administrator:verify_accounts')
        
        # Get plant record if exists
        plant_record = None
        try:
            plant_record = initPlantRecord.objects.select_related(
                'commodity_id', 'record_status'
            ).get(transaction=transaction)
        except initPlantRecord.DoesNotExist:
            pass
        
        # Get harvest records if exist
        harvest_records = initHarvestRecord.objects.select_related(
            'commodity_id', 'unit', 'record_status'
        ).filter(transaction=transaction)
        
        # Get notification if exists for plant record
        plant_notification = None
        if plant_record:
            from dashboard.models import Notification
            try:
                plant_notification = Notification.objects.filter(
                    account=transaction.account_id,
                    linked_plant_record=plant_record
                ).first()
            except:
                pass
        
        farmer_name = f"{transaction.account_id.userinfo_id.firstname} {transaction.account_id.userinfo_id.lastname}"
        
        context.update({
            'transaction': transaction,
            'plant_record': plant_record,
            'harvest_record': harvest_records,
            'plant_notification': plant_notification,
            'farmer_name': farmer_name,
            'farmer_account': transaction.account_id
        })
        
    except RecordTransaction.DoesNotExist:
        messages.error(request, "Transaction not found.")
        return redirect('administrator:verify_accounts')
    
    return render(request, 'admin_panel/farmer_transaction_detail.html', context)

@admin_or_agriculturist_required
@superuser_required
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

    context = get_admin_context(request)
    context.update({
        'form': form
    })

    return render(request, 'admin_panel/assign_admin_agriculturist.html', context)


@login_required
@admin_or_agriculturist_required
def admin_forecast(request):
    if not request.user.is_authenticated:
        return render(request, 'home.html', {})

    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    if not (userinfo_id and account_id):
        return redirect('home')

    userinfo = UserInformation.objects.get(pk=userinfo_id)
    commodity_types = CommodityType.objects.exclude(pk=1)
    all_municipalities = MunicipalityName.objects.exclude(pk=14)

    selected_commodity_id = None
    selected_municipality_id = None

    if request.GET.get('commodity_id'):
        selected_commodity_id = request.GET.get('commodity_id')
        selected_commodity_obj = CommodityType.objects.get(pk=selected_commodity_id)
    else :
        selected_commodity_id = commodity_types.first().commodity_id if commodity_types.exists() else None
        selected_commodity_obj = CommodityType.objects.get(pk=selected_commodity_id)
        
    if request.GET.get('municipality_id'):
        selected_municipality_id = request.GET.get('municipality_id')
        selected_municipality_obj = MunicipalityName.objects.get(pk=selected_municipality_id)
    else:
        selected_municipality_id = 14 if all_municipalities.exists() else None
        selected_municipality_obj = MunicipalityName.objects.get(pk=selected_municipality_id)
    
    
    # Only show municipalities with at least 2 months of data for the selected commodity
    municipality_qs = VerifiedHarvestRecord.objects.filter(commodity_id=selected_commodity_id)
    municipality_months = {}
    for muni_id in all_municipalities.values_list('municipality_id', flat=True):
        muni_records = municipality_qs.filter(municipality_id=muni_id)
        months = muni_records.values_list('harvest_date', flat=True)
        month_set = set((d.year, d.month) for d in months if d)
        if len(month_set) >= 2:
            municipality_months[muni_id] = True

    municipalities = all_municipalities.filter(municipality_id__in=municipality_months.keys())

    now_dt = datetime.now()
    current_year = now_dt.year
    available_years = list(
    ForecastResult.objects.order_by('forecast_year')
        .values_list('forecast_year', flat=True).distinct()
    )
    if not available_years:
        available_years = [timezone.now().year]

    # Always show all months
    months = Month.objects.order_by('number')
    
    
    filter_month = request.GET.get('filter_month')
    filter_year = request.GET.get('filter_year')
    print("Selected commodity:", selected_commodity_id)
    print("Filter month/year:", filter_month, filter_year)

    # TESTING FORECAST W/ SEPARATING HISTORICAL AND FORECAST
    
    # Get historical data
    print(type(selected_commodity_id), " : ", selected_commodity_id, type(selected_municipality_id), ':', selected_municipality_id)

    if selected_municipality_id == "14" or selected_municipality_id == 14:
        # "Overall" selected: do not filter by municipality, sum all
        qs = VerifiedHarvestRecord.objects.filter(
            commodity_id=selected_commodity_id,
        ).values('harvest_date', 'total_weight_kg').order_by('harvest_date')
        print("Overall selected, not filtering by municipality.", qs)
    else:
        qs = VerifiedHarvestRecord.objects.filter(
            commodity_id=selected_commodity_id,
            municipality_id=selected_municipality_id
        ).values('harvest_date', 'total_weight_kg').order_by('harvest_date')
        print("Filtered by municipality:", selected_municipality_id, qs)
        
    if not qs.exists():
        forecast_data = None
    else:
        # Prepare historical data
        df = pd.DataFrame(list(qs))
        df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
        df['ds'] = pd.to_datetime(df['ds'])
        df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
        df = df.groupby('ds', as_index=False)['y'].sum()

        # Prepare forecast data (from trained model)
        if selected_municipality_id == "14" or selected_municipality_id == 14:
            model_filename = f"prophet_{selected_commodity_id}_14.joblib"
        else:
            model_filename = f"prophet_{selected_commodity_id}_{selected_municipality_id}.joblib"
        
        bucket_path = f"prophet_models/{model_filename}"

        # Check if the model file exists in the Spaces bucket
        if not default_storage.exists(bucket_path):
            forecast_data = None
            print("No trained model found.")
        else:
            # Open the file from the bucket and load it with joblib
            with default_storage.open(bucket_path, 'rb') as f:
                m = joblib.load(f)
            
            # Define forecast period (e.g., 12 months into future)
            last_historical_date = df['ds'].max()
            backtest_start_date = last_historical_date - pd.offsets.MonthBegin(12) if len(df) > 12 else df['ds'].min()
            
            # Define the end date for your forecast (e.g., 12 months into the future)
            future_end_date = last_historical_date + pd.offsets.MonthBegin(12)

            # Create a 'future' DataFrame that includes the backtesting period
            # and the future forecast period.
            future_months = pd.date_range(start=backtest_start_date, end=future_end_date, freq='MS')
            future = pd.DataFrame({'ds': future_months})
            forecast = m.predict(future)
            
            # Create a comprehensive timeline that includes both historical and forecast periods
            all_dates = pd.date_range(start=df['ds'].min(), end=future_end_date, freq='MS')
            
            # Create dictionaries for easy lookup
            hist_dict = dict(zip(df['ds'], df['y']))
            forecast_dict = dict(zip(forecast['ds'], forecast['yhat']))
            
            # Build aligned arrays for Chart.js
            all_labels = [d.strftime('%b %Y') for d in all_dates]
            hist_values = [float(hist_dict.get(d, 0)) if d in hist_dict else None for d in all_dates]
            forecast_values = [float(forecast_dict.get(d, 0)) if d in forecast_dict else None for d in all_dates]
            
            # Combined data for CSV/table (only future forecasts)
            future_forecast = forecast[forecast['ds'] > last_historical_date]
            combined_list = list(zip(
                future_forecast['ds'].dt.strftime('%b %Y').tolist(),
                future_forecast['yhat'].round(2).tolist(),
                future_forecast['ds'].dt.month.tolist(),
                future_forecast['ds'].dt.year.tolist()
            ))

            print("Historical data points:", sum(1 for v in hist_values if v is not None))
            print("Forecast data points:", sum(1 for v in forecast_values if v is not None))
            print("Overlapping timeline created with", len(all_labels), "labels")

            forecast_data = {
                'all_labels': json.dumps(all_labels),
                'hist_values': json.dumps(hist_values),
                'forecast_values': json.dumps(forecast_values),
                'combined': combined_list,
            }
    
    
    
    # INITIAL WORKING FORECASTING

    # Filter by commodity and municipality
    # qs = VerifiedHarvestRecord.objects.filter(commodity_id=selected_commodity_id)
    # if selected_municipality_id:
    #     qs = qs.filter(municipality_id=selected_municipality_id)
    # qs = qs.values('harvest_date', 'total_weight_kg')

    # print("QS before if exists condition", qs)
    # if qs.exists():
    #     df = pd.DataFrame(list(qs))
    #     df['harvest_date'] = pd.to_datetime(df['harvest_date'])
    #     # Group by year and month, sum total_weight_kg
    #     df['year'] = df['harvest_date'].dt.year
    #     df['month'] = df['harvest_date'].dt.month
    #     grouped = df.groupby(['year', 'month'], as_index=False)['total_weight_kg'].sum()
    #     grouped['ds'] = pd.to_datetime(grouped['year'].astype(str) + '-' + grouped['month'].astype(str) + '-01')
    #     prophet_df = grouped[['ds', 'total_weight_kg']].rename(columns={'total_weight_kg': 'y'})
    #     prophet_df = prophet_df.drop_duplicates(subset=['ds'])
    #     prophet_df = prophet_df.dropna(subset=['ds', 'y'])
    #     prophet_df = prophet_df.sort_values('ds')
        
    #     print("Grouped DataFrame before creating 'ds':", grouped)
        
    #     # prophet_df = grouped[['ds', 'total_weight_kg']].rename(columns={'total_weight_kg': 'y'})
    #     # prophet_df = prophet_df[prophet_df['y'] > 0]
    #     # prophet_df = prophet_df.drop_duplicates(subset=['ds'])
        
    #     if len(prophet_df) >= 2:
    #         model = Prophet()
    #         model.fit(prophet_df)
            
    #         future = model.make_future_dataframe(periods=12, freq='M')
    #         forecast_df = model.predict(future)

    #         # Apply seasonal boost to in-season months, removed boost since kwan naman
    #         boost_factor = 1.0
    #         forecast_df['month_num'] = forecast_df['ds'].dt.month
    #         forecast_df['yhat_boosted'] = forecast_df.apply(
    #             lambda row: row['yhat'] * boost_factor if row['month_num'] in in_season_months else row['yhat'],
    #             axis=1
    #         )
    #         forecast_df['yhat_boosted'] = forecast_df['yhat_boosted'].clip(lower=0)

    #         labels = forecast_df['ds'].dt.strftime('%B %Y').tolist()
    #         month_numbers = forecast_df['ds'].dt.month.tolist()
    #         years = forecast_df['ds'].dt.year.tolist()
    #         values = forecast_df['yhat_boosted'].round().tolist()
    #         combined_forecast = list(zip(labels, values, month_numbers, years))

    #         forecast_data = {
    #             'labels': labels,
    #             'forecasted_count': values,
    #             'combined': combined_forecast
    #         }
    #     else:
    #         forecast_data = None
            
    # else:
    #     forecast_data = None

        # END OF WORKING FORECAST NA COMBINED SAVING NG HISTORICAL AT FORECAST 
        
        # QUERY FOR THE HISTORICAL DATA POINTS FROM THE DB
        
        # historical_qs = VerifiedHarvestRecord.objects.filter(
        #     commodity_id=selected_commodity_id,
        #     municipality_id=selected_municipality_id
        # ).order_by('harvest_date')

        # # Group by month/year
        # historical_data = OrderedDict()
        # for rec in historical_qs:
        #     key = rec.harvest_date.strftime('%B %Y')
        #     historical_data[key] = historical_data.get(key, 0) + float(rec.total_weight_kg)

        # if historical_qs.exists():
        #     df = pd.DataFrame([
        #         {'ds': rec.harvest_date, 'y': float(rec.total_weight_kg)}
        #         for rec in historical_qs
        #     ])
        #     model = Prophet()
        #     model.fit(df)
        #     future = model.make_future_dataframe(periods=12, freq='M')
        #     forecast = model.predict(future)

        #     # 3. Split Prophet output into historical and forecast
        #     last_hist_date = df['ds'].max()
        #     forecast['month_year'] = forecast['ds'].dt.strftime('%B %Y')
        #     historical_pred = forecast[forecast['ds'] <= last_hist_date]
        #     forecast_pred = forecast[forecast['ds'] > last_hist_date]

        #     # 4. Prepare for Chart.js
        #     all_labels = list(OrderedDict.fromkeys(
        #         list(historical_data.keys()) +
        #         list(forecast['month_year'])
        #     ))
        #     existing_values = [historical_data.get(label, None) for label in all_labels]
        #     forecast_values = []
        #     for label in all_labels:
        #         row = forecast_pred[forecast_pred['month_year'] == label]
        #         forecast_values.append(float(row['yhat'].values[0]) if not row.empty else None)

        # # modify this pagka nasure ng nagana, add to existing context
        # context = {
        #     # ...other context...
        #     'all_labels': all_labels,
        #     'existing_values': existing_values,
        #     'forecast_values': forecast_values,
        #     # ...other context...
        # }

        
        
        filter_month = request.GET.get('filter_month')
        filter_year = request.GET.get('filter_year')
        
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        months =  Month.objects.order_by('number')
        if filter_year and int(filter_year) == current_year:
            months = months.filter(number__gt=now_dt.month)

        # Prepare available years for the dropdown
        current_year = datetime.now().year
        available_years = [current_year, current_year + 1]
        if not available_years:
            available_years = [timezone.now().year]
            
        forecast_value_for_selected_month = None
        if forecast_data and filter_month and filter_year:
            for label, value, month_number, year in forecast_data['combined']:
                # label is like "July 2025"
                month_name, year_str = label.split()
                if int(filter_year) == int(year_str) and int(filter_month) == datetime.strptime(month_name, "%B").month:
                    forecast_value_for_selected_month = value
                    break
        # Prepare forecast summary per commodity for the selected month/year
        
        # --- 2D Mapping (unchanged, but you can filter map_data if you want) ---
        # with open('static/geojson/BATAAN_MUNICIPALITY.geojson', 'r') as f:
        #     geojson_data = json.load(f)

        # prev_to_municipality = {}
        # for rec in qs:
        #     prev_id = rec['prev_record']
        #     if prev_id:
        #         try:
        #             prev = initHarvestRecord.objects.get(pk=prev_id)
        #             if prev.transaction and prev.transaction.location_type == 'farm_land' and prev.transaction.farm_land:
        #                 municipality = prev.transaction.farm_land.municipality.municipality
        #                 prev_to_municipality[prev_id] = municipality
        #         except Exception:
        #             continue

        # df_full = pd.DataFrame.from_records(qs)
        # df_full['municipality'] = df_full['prev_record'].map(prev_to_municipality)
        # muni_group = df_full.groupby('municipality')['total_weight_kg'].sum().to_dict()

        # for feature in geojson_data['features']:
        #     properties = feature.get('properties', {})
        #     municipality = properties.get('MUNICIPALI') or properties.get('NAME_2')
        #     geom = shape(feature['geometry'])
        #     centroid = geom.centroid
        #     latitude = centroid.y
        #     longitude = centroid.x
        #     forecasted_amount = muni_group.get(municipality, 0)
        #     map_data.append({
        #         'latitude': latitude,
        #         'longitude': longitude,
        #         'barangay': None,
        #         'municipality': municipality,
        #         'province': properties.get('PROVINCE', None),
        #         'forecasted_amount': float(forecasted_amount),
        #         'forecast_value_for_selected_month': forecast_value_for_selected_month
        #     })

    context = get_admin_context(request)
    context.update({
        'forecast_data': forecast_data,
        'forecast_combined_json': json.dumps(forecast_data['combined']) if forecast_data else '[]',
        
        'commodity_types': commodity_types,
        'municipalities': municipalities,
        'selected_commodity_obj': selected_commodity_obj,
        'selected_commodity_id': selected_commodity_id,
        'selected_municipality_obj': selected_municipality_obj,
        'selected_municipality': selected_municipality_id,
        'filter_month': filter_month,
        'filter_year': filter_year,
        'available_years': available_years,
        'months': months,
        # 'forecast_summary': forecast_summary,
    })
    
    return render(request, 'admin_panel/admin_forecast.html', context)


@login_required
@admin_or_agriculturist_required
@staff_member_required
def retrain_forecast_model(request):
    if request.method == "POST":
        # Call the Celery task asynchronously
        retrain_and_generate_forecasts_task.delay()
        messages.success(request, "Forecast models are being retrained in the background!")
        return redirect('administrator:admin_forecast')
    return HttpResponseForbidden()


@login_required
@admin_or_agriculturist_required
@csrf_protect
def generate_all_forecasts(request):
    if request.method == 'POST':
        # This view is now redundant since the task combines both steps.
        # You can remove this view and its corresponding URL.
        messages.warning(request, "This function is now automated as part of the model retraining process.")
        return redirect('administrator:admin_forecast')
    return redirect('administrator:admin_forecast')


@csrf_exempt
@login_required
@admin_or_agriculturist_required
def save_admin_forecast(request):
    if request.method == 'POST':
        forecast_type = request.POST.get('forecast_type', 'by_month')
        try:
            userinfo = UserInformation.objects.get(auth_user=request.user)
            admin_info = AdminInformation.objects.filter(userinfo_id=userinfo).first()
        except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
            admin_info = None

        if forecast_type == "by_month":
            commodity_id = request.POST.get('commodity_id')
            municipality_id = request.POST.get('municipality_id')
            if not municipality_id or municipality_id == 'None':
                municipality_id = 14  # pk for 'Overall'
            months = request.POST.getlist('months[]')
            years = request.POST.getlist('years[]')
            values = request.POST.getlist('values[]')
            if not (months and years and values and commodity_id):
                messages.error(request, "Missing forecast data. Please try again.")
                return redirect('administrator:admin_forecast')
            commodity = CommodityType.objects.get(pk=commodity_id)
            municipality = MunicipalityName.objects.get(pk=municipality_id)
            notes = f"Commodity Type: {commodity.name}; Municipality: {municipality.municipality}"
            batch = ForecastBatch.objects.create(
                generated_by=admin_info,
                notes=notes,
            )
            for month, year, value in zip(months, years, values):
                if not month or not year or not value:
                    continue  # skip incomplete data
                month_obj = Month.objects.get(number=int(month))
                avg_weight_per_unit = float(commodity.average_weight_per_unit_kg)
                forecasted_kg = float(value)
                forecasted_count_units = forecasted_kg / avg_weight_per_unit if avg_weight_per_unit else None
                ForecastResult.objects.create(
                    batch=batch,
                    commodity=commodity,
                    forecast_month=month_obj,
                    forecast_year=int(year),
                    municipality_id=int(municipality_id),
                    forecasted_amount_kg=forecasted_kg,
                    forecasted_count_units=forecasted_count_units,
                    source_data_last_updated=timezone.now(),
                    seasonal_boost_applied=True,
                )
        elif forecast_type == "by_commodity":
            municipality_id = request.POST.get('municipality_id')
            if not municipality_id or municipality_id == 'None':
                municipality_id = 14  # pk for 'Overall'
            filter_month = request.POST.get('filter_month')
            filter_year = request.POST.get('filter_year')
            commodity_ids = request.POST.getlist('commodity_ids[]')
            values = request.POST.getlist('values[]')
            if not (commodity_ids and values and filter_month and filter_year):
                messages.error(request, "Missing forecast summary data. Please try again.")
                return redirect('administrator:admin_forecast')
            try:
                month_obj = Month.objects.get(number=int(filter_month))
            except Month.DoesNotExist:
                messages.error(request, "Invalid month selected.")
                return redirect('administrator:admin_forecast')
            notes = f"Month and Year: {month_obj.name} {filter_year}"
            batch = ForecastBatch.objects.create(
                generated_by=admin_info,
                notes=notes,
            )
            for commodity_id, value in zip(commodity_ids, values):
                if not commodity_id or not value:
                    continue
                try:
                    commodity = CommodityType.objects.get(pk=commodity_id)
                except CommodityType.DoesNotExist:
                    continue
                avg_weight_per_unit = float(commodity.average_weight_per_unit_kg)
                forecasted_kg = float(value)
                forecasted_count_units = forecasted_kg / avg_weight_per_unit if avg_weight_per_unit else None
                ForecastResult.objects.create(
                    batch=batch,
                    commodity=commodity,
                    forecast_month=month_obj,
                    forecast_year=int(filter_year),
                    municipality_id=int(municipality_id),
                    forecasted_amount_kg=forecasted_kg,
                    forecasted_count_units=forecasted_count_units,
                    source_data_last_updated=timezone.now(),
                    seasonal_boost_applied=True,
                )
        else:
            messages.error(request, "Unknown forecast type.")
            return redirect('administrator:admin_forecast')
        return redirect('administrator:admin_forecastviewall')
    else:
        return redirect('administrator:admin_forecast')


def forecast_csv(request, batch_id):
    batch = get_object_or_404(ForecastBatch, pk=batch_id)
    results = ForecastResult.objects.filter(batch=batch).select_related('commodity', 'municipality', 'forecast_month')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="forecast_batch_{batch_id}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Commodity', 'Municipality', 'Month & Year', 'Forecasted Amount (kg)', 'Forecasted Count (units)', 'Batch ID', 'Generated At'])

    for result in results:
        writer.writerow([
            result.commodity.name,
            result.municipality.municipality,
            f"{result.forecast_month.name} {result.forecast_year}",
            round(result.forecasted_amount_kg, 2) or 0,
            result.forecasted_count_units,
            result.batch.batch_id if result.batch else '',
            result.batch.generated_at.strftime('%Y-%m-%d %H:%M') if result.batch else '',
        ])

    return response



@login_required
@admin_or_agriculturist_required
def admin_forecastviewall(request):
    batches = ForecastBatch.objects.select_related('generated_by__userinfo_id').order_by('-generated_at')
    paginator = Paginator(batches, 10)  # Show 10 batches per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = get_admin_context(request)
    context.update({'page_obj': page_obj})
    return render(request, 'admin_panel/admin_forecastviewall.html', context)

@login_required
@admin_or_agriculturist_required
def admin_forecastbatchdetails(request, batch_id):
    batch = get_object_or_404(ForecastBatch, pk=batch_id)
    results = ForecastResult.objects.filter(batch=batch).select_related('commodity', 'municipality', 'forecast_month').order_by('forecast_year', 'forecast_month__number')
    context = get_admin_context(request)
    context.update({'batch': batch, 'results': results})
    return render(request, 'admin_panel/admin_forecastbatchdetails.html', context)

@login_required
@admin_or_agriculturist_required
def admin_commodity_list(request):
    if request.method == 'POST':
        selected_commodities = request.POST.getlist('selected_commodities')
        bulk_action = request.POST.get('bulk_action')
        
        if selected_commodities and bulk_action:
            try:
                if bulk_action == 'delete':
                    # Delete selected commodities
                    deleted_count = 0
                    for commodity_id in selected_commodities:
                        commodity = CommodityType.objects.get(pk=commodity_id)
                        # Don't allow deletion of 'Not Listed' or if there are related records
                        if commodity.pk != 1:  # Don't delete 'Not Listed'
                            commodity.delete()
                            deleted_count += 1
                    
                    if deleted_count > 0:
                        messages.success(request, f'Successfully deleted {deleted_count} commodit{"y" if deleted_count == 1 else "ies"}.')
                    else:
                        messages.warning(request, 'No commodities were deleted.')
                        
                elif bulk_action == 'export':
                    # Export selected commodities as CSV
                    response = HttpResponse(content_type='text/csv')
                    response['Content-Disposition'] = 'attachment; filename="selected_commodities.csv"'
                    
                    writer = csv.writer(response)
                    writer.writerow(['Name', 'Average Weight (kg)', 'Years to Mature', 'Years to Bear Fruit', 'Seasonal Months'])
                    
                    for commodity_id in selected_commodities:
                        commodity = CommodityType.objects.get(pk=commodity_id)
                        seasonal_months = ";".join([month.name for month in commodity.seasonal_months.all()])
                        writer.writerow([
                            commodity.name,
                            commodity.average_weight_per_unit_kg,
                            commodity.years_to_mature or '',
                            commodity.years_to_bearfruit or '',
                            seasonal_months
                        ])
                    
                    return response
                    
            except Exception as e:
                messages.error(request, f'Error performing bulk action: {str(e)}')
        else:
            if not selected_commodities:
                messages.warning(request, 'Please select at least one commodity.')
            if not bulk_action:
                messages.warning(request, 'Please select an action to perform.')
    
    commodities = CommodityType.objects.exclude(pk=1)  # Exclude 'Not Listed' commodity
    context = get_admin_context(request)
    context.update({'commodities': commodities})
    return render(request, 'admin_panel/admin_commodity.html', context)


@login_required
@admin_or_agriculturist_required
def admin_commodity_add_edit(request, pk=None):
    if request.method == "POST" and request.FILES.get("csv_file"):
        csv_file = request.FILES["csv_file"]
        decoded_file = csv_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded_file))
        for row in reader:
            # Clean up keys and values
            row = {k.strip(): v.strip() for k, v in row.items()}
            print(row)  # Debug: See what keys you have
            name = row["name"]  # This will now work if the header is correct
            avg_weight = float(row["average_weight_per_unit_kg"])
            years_to_mature = float(row["years_to_mature"])
            years_to_bearfruit = float(row.get("years_to_bearfruit", 0))
            commodity, _ = CommodityType.objects.get_or_create(
                name=name,
                defaults={
                    "average_weight_per_unit_kg": avg_weight,
                    "years_to_mature": years_to_mature,
                    "years_to_bearfruit": years_to_bearfruit,
                }
            )
            commodity.average_weight_per_unit_kg = avg_weight
            commodity.years_to_mature = years_to_mature
            commodity.years_to_bearfruit = years_to_bearfruit
            commodity.save()
            months = [m.strip() for m in row["seasonal_months"].split(";")]
            month_objs = Month.objects.filter(name__in=months)
            commodity.seasonal_months.set(month_objs)
        messages.success(request, "CSV uploaded successfully.")
        return redirect("administrator:admin_commodity_list")

    
    if pk:
        commodity = get_object_or_404(CommodityType, pk=pk)
    else:
        commodity = None

    if request.method == 'POST':
        form = CommodityTypeForm(request.POST, instance=commodity)
        if form.is_valid():
            form.save()
            return redirect('administrator:admin_commodity_list')
        else : 
            print("⚠️ Not valid Form errors:", form.errors)
    else:
        form = CommodityTypeForm(instance=commodity)
        print("⚠️ Not post Form errors:", form.errors)

    context = get_admin_context(request)
    context.update({'form': form, 'commodity': commodity})
    return render(request, 'admin_panel/commodity_add.html', context)


@login_required
@admin_or_agriculturist_required
def admin_verifyplantrec(request):
    user = request.user
    userinfo = UserInformation.objects.get(auth_user=user)
    admin_info = AdminInformation.objects.get(userinfo_id=userinfo)
    municipality_assigned = admin_info.municipality_incharge

    # Filters
    filter_municipality = request.GET.get('municipality')
    filter_commodity = request.GET.get('commodity')
    filter_status = request.GET.get('status')

    # Municipality filter logic
    if user.is_superuser or municipality_assigned.pk == 14:
        municipalities = MunicipalityName.objects.all()
        records = initPlantRecord.objects.all()
    else:
        municipalities = MunicipalityName.objects.filter(pk=municipality_assigned.pk)
        records = VerifiedPlantRecord.objects.filter(municipality=municipality_assigned)

    # Apply filters
    if filter_municipality:
        records = records.filter(
            Q(transaction__farm_land__municipality__pk=filter_municipality) |
            Q(transaction__manual_municipality__pk=filter_municipality)
        )
    if filter_commodity:
        records = records.filter(commodity_id__pk=filter_commodity)
    if filter_status:
        records = records.filter(record_status__pk=filter_status)

    if request.method == "POST":
        selected_ids = request.POST.getlist('selected_records')
        new_status_pk = int(request.POST.get('new_status'))
        verified_status_pk = 2  # pk for "Verified"
        new_status = AccountStatus.objects.get(pk=new_status_pk)
        for rec in records.filter(pk__in=selected_ids):
            rec.record_status = new_status
            if not rec.verified_by:
                rec.verified_by = admin_info
            rec.save()
            # Only create VerifiedPlantRecord if status is "Verified" and not already created
            if new_status_pk == verified_status_pk:
                if not VerifiedPlantRecord.objects.filter(prev_record=rec).exists():
                    # Get location
                    if rec.transaction.farm_land:
                        municipality = rec.transaction.farm_land.municipality
                        barangay = rec.transaction.farm_land.barangay
                    else:
                        municipality = rec.transaction.manual_municipality
                        barangay = rec.transaction.manual_barangay
                    # Calculate average and estimated weight
                    est_weight = (rec.min_expected_harvest + rec.max_expected_harvest) / 2
                    # est_weight = avg_units * float(rec.commodity_id.average_weight_per_unit_kg)
                    VerifiedPlantRecord.objects.create(
                        plant_date=rec.plant_date,
                        commodity_id=rec.commodity_id,
                        min_expected_harvest=rec.min_expected_harvest,
                        max_expected_harvest=rec.max_expected_harvest,
                        # average_harvest_units=avg_units,
                        estimated_weight_kg=est_weight,
                        remarks=rec.remarks,
                        municipality=municipality,
                        barangay=barangay,
                        verified_by=admin_info,
                        prev_record=rec,
                    )
        messages.success(request, "Selected records updated successfully.")
    else:
        messages.error(request, "No records selected or status not chosen.")

    commodities = CommodityType.objects.all()
    status_choices = AccountStatus.objects.all()

    context = get_admin_context(request)
    context.update({
        'records': records,
        'municipalities': municipalities,
        'commodities': commodities,
        'status_choices': status_choices,
        'selected_municipality': filter_municipality,
        'selected_commodity': filter_commodity,
        'selected_status': filter_status,
    })
    return render(request, 'admin_panel/admin_verifyplantrec.html', context)


@login_required
@admin_or_agriculturist_required
def admin_verifyharvestrec(request):
    user = request.user
    userinfo = UserInformation.objects.get(auth_user=user)
    admin_info = AdminInformation.objects.get(userinfo_id=userinfo)
    is_superuser = user.is_superuser
    is_pk14 = admin_info.municipality_incharge.pk == 14

    # Filters
    selected_municipality = request.GET.get('municipality')
    selected_commodity = request.GET.get('commodity')
    selected_status = request.GET.get('status')

    # Only show allowed municipalities
    if is_superuser or is_pk14:
        municipalities = MunicipalityName.objects.all()
    else:
        municipalities = MunicipalityName.objects.filter(pk=admin_info.municipality_incharge.pk)

    commodities = CommodityType.objects.all()
    status_choices = AccountStatus.objects.all()

    # Query records 
    records = initHarvestRecord.objects.all()
    if selected_municipality:
        records = records.filter(
            Q(transaction__farm_land__municipality__pk=selected_municipality) |
            Q(transaction__manual_municipality__pk=selected_municipality)
        )
    elif not (is_superuser or is_pk14):
        records = records.filter(municipality=admin_info.municipality_incharge)
    if selected_commodity:
        records = records.filter(commodity_id__pk=selected_commodity)
    if selected_status:
        records = records.filter(record_status__pk=selected_status)

    # Batch update
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_records')
        new_status_pk = int(request.POST.get('new_status'))
        verified_status_pk = 2  # pk for "Verified"
        new_status = AccountStatus.objects.get(pk=new_status_pk)
        for rec in records.filter(pk__in=selected_ids):
            rec.record_status = new_status
            if not rec.verified_by:
                rec.verified_by = admin_info
            rec.save()
            # Only create VerifiedHarvestRecord if status is "Verified" and not already created
            if new_status_pk == verified_status_pk and selected_ids:
                if not VerifiedHarvestRecord.objects.filter(prev_record=rec).exists():
                    
                    try : 
                        if rec.transaction.farm_land:
                            municipality = rec.transaction.farm_land.municipality
                            barangay = rec.transaction.farm_land.barangay
                        else:
                            municipality = rec.transaction.manual_municipality
                            barangay = rec.transaction.manual_barangay

                        VerifiedHarvestRecord.objects.create(
                            harvest_date=rec.harvest_date,
                            commodity_id=rec.commodity_id,
                            total_weight_kg=rec.total_weight,
                            weight_per_unit_kg=rec.weight_per_unit,
                            remarks=rec.remarks,
                            municipality=municipality,
                            barangay=barangay,
                            verified_by=admin_info,  # set this to the current admin
                            prev_record=rec,
                        )
                        
                        # ...
                        logger.info("Attempting to delay Celery task...")
                        logger.info(f"Using broker URL: {settings.CELERY_BROKER_URL}") # This will show the URL Celery sees
                        retrain_and_generate_forecasts_task.delay()
                        messages.success(request, "Records verified. Forecast models are being updated in the background.")
                        
                    except Exception as e:
                        logger.error(f"Error during verification: {e}")
                        messages.error(request, f"An error occurred during verification: {e}")


                       # for rec in records.filter(pk__in=selected_ids):
                       #     rec.record_status = new_status
                       #     if not rec.verified_by:
                       #         rec.verified_by = admin_info
                       #     rec.save()
        messages.success(request, "Selected records updated successfully.")
    else:
        messages.error(request, "No records selected or status not chosen.")

    
    
    context = get_admin_context(request)
    context.update({
        'municipalities': municipalities,
        'commodities': commodities,
        'status_choices': status_choices,
        'records': records,
        'selected_municipality': selected_municipality,
        'selected_commodity': selected_commodity,
        'selected_status': selected_status,
    })
    return render(request, 'admin_panel/admin_verifyharvestrec.html', context)

@login_required
@admin_or_agriculturist_required
def admin_add_verifyharvestrec(request):
    municipalities = MunicipalityName.objects.all()
    admin_info = AdminInformation.objects.get(userinfo_id=request.user.userinformation)
    context = get_admin_context(request)
    context.update({'municipalities': municipalities})

    if request.method == "POST" and request.FILES.get("csv_file"):
        csv_file = request.FILES["csv_file"]
        decoded_file = csv_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded_file))
        created_count = 0
        error_count = 0
        
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items()}
            try:
                commodity_name = row['commodity'].strip()
                try:
                    commodity_obj = CommodityType.objects.get(name__iexact=commodity_name)
                except CommodityType.DoesNotExist:
                    print(f"Commodity '{commodity_name}' does not exist in CommodityType model.")
                    messages.error(request, f"Commodity '{commodity_name}' does not exist in CommodityType model. Row skipped.")
                    error_count += 1
                    continue  # Skip this row
                municipality = MunicipalityName.objects.get(pk=int(row['municipality']))
                barangay_id_str = row.get("barangay", "")
                if barangay_id_str:
                    barangay = BarangayName.objects.get(pk=int(barangay_id_str), municipality_id=municipality)
                else:
                    barangay = None
                VerifiedHarvestRecord.objects.create(
                    harvest_date=row["harvest_date"],
                    commodity_id=commodity_obj,
                    total_weight_kg=row["total_weight_kg"],
                    weight_per_unit_kg=row["weight_per_unit_kg"],
                    municipality=municipality,
                    barangay=barangay,
                    remarks=row.get("remarks", ""),
                    date_verified=timezone.now(),
                    verified_by=admin_info,
                    prev_record=None,
                )
                created_count += 1
            except Exception as e:
                print("Error processing row:", row, e)
                error_count += 1
        
        # Show success/error messages
        if created_count > 0:
            messages.success(request, f'Successfully created {created_count} harvest record{"s" if created_count > 1 else ""} from CSV upload.')
            
            # Trigger model retraining and forecast generation
            try:
                from .tasks import retrain_and_generate_forecasts_task
                retrain_and_generate_forecasts_task.delay()
                messages.info(request, 'Model retraining and forecast generation has been initiated in the background.')
            except Exception as e:
                messages.warning(request, f'Records created successfully, but forecast regeneration failed: {str(e)}')
        
        if error_count > 0:
            messages.warning(request, f'{error_count} row{"s" if error_count > 1 else ""} could not be processed due to errors.')
            print(f'{error_count} row(s) could not be processed due to errors.')
        return redirect("administrator:admin_harvestverified")

    elif request.method == "POST":
        form = VerifiedHarvestRecordForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.date_verified = timezone.now()
            rec.verified_by = admin_info
            rec.prev_record = None
            rec.save()
            
            messages.success(request, 'Harvest record has been successfully added.')
            
            # Trigger model retraining and forecast generation
            try:
                from .tasks import retrain_and_generate_forecasts_task
                retrain_and_generate_forecasts_task.delay()
                messages.info(request, 'Model retraining and forecast generation has been initiated in the background.')
            except Exception as e:
                messages.warning(request, f'Record created successfully, but forecast regeneration failed: {str(e)}')
            
            return redirect("administrator:admin_verifyharvestrec")
        context["form"] = form
    else:
        context["form"] = VerifiedHarvestRecordForm()

    return render(request, "admin_panel/verifyharvest_add.html", context)


@login_required
@admin_or_agriculturist_required
def admin_harvestverified(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_records = request.POST.getlist('selected_records')
        
        if action == 'delete' and selected_records:
            try:
                # Delete selected records
                deleted_count = 0
                for record_id in selected_records:
                    record = VerifiedHarvestRecord.objects.get(pk=record_id)
                    record.delete()
                    deleted_count += 1
                
                if deleted_count > 0:
                    messages.success(request, f'Successfully deleted {deleted_count} harvest record{"s" if deleted_count > 1 else ""}.')
                    
                    # Trigger model retraining and forecast generation
                    try:
                        # Import here to avoid circular imports
                        from .tasks import retrain_and_generate_forecasts_task
                        retrain_and_generate_forecasts_task.delay()
                        messages.info(request, 'Model retraining and forecast generation has been initiated in the background.')
                    except Exception as e:
                        messages.warning(request, f'Records deleted successfully, but forecast regeneration failed: {str(e)}')
                
            except Exception as e:
                messages.error(request, f'Error deleting records: {str(e)}')
        
        return redirect('administrator:admin_harvestverified')
    
    # Handle filtering
    municipality_filter = request.GET.get('municipality')
    commodity_filter = request.GET.get('commodity')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    records = VerifiedHarvestRecord.objects.select_related('commodity_id', 'municipality', 'barangay', 'verified_by__userinfo_id')
    
    if municipality_filter:
        records = records.filter(municipality_id=municipality_filter)
    if commodity_filter:
        records = records.filter(commodity_id=commodity_filter)
    if date_from:
        records = records.filter(harvest_date__gte=date_from)
    if date_to:
        records = records.filter(harvest_date__lte=date_to)
    
    # Get filter options
    municipalities = MunicipalityName.objects.all()
    commodities = CommodityType.objects.all()
    
    context = get_admin_context(request)
    context.update({
        'records': records,
        'municipalities': municipalities,
        'commodities': commodities,
        'selected_municipality': municipality_filter,
        'selected_commodity': commodity_filter,
        'date_from': date_from,
        'date_to': date_to,
    })
    return render(request, 'admin_panel/admin_harvestverified.html', context)


@login_required
@admin_or_agriculturist_required
def admin_harvestverified_view(request, record_id):
    """View details of a specific verified harvest record"""
    record = get_object_or_404(VerifiedHarvestRecord, pk=record_id)
    context = get_admin_context(request)
    context.update({'record': record})
    return render(request, 'admin_panel/admin_harvestverified_view.html', context)


@login_required
@admin_or_agriculturist_required
def admin_harvestverified_edit(request, record_id):
    """Edit a specific verified harvest record"""
    record = get_object_or_404(VerifiedHarvestRecord, pk=record_id)
    
    if request.method == 'POST':
        form = VerifiedHarvestRecordForm(request.POST, instance=record)
        if form.is_valid():
            updated_record = form.save(commit=False)
            # Keep the original verification info
            updated_record.verified_by = record.verified_by
            updated_record.date_verified = record.date_verified
            updated_record.save()
            
            messages.success(request, 'Harvest record updated successfully.')
            
            # Trigger model retraining and forecast generation
            try:
                from .tasks import retrain_and_generate_forecasts_task
                retrain_and_generate_forecasts_task.delay()
                messages.info(request, 'Model retraining and forecast generation has been initiated in the background.')
            except Exception as e:
                messages.warning(request, f'Record updated successfully, but forecast regeneration failed: {str(e)}')
            
            return redirect('administrator:admin_harvestverified_view', record_id=record.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = VerifiedHarvestRecordForm(instance=record)
    
    context = get_admin_context(request)
    context.update({
        'form': form, 
        'record': record,
        'municipalities': MunicipalityName.objects.all(),
        'commodities': CommodityType.objects.all(),
    })
    return render(request, 'admin_panel/admin_harvestverified_edit.html', context)


# def accinfo(request):
#     print("🔥 DEBUG: account view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
            
#             account_id = request.session.get('account_id')
#             userinfo_id = request.session.get('userinfo_id')
#             if userinfo_id and account_id:
#                 userinfo = UserInformation.objects.get(pk=userinfo_id)
#                 account_info = AccountsInformation.objects.get(pk=account_id)
#                 context = {
#                     'user_firstname': userinfo.firstname,
#                     # ...other fields...
#                     'user_role_id': account_info.account_type_id.account_type_id,
#                 }
#                 return render(request, 'loggedin/account_info.html', context)
#             else:
#                 return redirect('administrator:dashboard')
        
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('base:home') #dapat redirect si user sa guest home
#     else :
#         return render(request, 'home.html', {})   


@admin_or_agriculturist_required
def admin_account_detail(request, account_id):
    """
    Display account details for administrators and agriculturists
    Access levels:
    - Superuser: Full information
    - Administrator: Limited information (name, age, sex, contact, address, assigned municipality)
    """
    try:
        # Get the account to view
        target_account = get_object_or_404(AccountsInformation, pk=account_id)
        target_userinfo = target_account.userinfo_id
        
        # Check if target account is admin or agriculturist
        if target_account.account_type_id.account_type not in ["Administrator", "Agriculturist"]:
            messages.error(request, "You can only view administrator and agriculturist accounts.")
            return redirect('administrator:show_allaccounts')
        
        # Get current user info
        current_user_info = request.user.userinformation
        current_account = AccountsInformation.objects.get(userinfo_id=current_user_info)
        current_admin_info = AdminInformation.objects.filter(userinfo_id=current_user_info).first()
        
        # Determine access level based on new rules
        is_superuser = request.user.is_superuser
        user_role_id = current_account.account_type_id.pk
        target_account_type_id = target_account.account_type_id.pk
        
        # New access control logic:
        # - Superuser: full info for everyone
        # - Administrator: full info for agriculturists, partial for administrators
        can_view_full_details = False
        if is_superuser:
            can_view_full_details = True
        elif user_role_id == 2:  # Administrator
            if target_account_type_id == 3:  # Target is Agriculturist
                can_view_full_details = True
            # If target is Administrator, partial info only (can_view_full_details remains False)
        
        # Calculate age
        today = date.today()
        birth_date = target_userinfo.birthdate
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        # Get admin information if target is admin/agriculturist
        target_admin_info = AdminInformation.objects.filter(userinfo_id=target_userinfo).first()
        
        # Get admin action history (if target has AdminInformation)
        admin_actions = []
        if target_admin_info:
            try:
                admin_actions = AdminUserManagement.objects.filter(
                    admin_id=target_admin_info
                ).order_by('-action_timestamp')[:20]  # Latest 20 actions
            except Exception as e:
                print(f"Warning: Could not fetch admin actions - database schema issue: {e}")
                # If there's a database schema issue, set empty list
                admin_actions = []
        
        context = {
            **get_admin_context(request),
            'target_account': target_account,
            'target_userinfo': target_userinfo,
            'target_admin_info': target_admin_info,
            'calculated_age': age,
            'is_superuser': is_superuser,
            'user_role_id': user_role_id,
            'target_account_type_id': target_account_type_id,
            'can_view_full_details': can_view_full_details,
            'admin_actions': admin_actions,
        }
        
        return render(request, 'admin_panel/admin_account_detail.html', context)
        
    except AccountsInformation.DoesNotExist:
        messages.error(request, "Account not found.")
        print("Error: Account not found in admin_account_detail")
        return redirect('administrator:show_allaccounts')
    except Exception as e:
        messages.error(request, f"Error loading account details: {str(e)}")
        print(f"Error in admin_account_detail: {e}")
        return redirect('administrator:show_allaccounts')


# def editacc(request):
#     print("🔥 DEBUG: editacc view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         userinfo_id = request.session.get('userinfo_id')
#         userinfo = UserInformation.objects.get(pk=userinfo_id)
        
#         context = {
#                 'user_firstname' : userinfo.firstname,
#             } 
        
#         if request.method == "POST":
#             form = EditUserInformation(request.POST,instance=userinfo)
#             if form.is_valid():
#                 updated_info = form.save(commit=False)
#                 updated_info.auth_user = request.user
#                 updated_info.save()
                
#                 request.user.email = updated_info.user_email
#                 request.user.save()
                
#                 return redirect('administrator:accinfo')                
        
#         else:
#             form = EditUserInformation(instance=userinfo)

#         return render(request, 'loggedin/account_edit.html', {'form': form})
#     else :
#         return render(request, 'home.html', {})  