from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from base.models import AuthUser, UserInformation, AdminInformation, AccountsInformation, AccountStatus, AccountType, MunicipalityName, BarangayName, CommodityType, Month, initHarvestRecord, initPlantRecord, FarmLand, RecordTransaction, UserLoginLog
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, HttpResponse
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
import logging
from django.db.models import Q, Count
from datetime import datetime, date
from calendar import monthrange
import csv, io, joblib, json, os
from django.core.paginator import Paginator
from collections import OrderedDict
from pathlib import Path
from django.core.management import call_command
from .tasks import retrain_and_generate_forecasts_task
from django.core.files.storage import default_storage
from django.contrib.contenttypes.models import ContentType
from base.models import AdminUserManagement

# PDF generation imports
try:
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Unit conversion functions
UNIT_CONVERSION_TO_KG = {
    "kg": 1,
    "g": 0.001,
    "ton": 1000,
    "lbs": 0.453592,
}

def convert_to_kg(weight, unit_abrv):
    """Convert weight from any unit to kg using unit abbreviation"""
    return float(weight) * UNIT_CONVERSION_TO_KG.get(unit_abrv.lower(), 1)


from django.contrib.admin.views.decorators import staff_member_required
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

    try:
        user_info = UserInformation.objects.get(auth_user=user)
        admin_info = AdminInformation.objects.get(userinfo_id=user_info)
        account_info = AccountsInformation.objects.get(userinfo_id=user_info)
        
        is_superuser = user.is_superuser
        is_pk14 = admin_info.municipality_incharge.pk == 14
        is_administrator = account_info.account_type_id.account_type.lower() == 'administrator'
        assigned_municipality = admin_info.municipality_incharge
        
        # Base statistics that apply to all admin types
        if is_superuser or is_pk14:
            # Superuser/Administrator (pk=14) sees all data
            total_accounts = AccountsInformation.objects.filter(account_type_id=1).count()  # All farmers
            verified_accounts = AccountsInformation.objects.filter(account_type_id=1, acc_status_id=2).count()
            pending_accounts = AccountsInformation.objects.filter(account_type_id=1, acc_status_id=3).count()
            total_plant_records = initPlantRecord.objects.count()
            total_harvest_records = initHarvestRecord.objects.count()
            pending_plant_records = initPlantRecord.objects.filter(record_status__acc_stat_id=3).count()
            pending_harvest_records = initHarvestRecord.objects.filter(record_status__acc_stat_id=3).count()
            verified_plant_records = VerifiedPlantRecord.objects.count()
            verified_harvest_records = VerifiedHarvestRecord.objects.count()
            recent_registrations = AccountsInformation.objects.filter(
                account_type_id=1
            ).order_by('-account_register_date')[:5]
            municipalities_data = MunicipalityName.objects.exclude(pk=14).annotate(
                farmer_count=Count('userinformation__accountsinformation', 
                                 filter=Q(userinformation__accountsinformation__account_type_id=1))
            )
        else:
            # Agriculturist sees only their municipality data
            total_accounts = AccountsInformation.objects.filter(
                account_type_id=1,
                userinfo_id__municipality_id=assigned_municipality
            ).count()
            verified_accounts = AccountsInformation.objects.filter(
                account_type_id=1,
                acc_status_id=2,
                userinfo_id__municipality_id=assigned_municipality
            ).count()
            pending_accounts = AccountsInformation.objects.filter(
                account_type_id=1,
                acc_status_id=3,
                userinfo_id__municipality_id=assigned_municipality
            ).count()
            
            # Plant and harvest records for their municipality
            municipality_plant_records = initPlantRecord.objects.filter(
                Q(transaction__farm_land__municipality=assigned_municipality) |
                Q(transaction__manual_municipality=assigned_municipality)
            )
            municipality_harvest_records = initHarvestRecord.objects.filter(
                Q(transaction__farm_land__municipality=assigned_municipality) |
                Q(transaction__manual_municipality=assigned_municipality)
            )
            
            total_plant_records = municipality_plant_records.count()
            total_harvest_records = municipality_harvest_records.count()
            pending_plant_records = municipality_plant_records.filter(record_status__acc_stat_id=3).count()
            pending_harvest_records = municipality_harvest_records.filter(record_status__acc_stat_id=3).count()
            
            verified_plant_records = VerifiedPlantRecord.objects.filter(municipality=assigned_municipality).count()
            verified_harvest_records = VerifiedHarvestRecord.objects.filter(municipality=assigned_municipality).count()
            
            recent_registrations = AccountsInformation.objects.filter(
                account_type_id=1,
                userinfo_id__municipality_id=assigned_municipality
            ).order_by('-account_register_date')[:5]
            
            municipalities_data = [assigned_municipality]  # Only their municipality

        # Recent activities (last 10 admin actions)
        recent_activities = AdminUserManagement.objects.filter(
            admin_id=admin_info
        ).order_by('-action_timestamp')[:10]

        # Commodity statistics
        if is_superuser or is_pk14:
            top_commodities = CommodityType.objects.annotate(
                plant_count=Count('initplantrecord'),
                harvest_count=Count('initharvestrecord')
            ).order_by('-plant_count')[:5]
        else:
            # For agriculturists, filter by their municipality
            top_commodities = CommodityType.objects.annotate(
                plant_count=Count('initplantrecord', 
                    filter=Q(initplantrecord__transaction__farm_land__municipality=assigned_municipality) |
                           Q(initplantrecord__transaction__manual_municipality=assigned_municipality)),
                harvest_count=Count('initharvestrecord',
                    filter=Q(initharvestrecord__transaction__farm_land__municipality=assigned_municipality) |
                           Q(initharvestrecord__transaction__manual_municipality=assigned_municipality))
            ).order_by('-plant_count')[:5]

        # Recent forecast batches
        recent_forecasts = ForecastBatch.objects.order_by('-generated_at')[:5]

        context.update({
            'total_accounts': total_accounts,
            'verified_accounts': verified_accounts,
            'pending_accounts': pending_accounts,
            'total_plant_records': total_plant_records,
            'total_harvest_records': total_harvest_records,
            'pending_plant_records': pending_plant_records,
            'pending_harvest_records': pending_harvest_records,
            'verified_plant_records': verified_plant_records,
            'verified_harvest_records': verified_harvest_records,
            'recent_registrations': recent_registrations,
            'recent_activities': recent_activities,
            'top_commodities': top_commodities,
            'recent_forecasts': recent_forecasts,
            'municipalities_data': municipalities_data,
            'is_administrator': is_administrator,
            'is_agriculturist': not (is_superuser or is_pk14),
            'assigned_municipality': assigned_municipality,
            'admin_info': admin_info,
        })

        return render(request, 'admin_panel/admin_dashboard.html', context)
        
    except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist, AccountsInformation.DoesNotExist):
        return HttpResponseForbidden("You are not authorized to access this page.")

@login_required
def update_account_status(request, account_id):
    if request.method == 'POST':
        account = get_object_or_404(AccountsInformation, pk=account_id)
        
        # Try both possible field names from the form
        new_status_value = request.POST.get('new_status') or request.POST.get('status')
        
        if new_status_value is None:
            messages.error(request, 'No status provided for update.')
            return redirect('administrator:show_allaccounts')
        
        try:
            new_status_id = int(new_status_value)
            new_status = get_object_or_404(AccountStatus, pk=new_status_id)
            
            # Store old status for logging
            old_status = account.acc_status_id.acc_status if account.acc_status_id else "None"
            
            account.acc_status_id = new_status
            account.account_isverified = new_status_id == 2  # If Verified (pk=2)
            if account.account_verified_date is None and new_status_id == 2:
                account.account_verified_date = timezone.now()

            # Link the admin who verified
            try:
                user_info = UserInformation.objects.get(auth_user=request.user)
                admin = AdminInformation.objects.get(userinfo_id=user_info)
                if new_status_id == 2:  # Only set verified_by for verified status
                    account.account_verified_by = admin
                    
                # Create AdminUserManagement log entry
                AdminUserManagement.objects.create(
                    admin_id=admin,
                    action=f"Account ID {account.account_id} status changed from '{old_status}' to '{new_status.acc_status}'",
                    content_type=ContentType.objects.get_for_model(AccountsInformation),
                    object_id=account.account_id
                )
            except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
                pass  # Skip linking if not a recognized admin

            account.save()
            messages.success(request, f'Account status updated to {new_status.acc_status}.')
            
        except (ValueError, TypeError):
            messages.error(request, 'Invalid status value provided.')
        except Exception as e:
            messages.error(request, f'Error updating account status: {str(e)}')
            
        return redirect('administrator:show_allaccounts')

@admin_or_agriculturist_required    
def verify_accounts(request):
    # this is the view for the verify accounts page which is the farmers list
    user = request.user
    userinfo = UserInformation.objects.get(auth_user=user)
    admin_info = AdminInformation.objects.get(userinfo_id=userinfo)
    municipality_assigned = admin_info.municipality_incharge
    is_superuser = user.is_superuser
    is_pk14 = municipality_assigned.pk == 14

    pending_accounts = AccountsInformation.objects.filter(acc_status_id=2).select_related('userinfo_id', 'account_type_id', 'acc_status_id')    
    print(pending_accounts)
    
    status_filter = request.GET.get('status')
    municipality_filter = request.GET.get('municipality')
    sort_by = request.GET.get('sort', 'account_register_date')  # Default sort by date
    order = request.GET.get('order', 'desc')  # Default to desc (most recent first)

    accounts_query = AccountsInformation.objects.filter(account_type_id=1).select_related('userinfo_id', 'account_type_id', 'acc_status_id')

    # Filter by agriculturist's assigned municipality if not superuser or administrator (pk=14)
    if not is_superuser:
        if is_pk14:
            # Administrator with pk=14: can see all farmer accounts
            pass  # No additional filtering needed
        else:
            # Administrator with municipality not pk=14: can only see farmers in their municipality
            accounts_query = accounts_query.filter(
                Q(userinfo_id__municipality_id=municipality_assigned) |  # Farmer's municipality matches
                Q(recordtransaction__farm_land__municipality=municipality_assigned) |  # Has farmland in municipality
                Q(recordtransaction__manual_municipality=municipality_assigned)  # Has transactions in municipality
            ).distinct()

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
    
    # Pagination
    paginator = Paginator(all_accounts, 10)  # Show 10 accounts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    if request.method == 'POST':
        selected_ids = [sid for sid in request.POST.getlist('selected_records') if sid]
        new_status_id = request.POST.get('new_status')
        admin_info = AdminInformation.objects.filter(userinfo_id=request.user.userinformation).first()
        if selected_ids and new_status_id and admin_info:
            # Work with all_accounts queryset for batch operations, not just current page
            for acc in all_accounts.filter(pk__in=selected_ids):
                acc.acc_status_id_id = new_status_id
                acc.account_verified_by = admin_info
                if int(new_status_id) == 2:  # 2 = Verified
                    acc.account_isverified = True
                else:
                    acc.account_isverified = False
                acc.save()
            messages.success(request, f"Updated {len(selected_ids)} account(s).")
            return redirect('administrator:verify_accounts')
    
    # Pass status choices for filter dropdown - filter municipalities if agriculturist
    status_choices = AccountStatus.objects.all()
    # For bulk actions, limit to Verified (pk=2) and Suspended (pk=6) only
    bulk_action_status_choices = AccountStatus.objects.filter(pk__in=[2, 6])
    if is_superuser or is_pk14:
        municipalities = MunicipalityName.objects.exclude(pk=14)
    else:
        municipalities = MunicipalityName.objects.filter(pk=municipality_assigned.pk)
    
    context = get_admin_context(request)
    # Handle export requests
    export_type = request.GET.get('export')
    export_format = request.GET.get('format')
    
    if export_type and export_format:
        if export_type == 'records':
            return export_accounts_csv(all_accounts, 'farmer_accounts', export_format, request)
        elif export_type == 'summary':
            return export_accounts_summary_csv(all_accounts, 'farmer_accounts_summary', export_format, request)

    context.update({
        'accounts': page_obj.object_list,  # Paginated accounts for display
        'page_obj': page_obj,
        'paginator': paginator,
        'status_choices': status_choices,
        'bulk_action_status_choices': bulk_action_status_choices,  # Limited choices for bulk actions
        'municipalities': municipalities,
        'current_status': status_filter,
        'current_municipality': municipality_filter,
        'current_sort': sort_by,
        'current_order': order,
        'is_agriculturist': not is_superuser and not is_pk14,
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
    user = request.user
    user_info = user.userinformation
    account_info = AccountsInformation.objects.get(userinfo_id=user_info)
    
    # Get admin information and determine access level
    admin_info = AdminInformation.objects.get(userinfo_id=user_info)
    municipality_assigned = admin_info.municipality_incharge
    is_superuser = user.is_superuser
    is_pk14 = municipality_assigned.pk == 14  # Overall in Bataan
    user_role_id = account_info.account_type_id.pk
    
    # Restrict access to administrators only
    if user_role_id != 2:  # Only administrators (pk=2) can access
        return render(request, 'admin_panel/access_denied.html', {
            'error_message': 'Access denied. Only administrators can view this page.'
        })
        
    status_filter = request.GET.get('status')
    sort_by = request.GET.get('sort', 'account_register_date')  # Default sort by date
    order = request.GET.get('order', 'asc')  # 'asc' or 'desc'

    accounts_query = AccountsInformation.objects.select_related(
        'userinfo_id', 'account_type_id', 'acc_status_id'
    ).filter(account_type_id__account_type__in=["Administrator", "Agriculturist"])

    # Apply privilege-based filtering
    if not is_superuser:
        if is_pk14:
            # Administrator with pk=14: can see all agriculturists and administrators
            accounts_query = accounts_query.filter(
                account_type_id__account_type__in=["Administrator", "Agriculturist"]
            )
        else:
            # Administrator with municipality not pk=14
            accounts_query = accounts_query.filter(
                Q(
                    # Can see agriculturists in same municipality
                    account_type_id__account_type="Agriculturist",
                    userinfo_id__municipality_id=municipality_assigned.pk
                ) |
                Q(
                    # Can see administrators in same municipality and pk=14
                    account_type_id__account_type="Administrator",
                    userinfo_id__municipality_id__in=[municipality_assigned.pk, 14]
                )
            )

    if status_filter:
        accounts_query = accounts_query.filter(acc_status_id=status_filter)

    account_type_filter = request.GET.get('acctype')
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
    
    # Pagination
    paginator = Paginator(all_accounts, 10)  # Show 10 accounts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    if request.method == 'POST':
        selected_ids = [sid for sid in request.POST.getlist('selected_records') if sid]
        new_status_id = request.POST.get('new_status')
        if selected_ids and new_status_id and admin_info:
            # Work with all_accounts queryset for batch operations, not just current page
            for acc in all_accounts.filter(pk__in=selected_ids):
                acc.acc_status_id_id = new_status_id
                acc.account_verified_by = admin_info
                if int(new_status_id) == 2:  # 2 = Verified
                    acc.account_isverified = True
                else:
                    acc.account_isverified = False
                acc.save()
            messages.success(request, f"Updated {len(selected_ids)} account(s).")
            return redirect('administrator:show_allaccounts')

    # Filter municipalities based on access level
    if is_superuser or is_pk14:
        municipalities = MunicipalityName.objects.all()
    else:
        municipalities = MunicipalityName.objects.filter(
            Q(pk=14) | Q(pk=municipality_assigned.pk)
        )

    status_choices = AccountStatus.objects.all()
    # For bulk actions, limit to Verified (pk=2) and Suspended (pk=6) only
    bulk_action_status_choices = AccountStatus.objects.filter(pk__in=[2, 6])
    
    # Handle export requests
    export_type = request.GET.get('export')
    export_format = request.GET.get('format')
    
    if export_type and export_format:
        if export_type == 'records':
            return export_accounts_csv(all_accounts, 'all_accounts', export_format, request)
        elif export_type == 'summary':
            return export_accounts_summary_csv(all_accounts, 'all_accounts_summary', export_format, request)
    
    context = get_admin_context(request)
    context.update({
        'allAccounts': page_obj.object_list,  # Paginated accounts for display
        'page_obj': page_obj,
        'paginator': paginator,
        'account_types': AccountType.objects.exclude(account_type='Farmer'),
        'status_choices': status_choices,
        'bulk_action_status_choices': bulk_action_status_choices,  # Limited choices for bulk actions
        'municipalities': municipalities,
        'current_municipality': municipality_filter,
        'current_status': status_filter,
        'current_acctype': account_type_filter,
        'current_sort': sort_by,
        'current_order': order,
        'is_superuser': is_superuser,
        'is_pk14': is_pk14,
        'user_role_id': user_role_id,
    })

    return render(request, 'admin_panel/show_allaccounts.html', context)

@admin_or_agriculturist_required
@require_POST
def change_account_type(request, account_id):
    user_info = request.user.userinformation
    account_info = AccountsInformation.objects.get(userinfo_id=user_info)
    admin_info = AdminInformation.objects.get(userinfo_id=user_info)

    account = get_object_or_404(AccountsInformation, pk=account_id)
    new_type_id = request.POST.get('new_type')
    
    # Get account holder's full name for logging
    account_holder_name = f"{account.userinfo_id.firstname} {account.userinfo_id.lastname}"
    old_account_type = account.account_type_id.account_type

    if account.account_type_id.account_type == "Agriculturist":
        new_type = get_object_or_404(AccountType, pk=new_type_id)
        account.account_type_id = new_type
        account.save()
        
        # Create detailed AdminUserManagement log entry
        AdminUserManagement.objects.create(
            admin_id=admin_info,
            action=f"Changed {account_holder_name}'s account type from '{old_account_type}' to '{new_type.account_type}'",
            content_type=ContentType.objects.get_for_model(AccountsInformation),
            object_id=account.account_id
        )
        
        messages.success(request, f"Account type for {account_holder_name} updated successfully from {old_account_type} to {new_type.account_type}.")
    else:
        messages.warning(request, f"Only Agriculturist accounts can be updated. {account_holder_name} has account type: {old_account_type}")

    return redirect('administrator:show_allaccounts')  # or wherever the list view lives

@admin_or_agriculturist_required    
def farmer_transaction_history(request, account_id):
    """View to display transaction history for a specific farmer account"""
    context = get_admin_context(request)
    
    try:
        # Get current admin/agriculturist info for municipality filtering
        user = request.user
        userinfo = UserInformation.objects.get(auth_user=user)
        admin_info = AdminInformation.objects.get(userinfo_id=userinfo)
        municipality_assigned = admin_info.municipality_incharge
        is_superuser = user.is_superuser
        is_pk14 = municipality_assigned.pk == 14  # Administrator
        
        # Get the farmer's account information
        farmer_account = AccountsInformation.objects.get(
            pk=account_id, 
            account_type_id=1  # Ensure it's a farmer account
        )
        
        # Check if agriculturist has access to this farmer
        if not is_superuser and not is_pk14:
            # Check if this farmer falls under the agriculturist's assigned municipality
            farmer_accessible = AccountsInformation.objects.filter(
                pk=account_id,
                account_type_id=1
            ).filter(
                Q(userinfo_id__municipality_id=municipality_assigned) |  # Farmer's municipality matches
                Q(recordtransaction__farm_land__municipality=municipality_assigned) |  # Has farmland in municipality
                Q(recordtransaction__manual_municipality=municipality_assigned)  # Has transactions in municipality
            ).distinct().exists()
            
            if not farmer_accessible:
                messages.error(request, "You don't have access to view this farmer's information.")
                return redirect('administrator:verify_accounts')
        
        # Get transactions for this farmer, filtered by municipality for agriculturists
        transactions_query = RecordTransaction.objects.filter(
            account_id=farmer_account
        )
        
        # Apply municipality filtering for agriculturists
        if not is_superuser and not is_pk14:
            transactions_query = transactions_query.filter(
                Q(farm_land__municipality=municipality_assigned) |  # Farmland in assigned municipality
                Q(manual_municipality=municipality_assigned)  # Manual location in assigned municipality
            )
        
        transactions = transactions_query.order_by('-transaction_date')
        
        # Get farmer's farm lands
        farm_lands = FarmLand.objects.filter(
            userinfo_id=farmer_account.userinfo_id
        ).select_related('municipality', 'barangay')
        
        # Filter farm lands for agriculturists
        if not is_superuser and not is_pk14:
            farm_lands = farm_lands.filter(municipality=municipality_assigned)
        
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
            'farmer_age': age,
            'is_agriculturist': not is_superuser and not is_pk14,
            'assigned_municipality': municipality_assigned.municipality if not is_superuser and not is_pk14 else None
        })
        
    except AccountsInformation.DoesNotExist:
        messages.error(request, "Farmer account not found.")
        return redirect('administrator:verify_accounts')
    except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
        messages.error(request, "Admin information not found.")
        return redirect('administrator:verify_accounts')
    
    return render(request, 'admin_panel/farmer_transaction_history.html', context)

@admin_or_agriculturist_required
def farmer_transaction_detail(request, transaction_id):
    """View to display detailed information for a specific transaction"""
    context = get_admin_context(request)
    
    try:
        # Get current admin/agriculturist info for municipality filtering
        user = request.user
        userinfo = UserInformation.objects.get(auth_user=user)
        admin_info = AdminInformation.objects.get(userinfo_id=userinfo)
        municipality_assigned = admin_info.municipality_incharge
        is_superuser = user.is_superuser
        is_pk14 = municipality_assigned.pk == 14  # Administrator
        
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
        
        # Check municipality access for agriculturists
        if not is_superuser and not is_pk14:
            transaction_municipality = None
            if transaction.location_type == 'farm_land' and transaction.farm_land:
                transaction_municipality = transaction.farm_land.municipality
            elif transaction.manual_municipality:
                transaction_municipality = transaction.manual_municipality
            
            if transaction_municipality != municipality_assigned:
                messages.error(request, "You don't have access to view this transaction.")
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
            'farmer_account': transaction.account_id,
            'is_agriculturist': not is_superuser and not is_pk14,
            'assigned_municipality': municipality_assigned.municipality if not is_superuser and not is_pk14 else None
        })
        
    except RecordTransaction.DoesNotExist:
        messages.error(request, "Transaction not found.")
        return redirect('administrator:verify_accounts')
    except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
        messages.error(request, "Admin information not found.")
        return redirect('administrator:verify_accounts')
    
    return render(request, 'admin_panel/farmer_transaction_detail.html', context)

@admin_or_agriculturist_required
def assign_account(request):
    user = request.user
    
    # Get user role info for access control
    user_info = user.userinformation
    account_info = AccountsInformation.objects.get(userinfo_id=user_info)
    admin_info = AdminInformation.objects.get(userinfo_id=user_info)
    municipality_assigned = admin_info.municipality_incharge
    is_superuser = user.is_superuser
    is_pk14 = municipality_assigned.pk == 14  # Overall in Bataan
    user_role_id = account_info.account_type_id.pk
    
    # Allow both superusers and administrators (pk=2) to access
    if user_role_id != 2:
        return render(request, 'admin_panel/access_denied.html', {
            'error_message': 'Access denied. Only administrators can create accounts.'
        })

    if request.method == 'POST':
        form = AssignAdminAgriForm(request.POST, user=user, admin_info=admin_info)
        
        if form.is_valid():
            email = form.cleaned_data['email']
            first_name = form.cleaned_data['first_name']
            middle_name = form.cleaned_data['middle_name']
            last_name = form.cleaned_data['last_name']
            sex = form.cleaned_data['sex']
            account_type = form.cleaned_data['account_type']
            municipality = form.cleaned_data.get('municipality')  # Required only for agriculturist

            # Server-side validation based on access control rules
            validation_error = None
            
            if is_superuser:
                # Superuser can assign any type with any municipality
                pass
            elif is_pk14:
                # Administrator with pk=14 can assign admin and agriculturist but not pk=14
                if municipality and municipality.pk == 14:
                    validation_error = "You cannot assign accounts to 'Overall in Bataan' municipality."
            else:
                # Administrator with municipality != pk=14 can only assign agriculturists in their municipality
                if account_type != 'Agriculturist':
                    validation_error = "You can only create Agriculturist accounts."
                elif municipality and municipality.pk == 14:
                    validation_error = "You cannot assign accounts to 'Overall in Bataan' municipality."
                elif municipality and municipality.pk != municipality_assigned.pk:
                    validation_error = f"You can only assign accounts to your municipality: {municipality_assigned.municipality}."
            
            if validation_error:
                form.add_error(None, validation_error)
            # Check if email already exists
            elif AuthUser.objects.filter(email=email).exists():
                form.add_error('email', 'Email already exists in the system.')
            else:
                try:
                    with transaction.atomic():
                        # Generate a strong password
                        generated_password = get_random_string(length=12)

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

                        # Create AccountsInformation with Verified status instead of Pending
                        acct_type = AccountType.objects.get(account_type=account_type)
                        acct_status = AccountStatus.objects.get(pk=2)  # pk=2 = Verified
                        account_info_new = AccountsInformation.objects.create(
                            userinfo_id=userinfo,
                            account_type_id=acct_type,
                            acc_status_id=acct_status,
                            account_register_date=timezone.now(),
                            account_isverified=True,  # Set as verified
                            account_verified_date=timezone.now(),  # Set verification date
                            account_verified_by=admin_info  # Set verified by current admin
                        )

                        # Create AdminInformation (even for agriculturist)
                        new_admin_info = AdminInformation.objects.create(
                            userinfo_id=userinfo,
                            municipality_incharge=municipality
                        )

                        # Log the action in AdminUserManagement for tracking
                        account_holder_name = f"{first_name} {last_name}"
                        AdminUserManagement.objects.create(
                            admin_id=admin_info,
                            action=f"Created new {account_type} account for {account_holder_name} (Email: {email}) assigned to {municipality.municipality}",
                            content_type=ContentType.objects.get_for_model(AccountsInformation),
                            object_id=account_info_new.pk
                        )

                        # Send email with credentials
                        email_sent = send_mail(
                            subject="Fruit Cast Admin Account Created",
                            message=f"Hello {first_name},\n\nYour admin account has been created.\nEmail: {email}\nPassword: {generated_password}\n\nPlease log in and change your password.",
                            from_email="eloisamariemsumbad@gmail.com",
                            recipient_list=[email],
                            fail_silently=False,
                        )

                        if email_sent:
                            messages.success(request, f"{account_type} account for {account_holder_name} created successfully and logged in AdminUserManagement.")
                            return redirect('administrator:assign_account')
                        else:
                            raise Exception("Failed to send email. Account creation aborted.")

                except Exception as e:
                    form.add_error(None, f"Something went wrong: {e}")
    else:
        form = AssignAdminAgriForm(user=user, admin_info=admin_info)

    context = get_admin_context(request)
    context.update({
        'form': form,
        'is_superuser': is_superuser,
        'is_pk14': is_pk14,
        'user_role_id': user_role_id,
        'municipality_assigned': municipality_assigned
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
    
    commodities = CommodityType.objects.exclude(pk=1).order_by('name')  # Exclude 'Not Listed' commodity and order alphabetically
    
    # Pagination
    paginator = Paginator(commodities, 10)  # Show 10 commodities per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_admin_context(request)
    context.update({
        'commodities': page_obj.object_list,  # Pass the actual commodities for display
        'page_obj': page_obj,
        'paginator': page_obj.paginator,
        'is_paginated': paginator.num_pages > 1,
    })
    return render(request, 'admin_panel/admin_commodity.html', context)


@login_required
@admin_or_agriculturist_required
def admin_commodity_add_edit(request, pk=None):
    if request.method == "POST" and request.FILES.get("csv_file"):
        csv_file = request.FILES["csv_file"]
        created_count = 0
        updated_count = 0
        error_count = 0
        error_details = []
        
        try:
            decoded_file = csv_file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded_file))
            
            # Check if required headers exist
            required_headers = ['name', 'average_weight_per_unit_kg', 'seasonal_months', 'years_to_mature', 'years_to_bearfruit']
            if not all(header in reader.fieldnames for header in required_headers):
                missing_headers = [h for h in required_headers if h not in reader.fieldnames]
                messages.error(request, f"CSV file is missing required headers: {', '.join(missing_headers)}. Please check the template format.")
            else:
                for row_num, row in enumerate(reader, start=2):  # Start at 2 because row 1 is headers
                    try:
                        # Clean up keys and values
                        row = {k.strip(): v.strip() for k, v in row.items()}
                        
                        # Validate required fields
                        if not row.get("name"):
                            error_details.append(f"Row {row_num}: Commodity name is required")
                            error_count += 1
                            continue
                            
                        name = row["name"]
                        
                        # Validate numeric fields
                        try:
                            avg_weight = float(row["average_weight_per_unit_kg"])
                            if avg_weight <= 0:
                                raise ValueError("Average weight must be positive")
                        except (ValueError, TypeError):
                            error_details.append(f"Row {row_num}: Invalid average weight per unit - must be a positive number")
                            error_count += 1
                            continue
                            
                        try:
                            years_to_mature = float(row["years_to_mature"])
                            if years_to_mature < 0:
                                raise ValueError("Years to mature cannot be negative")
                        except (ValueError, TypeError):
                            error_details.append(f"Row {row_num}: Invalid years to mature - must be a non-negative number")
                            error_count += 1
                            continue
                            
                        try:
                            years_to_bearfruit = float(row.get("years_to_bearfruit", 0))
                            if years_to_bearfruit < 0:
                                raise ValueError("Years to bear fruit cannot be negative")
                        except (ValueError, TypeError):
                            error_details.append(f"Row {row_num}: Invalid years to bear fruit - must be a non-negative number")
                            error_count += 1
                            continue
                        
                        # Check if commodity already exists
                        commodity, created = CommodityType.objects.get_or_create(
                            name=name,
                            defaults={
                                "average_weight_per_unit_kg": avg_weight,
                                "years_to_mature": years_to_mature,
                                "years_to_bearfruit": years_to_bearfruit,
                            }
                        )
                        
                        if not created:
                            # Update existing commodity
                            commodity.average_weight_per_unit_kg = avg_weight
                            commodity.years_to_mature = years_to_mature
                            commodity.years_to_bearfruit = years_to_bearfruit
                            commodity.save()
                            updated_count += 1
                        else:
                            created_count += 1
                        
                        # Handle seasonal months
                        seasonal_months_str = row.get("seasonal_months", "")
                        if seasonal_months_str:
                            months = [m.strip() for m in seasonal_months_str.split(";") if m.strip()]
                            month_objs = Month.objects.filter(name__in=months)
                            
                            # Check if all months were found
                            found_month_names = [month.name for month in month_objs]
                            invalid_months = [m for m in months if m not in found_month_names]
                            if invalid_months:
                                error_details.append(f"Row {row_num}: Invalid month names: {', '.join(invalid_months)}")
                                error_count += 1
                                continue
                                
                            commodity.seasonal_months.set(month_objs)
                        else:
                            commodity.seasonal_months.clear()
                            
                    except Exception as e:
                        error_details.append(f"Row {row_num}: Unexpected error - {str(e)}")
                        error_count += 1
                        continue
                
                # Show appropriate messages
                if created_count > 0:
                    messages.success(request, f"Successfully created {created_count} new commodit{'ies' if created_count > 1 else 'y'} from CSV upload.")
                    
                if updated_count > 0:
                    messages.info(request, f"Successfully updated {updated_count} existing commodit{'ies' if updated_count > 1 else 'y'} from CSV upload.")
                    
                if error_count > 0:
                    messages.error(request, f"Failed to process {error_count} row{'s' if error_count > 1 else ''} due to errors:")
                    for error_detail in error_details[:10]:  # Show first 10 errors to avoid overwhelming UI
                        messages.error(request, error_detail)
                    if len(error_details) > 10:
                        messages.error(request, f"... and {len(error_details) - 10} more errors.")
                        
                if created_count == 0 and updated_count == 0 and error_count == 0:
                    messages.warning(request, "No data was processed from the CSV file.")
                    
        except Exception as e:
            messages.error(request, f"Error reading CSV file: {str(e)}. Please ensure the file is properly formatted.")
            
        # Stay on the same page to show messages
        if pk:
            commodity = get_object_or_404(CommodityType, pk=pk)
        else:
            commodity = None
        form = CommodityTypeForm(instance=commodity)
        context = get_admin_context(request)
        context.update({'form': form, 'commodity': commodity})
        return render(request, 'admin_panel/commodity_add.html', context)

    
    if pk:
        commodity = get_object_or_404(CommodityType, pk=pk)
    else:
        commodity = None

    if request.method == 'POST':
        form = CommodityTypeForm(request.POST, instance=commodity)
        if form.is_valid():
            commodity_obj = form.save()
            if pk:
                messages.success(request, f'Commodity "{commodity_obj.name}" has been successfully updated.')
            else:
                messages.success(request, f'Commodity "{commodity_obj.name}" has been successfully created.')
            return redirect('administrator:admin_commodity_list')
        else : 
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CommodityTypeForm(instance=commodity)

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
    is_superuser = user.is_superuser
    is_pk14 = municipality_assigned.pk == 14

    # Filters
    filter_municipality = request.GET.get('municipality')
    filter_commodity = request.GET.get('commodity')
    filter_status = request.GET.get('status')

    # Municipality filter logic - always use initPlantRecord for all users
    if is_superuser or is_pk14:
        municipalities = MunicipalityName.objects.exclude(pk=14)
        records = initPlantRecord.objects.select_related(
            'commodity_id', 'record_status', 'transaction', 
            'transaction__account_id__userinfo_id', 'verified_by__userinfo_id'
        ).order_by('-plant_id')
    else:
        municipalities = MunicipalityName.objects.filter(pk=municipality_assigned.pk)
        records = initPlantRecord.objects.select_related(
            'commodity_id', 'record_status', 'transaction', 
            'transaction__account_id__userinfo_id', 'verified_by__userinfo_id'
        ).filter(
            Q(transaction__farm_land__municipality=municipality_assigned) |
            Q(transaction__manual_municipality=municipality_assigned)
        ).order_by('-plant_id')

    # Apply filters
    if filter_municipality:
        records = records.filter(
            Q(transaction__farm_land__municipality__pk=filter_municipality) |
            Q(transaction__manual_municipality__pk=filter_municipality)
        )
    elif not (is_superuser or is_pk14):
        # For non-superuser/non-pk14 users, ensure they only see their municipality records
        records = records.filter(
            Q(transaction__farm_land__municipality=municipality_assigned) |
            Q(transaction__manual_municipality=municipality_assigned)
        )
    
    if filter_commodity:
        records = records.filter(commodity_id__pk=filter_commodity)
    if filter_status:
        records = records.filter(record_status__pk=filter_status)

    # Pagination
    paginator = Paginator(records, 10)  # Show 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.method == "POST":
        selected_ids = request.POST.getlist('selected_records')
        new_status_pk = int(request.POST.get('new_status'))
        verified_status_pk = 2  # pk for "Verified"
        new_status = AccountStatus.objects.get(pk=new_status_pk)
        
        # Get all matching records (not just the current page) for batch operations
        all_records = records  # Use the already filtered queryset
        
        for rec in all_records.filter(pk__in=selected_ids):
            # Store old status for logging
            old_status = rec.record_status.acc_status if rec.record_status else "None"
            
            rec.record_status = new_status
            if not rec.verified_by:
                rec.verified_by = admin_info
            rec.save()
            
            # Create AdminUserManagement log entry for status change
            AdminUserManagement.objects.create(
                admin_id=admin_info,
                action=f"Plant Record ID {rec.plant_id} changed status from '{old_status}' to '{new_status.acc_status}'",
                content_type=ContentType.objects.get_for_model(initPlantRecord),
                object_id=rec.plant_id
            )
            
            # Handle verified record creation and deletion based on status
            if new_status_pk == verified_status_pk:
                # Only create VerifiedPlantRecord if status is "Verified" and not already created
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
                    verified_plant_record = VerifiedPlantRecord.objects.create(
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
                    
                    # Log the creation of verified plant record
                    AdminUserManagement.objects.create(
                        admin_id=admin_info,
                        action=f"Created Verified Plant Record ID {verified_plant_record.id} from Plant Record ID {rec.plant_id}",
                        content_type=ContentType.objects.get_for_model(VerifiedPlantRecord),
                        object_id=verified_plant_record.id
                    )
            elif new_status_pk == 4:  # Rejected status
                # Delete any existing VerifiedPlantRecord for this init record
                verified_records = VerifiedPlantRecord.objects.filter(prev_record=rec)
                if verified_records.exists():
                    for verified_record in verified_records:
                        verified_record_id = verified_record.id
                        verified_record.delete()
                        
                        # Log the deletion of verified plant record
                        AdminUserManagement.objects.create(
                            admin_id=admin_info,
                            action=f"Deleted Verified Plant Record ID {verified_record_id} due to Plant Record ID {rec.plant_id} being rejected",
                            content_type=ContentType.objects.get_for_model(VerifiedPlantRecord),
                            object_id=verified_record_id
                        )
        messages.success(request, "Selected records updated successfully.")
    else:
        messages.error(request, "No records selected or status not chosen.")

    commodities = CommodityType.objects.all()
    status_choices = AccountStatus.objects.filter(acc_stat_id__in=[2, 3, 4, 7])  # Only verified, pending, rejected, and removed

    # Handle export requests
    export_type = request.GET.get('export')
    export_format = request.GET.get('format')
    
    if export_type and export_format:
        if export_type == 'records':
            return export_plant_records_csv(records, 'plant_verification_records', export_format, request)
        elif export_type == 'summary':
            return export_plant_records_summary_csv(records, 'plant_verification_summary', export_format)

    context = get_admin_context(request)
    context.update({
        'records': page_obj.object_list,  # Pass the actual records for display
        'page_obj': page_obj,
        'paginator': page_obj.paginator,
        'municipalities': municipalities,
        'commodities': commodities,
        'status_choices': status_choices,
        'selected_municipality': filter_municipality,
        'selected_commodity': filter_commodity,
        'selected_status': filter_status,
        'is_agriculturist': not (is_superuser or is_pk14),
        'assigned_municipality': municipality_assigned,
        'is_paginated': paginator.num_pages > 1,
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
        municipalities = MunicipalityName.objects.exclude(pk=14)
    else:
        municipalities = MunicipalityName.objects.filter(pk=admin_info.municipality_incharge.pk)

    commodities = CommodityType.objects.all()
    status_choices = AccountStatus.objects.filter(acc_stat_id__in=[2, 3, 4, 7])  # Only verified, pending, rejected, and removed

    # Query records with sorting by ID (most recent first) and pagination
    records = initHarvestRecord.objects.select_related(
        'unit', 'commodity_id', 'record_status', 'transaction', 
        'transaction__account_id__userinfo_id', 'verified_by__userinfo_id'
    ).order_by('-harvest_id')
    if selected_municipality:
        records = records.filter(
            Q(transaction__farm_land__municipality__pk=selected_municipality) |
            Q(transaction__manual_municipality__pk=selected_municipality)
        )
    elif not (is_superuser or is_pk14):
        records = records.filter(
            Q(transaction__farm_land__municipality=admin_info.municipality_incharge) |
            Q(transaction__manual_municipality=admin_info.municipality_incharge)
        )
    if selected_commodity:
        records = records.filter(commodity_id__pk=selected_commodity)
    if selected_status:
        records = records.filter(record_status__pk=selected_status)

    # Pagination
    paginator = Paginator(records, 10)  # Show 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Add converted weight in kg for each record in the current page
    for record in page_obj:
        record.total_weight_kg = convert_to_kg(record.total_weight, record.unit.unit_abrv)

    # Batch update
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_records')
        new_status_pk = int(request.POST.get('new_status'))
        verified_status_pk = 2  # pk for "Verified"
        new_status = AccountStatus.objects.get(pk=new_status_pk)
        
        # Get all matching records (not just the current page) for batch operations
        all_records = initHarvestRecord.objects.select_related(
            'unit', 'commodity_id', 'record_status', 'transaction', 
            'transaction__account_id__userinfo_id', 'verified_by__userinfo_id'
        )
        if selected_municipality:
            all_records = all_records.filter(
                Q(transaction__farm_land__municipality__pk=selected_municipality) |
                Q(transaction__manual_municipality__pk=selected_municipality)
            )
        elif not (is_superuser or is_pk14):
            all_records = all_records.filter(
                Q(transaction__farm_land__municipality=admin_info.municipality_incharge) |
                Q(transaction__manual_municipality=admin_info.municipality_incharge)
            )
        if selected_commodity:
            all_records = all_records.filter(commodity_id__pk=selected_commodity)
        if selected_status:
            all_records = all_records.filter(record_status__pk=selected_status)
        
        for rec in all_records.filter(pk__in=selected_ids):
            # Store old status for logging
            old_status = rec.record_status.acc_status if rec.record_status else "None"
            
            rec.record_status = new_status
            if not rec.verified_by:
                rec.verified_by = admin_info
            rec.save()
            
            # Create AdminUserManagement log entry for status change
            AdminUserManagement.objects.create(
                admin_id=admin_info,
                action=f"Harvest Record ID {rec.harvest_id} changed status from '{old_status}' to '{new_status.acc_status}'",
                content_type=ContentType.objects.get_for_model(initHarvestRecord),
                object_id=rec.harvest_id
            )
            
            # Handle verified record creation and deletion based on status
            if new_status_pk == verified_status_pk and selected_ids:
                # Only create VerifiedHarvestRecord if status is "Verified" and not already created
                if not VerifiedHarvestRecord.objects.filter(prev_record=rec).exists():
                    try : 
                        if rec.transaction.farm_land:
                            municipality = rec.transaction.farm_land.municipality
                            barangay = rec.transaction.farm_land.barangay
                        else:
                            municipality = rec.transaction.manual_municipality
                            barangay = rec.transaction.manual_barangay

                        # Convert weights to kg before storing
                        total_weight_kg = convert_to_kg(rec.total_weight, rec.unit.unit_abrv)

                        verified_harvest_record = VerifiedHarvestRecord.objects.create(
                            harvest_date=rec.harvest_date,
                            commodity_id=rec.commodity_id,
                            total_weight_kg=total_weight_kg,
                            remarks=rec.remarks,
                            municipality=municipality,
                            barangay=barangay,
                            verified_by=admin_info,  # set this to the current admin
                            prev_record=rec,
                        )
                        
                        # Log the creation of verified harvest record
                        AdminUserManagement.objects.create(
                            admin_id=admin_info,
                            action=f"Created Verified Harvest Record ID {verified_harvest_record.id} from Harvest Record ID {rec.harvest_id}",
                            content_type=ContentType.objects.get_for_model(VerifiedHarvestRecord),
                            object_id=verified_harvest_record.id
                        )
                        
                        # ...
                        logger.info("Attempting to delay Celery task...")
                        logger.info(f"Using broker URL: {settings.CELERY_BROKER_URL}") # This will show the URL Celery sees
                        retrain_and_generate_forecasts_task.delay()
                        messages.success(request, "Records verified. Forecast models are being updated in the background.")
                        
                    except Exception as e:
                        logger.error(f"Error during verification: {e}")
                        messages.error(request, f"An error occurred during verification: {e}")
            elif new_status_pk == 4:  # Rejected status
                # Delete any existing VerifiedHarvestRecord for this init record
                verified_records = VerifiedHarvestRecord.objects.filter(prev_record=rec)
                if verified_records.exists():
                    for verified_record in verified_records:
                        verified_record_id = verified_record.id
                        verified_record.delete()
                        
                        # Log the deletion of verified harvest record
                        AdminUserManagement.objects.create(
                            admin_id=admin_info,
                            action=f"Deleted Verified Harvest Record ID {verified_record_id} due to Harvest Record ID {rec.harvest_id} being rejected",
                            content_type=ContentType.objects.get_for_model(VerifiedHarvestRecord),
                            object_id=verified_record_id
                        )


                       # for rec in records.filter(pk__in=selected_ids):
                       #     rec.record_status = new_status
                       #     if not rec.verified_by:
                       #         rec.verified_by = admin_info
                       #     rec.save()
        messages.success(request, "Selected records updated successfully.")
    else:
        messages.error(request, "No records selected or status not chosen.")

    # Handle export requests
    export_type = request.GET.get('export')
    export_format = request.GET.get('format')
    
    if export_type and export_format:
        if export_type == 'records':
            return export_harvest_records_csv(records, 'harvest_verification_records', export_format, request)
        elif export_type == 'summary':
            return export_harvest_records_summary_csv(records, 'harvest_verification_summary', export_format, request)
    
    context = get_admin_context(request)
    context.update({
        'records': page_obj.object_list,  # Pass the actual records for display
        'page_obj': page_obj,
        'paginator': page_obj.paginator,
        'municipalities': municipalities,
        'commodities': commodities,
        'status_choices': status_choices,
        'selected_municipality': selected_municipality,
        'selected_commodity': selected_commodity,
        'selected_status': selected_status,
        'is_agriculturist': not (is_superuser or is_pk14),
        'assigned_municipality': admin_info.municipality_incharge,
        'is_paginated': paginator.num_pages > 1,
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
        created_count = 0
        error_count = 0
        error_details = []
        
        try:
            decoded_file = csv_file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded_file))
            
            # Check if required headers exist
            required_headers = ['harvest_date', 'commodity', 'municipality', 'total_weight_kg']
            if not all(header in reader.fieldnames for header in required_headers):
                missing_headers = [h for h in required_headers if h not in reader.fieldnames]
                messages.error(request, f"CSV file is missing required headers: {', '.join(missing_headers)}. Please check the template format.")
            else:
                for row_num, row in enumerate(reader, start=2):  # Start at 2 because row 1 is headers
                    try:
                        row = {k.strip(): v.strip() for k, v in row.items()}
                        
                        # Validate required fields
                        if not row.get("harvest_date"):
                            error_details.append(f"Row {row_num}: Harvest date is required")
                            error_count += 1
                            continue
                            
                        if not row.get("commodity"):
                            error_details.append(f"Row {row_num}: Commodity is required")
                            error_count += 1
                            continue
                            
                        if not row.get("municipality"):
                            error_details.append(f"Row {row_num}: Municipality is required")
                            error_count += 1
                            continue
                            
                        if not row.get("total_weight_kg"):
                            error_details.append(f"Row {row_num}: Total weight is required")
                            error_count += 1
                            continue
                        
                        # Validate harvest date format
                        try:
                            harvest_date = datetime.strptime(row["harvest_date"], "%Y-%m-%d").date()
                        except ValueError:
                            error_details.append(f"Row {row_num}: Invalid harvest date format. Use YYYY-MM-DD format")
                            error_count += 1
                            continue
                        
                        # Validate total weight
                        try:
                            total_weight_kg = float(row["total_weight_kg"])
                            if total_weight_kg <= 0:
                                raise ValueError("Weight must be positive")
                        except (ValueError, TypeError):
                            error_details.append(f"Row {row_num}: Invalid total weight - must be a positive number")
                            error_count += 1
                            continue
                        
                        # Process commodity name as string
                        commodity_name = row['commodity'].strip()
                        try:
                            commodity_obj = CommodityType.objects.get(name__iexact=commodity_name)
                        except CommodityType.DoesNotExist:
                            error_details.append(f"Row {row_num}: Commodity '{commodity_name}' does not exist in database")
                            error_count += 1
                            continue
                        
                        # Process municipality name as string
                        municipality_name = row['municipality'].strip()
                        try:
                            municipality = MunicipalityName.objects.get(municipality__iexact=municipality_name)
                        except MunicipalityName.DoesNotExist:
                            error_details.append(f"Row {row_num}: Municipality '{municipality_name}' does not exist in database")
                            error_count += 1
                            continue
                        
                        # Process barangay name as string (optional)
                        barangay_name = row.get("barangay", "").strip()
                        barangay = None
                        if barangay_name:
                            try:
                                barangay = BarangayName.objects.get(barangay__iexact=barangay_name, municipality_id=municipality)
                            except BarangayName.DoesNotExist:
                                error_details.append(f"Row {row_num}: Barangay '{barangay_name}' not found in '{municipality_name}'. Record will be created without barangay")
                                # Don't skip the row, just proceed without barangay
                        
                        verified_harvest_record = VerifiedHarvestRecord.objects.create(
                            harvest_date=harvest_date,
                            commodity_id=commodity_obj,
                            total_weight_kg=total_weight_kg,
                            municipality=municipality,
                            barangay=barangay,
                            remarks=row.get("remarks", ""),
                            date_verified=timezone.now(),
                            verified_by=admin_info,
                            prev_record=None,
                        )
                        
                        # Log the creation from CSV upload
                        AdminUserManagement.objects.create(
                            admin_id=admin_info,
                            action=f"Created Verified Harvest Record ID {verified_harvest_record.id} via CSV upload - {commodity_obj.name} ({total_weight_kg}kg) from {municipality_name}",
                            content_type=ContentType.objects.get_for_model(VerifiedHarvestRecord),
                            object_id=verified_harvest_record.id
                        )
                        
                        created_count += 1
                        
                    except Exception as e:
                        error_details.append(f"Row {row_num}: Unexpected error - {str(e)}")
                        error_count += 1
                        continue
                
                # Show appropriate messages
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
                    messages.error(request, f"Failed to process {error_count} row{'s' if error_count > 1 else ''} due to errors:")
                    for error_detail in error_details[:10]:  # Show first 10 errors to avoid overwhelming UI
                        messages.error(request, error_detail)
                    if len(error_details) > 10:
                        messages.error(request, f"... and {len(error_details) - 10} more errors.")
                        
                if created_count == 0 and error_count == 0:
                    messages.warning(request, "No data was processed from the CSV file.")
                    
        except Exception as e:
            messages.error(request, f"Error reading CSV file: {str(e)}. Please ensure the file is properly formatted.")
            
        # Stay on the same page to show messages
        context = get_admin_context(request)
        context.update({'municipalities': municipalities, 'form': VerifiedHarvestRecordForm()})
        return render(request, 'admin_panel/verifyharvest_add.html', context)

    elif request.method == "POST":
        form = VerifiedHarvestRecordForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.date_verified = timezone.now()
            rec.verified_by = admin_info
            rec.prev_record = None
            rec.save()
            
            # Log the individual record creation
            AdminUserManagement.objects.create(
                admin_id=admin_info,
                action=f"Created Verified Harvest Record ID {rec.id} via manual entry - {rec.commodity_id.name} ({rec.total_weight_kg}kg) from {rec.municipality.municipality if rec.municipality else 'Unknown'}",
                content_type=ContentType.objects.get_for_model(VerifiedHarvestRecord),
                object_id=rec.id
            )
            
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
    user = request.user
    userinfo = UserInformation.objects.get(auth_user=user)
    admin_info = AdminInformation.objects.get(userinfo_id=userinfo)
    is_superuser = user.is_superuser
    is_pk14 = admin_info.municipality_incharge.pk == 14
    
    # Define filter variables early to be used in POST handling
    municipality_filter = request.GET.get('municipality')
    barangay_filter = request.GET.get('barangay')
    commodity_filter = request.GET.get('commodity')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_records = request.POST.getlist('selected_records')
        
        if action == 'delete' and selected_records:
            try:                
                # Get all matching records for deletion (not just current page)
                all_records = VerifiedHarvestRecord.objects.select_related('commodity_id', 'municipality', 'barangay', 'verified_by__userinfo_id')
                
                # Apply same filters as display logic
                if municipality_filter:
                    all_records = all_records.filter(municipality_id=municipality_filter)
                elif not (is_superuser or is_pk14):
                    all_records = all_records.filter(municipality=admin_info.municipality_incharge)
                if barangay_filter:
                    all_records = all_records.filter(barangay_id=barangay_filter)
                if commodity_filter:
                    all_records = all_records.filter(commodity_id=commodity_filter)
                if date_from:
                    all_records = all_records.filter(harvest_date__gte=date_from)
                if date_to:
                    all_records = all_records.filter(harvest_date__lte=date_to)
                
                # Delete selected records
                deleted_count = 0
                for record_id in selected_records:
                    record = all_records.filter(pk=record_id).first()
                    if record:
                        # Log the deletion before deleting the record
                        AdminUserManagement.objects.create(
                            admin_id=admin_info,
                            action=f"Deleted Verified Harvest Record ID {record.id} - {record.commodity_id.name} ({record.total_weight_kg}kg) from {record.harvest_date}",
                            content_type=ContentType.objects.get_for_model(VerifiedHarvestRecord),
                            object_id=record.id
                        )
                        
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
    
    # Only show allowed municipalities (same logic as admin_verifyharvestrec)
    if is_superuser or is_pk14:
        municipalities = MunicipalityName.objects.exclude(pk=14)
    else:
        municipalities = MunicipalityName.objects.filter(pk=admin_info.municipality_incharge.pk)
    
    # Filter barangays based on selected municipality if applicable
    if municipality_filter:
        barangays = BarangayName.objects.filter(municipality_id=municipality_filter)
    else:
        barangays = BarangayName.objects.all()
    
    commodities = CommodityType.objects.all()
    
    records = VerifiedHarvestRecord.objects.select_related('commodity_id', 'municipality', 'barangay', 'verified_by__userinfo_id').order_by('-date_verified')
    
    if municipality_filter:
        records = records.filter(municipality_id=municipality_filter)
    elif not (is_superuser or is_pk14):
        # If not superuser or pk14, filter by admin's municipality
        records = records.filter(municipality=admin_info.municipality_incharge)
    if barangay_filter:
        records = records.filter(barangay_id=barangay_filter)
    if commodity_filter:
        records = records.filter(commodity_id=commodity_filter)
    if date_from:
        records = records.filter(harvest_date__gte=date_from)
    if date_to:
        records = records.filter(harvest_date__lte=date_to)
    
    # Pagination
    paginator = Paginator(records, 10)  # Show 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Handle export requests
    export_type = request.GET.get('export')
    export_format = request.GET.get('format')
    
    if export_type and export_format:
        if export_type == 'records':
            return export_verified_harvest_records_csv(records, 'verified_harvest_records', export_format)
        elif export_type == 'summary':
            return export_verified_harvest_records_summary_csv(records, 'verified_harvest_summary', export_format)

    context = get_admin_context(request)
    context.update({
        'records': page_obj.object_list,  # Pass the actual records for display
        'page_obj': page_obj,
        'paginator': page_obj.paginator,
        'municipalities': municipalities,
        'barangays': barangays,
        'commodities': commodities,
        'selected_municipality': municipality_filter,
        'selected_barangay': barangay_filter,
        'selected_commodity': commodity_filter,
        'date_from': date_from,
        'date_to': date_to,
        'is_paginated': paginator.num_pages > 1,
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
            # Get admin info for logging
            admin_info = AdminInformation.objects.get(userinfo_id=request.user.userinformation)
            
            # Store original values for comparison
            original_data = {
                'harvest_date': record.harvest_date,
                'commodity': record.commodity_id.name,
                'total_weight_kg': record.total_weight_kg,
                'weight_per_unit_kg': record.weight_per_unit_kg,
                'municipality': record.municipality.municipality if record.municipality else 'None',
                'barangay': record.barangay.barangay if record.barangay else 'None',
                'remarks': record.remarks or 'None'
            }
            
            updated_record = form.save(commit=False)
            # Keep the original verification info
            updated_record.verified_by = record.verified_by
            updated_record.date_verified = record.date_verified
            updated_record.save()
            
            # Log the edit with details of what changed
            changes = []
            if str(original_data['harvest_date']) != str(updated_record.harvest_date):
                changes.append(f"harvest_date: {original_data['harvest_date']} → {updated_record.harvest_date}")
            if original_data['commodity'] != updated_record.commodity_id.name:
                changes.append(f"commodity: {original_data['commodity']} → {updated_record.commodity_id.name}")
            if original_data['total_weight_kg'] != updated_record.total_weight_kg:
                changes.append(f"total_weight_kg: {original_data['total_weight_kg']} → {updated_record.total_weight_kg}")
            if original_data['weight_per_unit_kg'] != updated_record.weight_per_unit_kg:
                changes.append(f"weight_per_unit_kg: {original_data['weight_per_unit_kg']} → {updated_record.weight_per_unit_kg}")
            
            new_municipality = updated_record.municipality.municipality if updated_record.municipality else 'None'
            if original_data['municipality'] != new_municipality:
                changes.append(f"municipality: {original_data['municipality']} → {new_municipality}")
                
            new_barangay = updated_record.barangay.barangay if updated_record.barangay else 'None'
            if original_data['barangay'] != new_barangay:
                changes.append(f"barangay: {original_data['barangay']} → {new_barangay}")
                
            new_remarks = updated_record.remarks or 'None'
            if original_data['remarks'] != new_remarks:
                changes.append(f"remarks: {original_data['remarks']} → {new_remarks}")
            
            if changes:
                change_details = "; ".join(changes)
                AdminUserManagement.objects.create(
                    admin_id=admin_info,
                    action=f"Edited Verified Harvest Record ID {updated_record.id} - Changes: {change_details}",
                    content_type=ContentType.objects.get_for_model(VerifiedHarvestRecord),
                    object_id=updated_record.id
                )
            
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
    - Superuser: Full information for all accounts
    - Administrator: Full information for agriculturists, partial for administrators
    - Agriculturist: Full access to their own account only, blocked from viewing others
    """
    try:
        # Get current user info
        current_user_info = request.user.userinformation
        current_account = AccountsInformation.objects.get(userinfo_id=current_user_info)
        current_admin_info = AdminInformation.objects.filter(userinfo_id=current_user_info).first()
        current_municipality_assigned = current_admin_info.municipality_incharge if current_admin_info else None
        is_superuser = request.user.is_superuser
        is_pk14 = current_municipality_assigned.pk == 14 if current_municipality_assigned else False
        
        # Get the account to view
        target_account = get_object_or_404(AccountsInformation, pk=account_id)
        target_userinfo = target_account.userinfo_id
        target_admin_info = AdminInformation.objects.filter(userinfo_id=target_userinfo).first()
        
        # Check if target account is admin or agriculturist
        if target_account.account_type_id.account_type not in ["Administrator", "Agriculturist"]:
            messages.error(request, "You can only view administrator and agriculturist accounts.")
            return redirect('administrator:show_allaccounts')
        
        # Access control for agriculturists: they can only view their own account
        if current_account.account_type_id.pk == 3:  # Agriculturist
            if current_account.pk != target_account.pk:  # Not viewing their own account
                return render(request, 'admin_panel/access_denied.html', {
                    'error_message': 'Access denied. You can only view your own account details.'
                })
        
        # Access control for administrators
        if current_account.account_type_id.pk == 2 and not is_superuser:  # Administrator but not superuser
            target_municipality = target_admin_info.municipality_incharge if target_admin_info else None
            target_account_type = target_account.account_type_id.account_type
            
            if not is_pk14:  # Administrator with assigned municipality not pk=14
                # Can't see agriculturists in different municipalities
                if target_account_type == "Agriculturist":
                    if not target_municipality or target_municipality.pk != current_municipality_assigned.pk:
                        return render(request, 'admin_panel/access_denied.html', {
                            'error_message': 'Unauthorized access. You can only view agriculturists in your assigned municipality.'
                        })
                # Can see administrators in same municipality and pk=14
                elif target_account_type == "Administrator":
                    if not target_municipality or target_municipality.pk not in [current_municipality_assigned.pk, 14]:
                        return render(request, 'admin_panel/access_denied.html', {
                            'error_message': 'Unauthorized access. You can only view administrators in your municipality or assigned to Overall Bataan.'
                        })
        
        # Handle POST requests for editing account type and municipality
        if request.method == 'POST':
            action = request.POST.get('action')
            user_role_id = current_account.account_type_id.pk
            target_account_type_id = target_account.account_type_id.pk
            is_own_account = target_account.pk == current_account.pk
            
            # Prevent editing own account
            if is_own_account:
                messages.error(request, "You cannot edit your own account details.")
                return redirect('administrator:admin_account_detail', account_id=account_id)
            
            # Check permissions for editing based on complex rules
            can_edit_account_type = False
            can_edit_municipality = False
            
            if is_superuser:
                # Superuser can edit everything
                can_edit_account_type = True
                can_edit_municipality = True
            elif user_role_id == 2:  # Administrator
                if is_pk14:
                    # Administrator with pk=14
                    if target_account_type_id == 3:  # Agriculturist
                        can_edit_municipality = True  # Can edit agriculturist municipality (excluding pk=14)
                    elif target_account_type_id == 2:  # Administrator
                        target_municipality = target_admin_info.municipality_incharge if target_admin_info else None
                        if target_municipality and target_municipality.pk != 14:  # Administrator not pk=14
                            can_edit_municipality = True  # Can edit administrator municipality (excluding pk=14)
                else:
                    # Administrator with municipality not pk=14
                    if target_account_type_id == 3:  # Agriculturist in same municipality
                        # Can see agriculturists but can't edit account type or municipality
                        pass
            
            # Handle actions based on permissions
            if action == 'change_account_type':
                if not can_edit_account_type:
                    messages.error(request, "You don't have permission to edit account types.")
                    return redirect('administrator:admin_account_detail', account_id=account_id)
                    
                new_account_type_id = request.POST.get('new_account_type')
                if new_account_type_id:
                    try:
                        old_account_type = target_account.account_type_id.account_type
                        new_account_type = AccountType.objects.get(pk=new_account_type_id)
                        target_account.account_type_id = new_account_type
                        target_account.save()
                        
                        # Get account holder's full name for logging
                        account_holder_name = f"{target_account.userinfo_id.firstname} {target_account.userinfo_id.lastname}"
                        
                        # Log the action with detailed information
                        AdminUserManagement.objects.create(
                            admin_id=current_admin_info,
                            action=f"Changed {account_holder_name}'s account type from '{old_account_type}' to '{new_account_type.account_type}'",
                            content_type=ContentType.objects.get_for_model(AccountsInformation),
                            object_id=target_account.pk
                        )
                        
                        messages.success(request, f"Account type updated to {new_account_type.account_type}")
                    except Exception as e:
                        messages.error(request, f"Error updating account type: {str(e)}")
            
            # Handle municipality change
            elif action == 'change_municipality':
                if not can_edit_municipality:
                    messages.error(request, "You don't have permission to edit municipality assignments.")
                    return redirect('administrator:admin_account_detail', account_id=account_id)
                    
                new_municipality_id = request.POST.get('new_municipality')
                if new_municipality_id:
                    # Prevent assigning pk=14 if not superuser
                    if not is_superuser and int(new_municipality_id) == 14:
                        messages.error(request, "You cannot assign Overall Bataan (pk=14) municipality.")
                        return redirect('administrator:admin_account_detail', account_id=account_id)
                        
                    try:
                        old_municipality = target_admin_info.municipality_incharge.municipality if target_admin_info else "Unknown"
                        new_municipality = MunicipalityName.objects.get(pk=new_municipality_id)
                        if target_admin_info:
                            target_admin_info.municipality_incharge = new_municipality
                            target_admin_info.save()
                        
                        # Get account holder's full name for logging
                        account_holder_name = f"{target_account.userinfo_id.firstname} {target_account.userinfo_id.lastname}"
                        
                        # Log the action with detailed information
                        AdminUserManagement.objects.create(
                            admin_id=current_admin_info,
                            action=f"Changed {account_holder_name}'s municipality assignment from '{old_municipality}' to '{new_municipality.municipality}'",
                            content_type=ContentType.objects.get_for_model(AdminInformation),
                            object_id=target_admin_info.pk if target_admin_info else None
                        )
                        
                        messages.success(request, f"Municipality assignment for {account_holder_name} updated from {old_municipality} to {new_municipality.municipality}")
                    except Exception as e:
                        messages.error(request, f"Error updating municipality: {str(e)}")
            
            return redirect('administrator:admin_account_detail', account_id=account_id)
        
        # Determine access level based on hierarchical rules
        user_role_id = current_account.account_type_id.pk
        target_account_type_id = target_account.account_type_id.pk
        is_own_account = target_account.pk == current_account.pk
        
        # Complex access control based on the specified rules
        can_view_full_details = False
        can_view_histories = False
        can_edit_account_type = False
        can_edit_municipality = False
        
        if is_superuser:
            # Superuser: can see all information and edit everything
            can_view_full_details = True
            can_view_histories = True
            can_edit_account_type = not is_own_account
            can_edit_municipality = not is_own_account
        elif user_role_id == 2:  # Current user is Administrator
            if is_pk14:
                # Administrator with pk=14
                if target_account_type_id == 3:  # Target is Agriculturist
                    can_view_full_details = True
                    can_view_histories = True
                    can_edit_municipality = True  # Can edit agriculturist municipality (excluding pk=14)
                elif target_account_type_id == 2:  # Target is Administrator
                    target_municipality = target_admin_info.municipality_incharge if target_admin_info else None
                    if target_municipality and target_municipality.pk != 14:
                        # Can see all information of administrators not assigned to pk=14
                        can_view_full_details = True
                        can_view_histories = True
                        can_edit_municipality = True  # Can edit municipality (excluding pk=14)
                    else:
                        # Limited access for administrators assigned to pk=14
                        can_view_full_details = False
                        can_view_histories = False
            else:
                # Administrator with municipality not pk=14
                if target_account_type_id == 3:  # Target is Agriculturist in same municipality
                    can_view_full_details = True
                    can_view_histories = True
                    # Can't edit account type and municipality for agriculturists
                elif target_account_type_id == 2:  # Target is Administrator
                    # Can see administrators with same municipality and pk=14 but restricted content
                    can_view_full_details = False  # Can't see personal details, login history, actions
                    can_view_histories = False
        elif user_role_id == 3 and is_own_account:  # Agriculturist viewing own account
            can_view_full_details = True
            can_view_histories = True
            # Agriculturists cannot edit their own account details
        
        # Calculate age
        today = date.today()
        birth_date = target_userinfo.birthdate
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        # Get admin action history (only if allowed to view histories)
        admin_actions = []
        if target_admin_info and can_view_histories:
            try:
                admin_actions = AdminUserManagement.objects.filter(
                    admin_id=target_admin_info
                ).order_by('-action_timestamp')[:20]  # Latest 20 actions
            except Exception as e:
                print(f"Warning: Could not fetch admin actions - database schema issue: {e}")
                admin_actions = []
        
        # Get login history (only if allowed to view histories)
        login_history = []
        if can_view_histories:
            try:
                login_history = UserLoginLog.objects.filter(
                    account_id=target_account
                ).order_by('-login_date')[:20]  # Latest 20 logins
            except Exception as e:
                print(f"Warning: Could not fetch login history: {e}")
                login_history = []
        
        # Get options for editing - filter municipalities to exclude pk=14 for non-superusers
        account_types = AccountType.objects.exclude(account_type='Farmer')
        if is_superuser:
            municipalities = MunicipalityName.objects.all()
        else:
            municipalities = MunicipalityName.objects.exclude(pk=14)
        
        context = {
            **get_admin_context(request),
            'target_account': target_account,
            'target_userinfo': target_userinfo,
            'target_admin_info': target_admin_info,
            'calculated_age': age,
            'is_superuser': is_superuser,
            'is_pk14': is_pk14,
            'user_role_id': user_role_id,
            'target_account_type_id': target_account_type_id,
            'is_own_account': is_own_account,
            'can_view_full_details': can_view_full_details,
            'can_view_histories': can_view_histories,
            'can_edit_account_type': can_edit_account_type,
            'can_edit_municipality': can_edit_municipality,
            'admin_actions': admin_actions,
            'login_history': login_history,
            'account_types': account_types,
            'municipalities': municipalities,
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

# Export functions for CSV and PDF generation
def export_harvest_records_csv(records, filename, format_type='csv', request=None):
    """Export harvest records to CSV or PDF format"""
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date Created', 'Farmer Name', 'Commodity', 'Harvest Date', 
            'Total Weight (kg)', 'Estimated Hectare', 'Location', 'Status', 'Verified By', 'Date Verified'
        ])
        
        for record in records:
            # Get estimated hectare
            estimated_hectare = 0
            if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
                estimated_hectare = record.transaction.farm_land.estimated_area or 0
            
            # Convert weight to kg
            weight_kg = convert_to_kg(record.total_weight, record.unit.unit_abrv)
            
            writer.writerow([
                record.transaction.transaction_date.strftime('%Y-%m-%d %H:%M'),
                f"{record.transaction.account_id.userinfo_id.lastname}, {record.transaction.account_id.userinfo_id.firstname}",
                record.commodity_id.name,
                record.harvest_date.strftime('%Y-%m-%d'),
                f"{weight_kg:.2f}",
                f"{estimated_hectare:.2f}",
                record.transaction.get_location_display(),
                record.record_status.acc_status if record.record_status else 'N/A',
                f"{record.verified_by.userinfo_id.lastname}, {record.verified_by.userinfo_id.firstname}" if record.verified_by else 'Not Verified',
                record.date_verified.strftime('%Y-%m-%d %H:%M') if record.date_verified else 'Not Verified'
            ])
        
        return response
    elif format_type == 'pdf':
        return generate_harvest_records_pdf(records, filename, request)

def export_harvest_records_summary_csv(records, filename, format_type='csv', request=None):
    """Export harvest records summary to CSV or PDF format"""
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        # Group by commodity and municipality for summary
        summary_data = {}
        for record in records:
            commodity = record.commodity_id.name
            location = record.transaction.get_location_display()
            key = f"{commodity} - {location}"
            
            if key not in summary_data:
                summary_data[key] = {
                    'commodity': commodity,
                    'location': location,
                    'total_records': 0,
                    'total_weight': 0,
                    'total_hectare': 0,
                    'verified_count': 0,
                    'pending_count': 0
                }
            
            summary_data[key]['total_records'] += 1
            
            # Convert weight to kg and add estimated hectare
            weight_kg = convert_to_kg(record.total_weight, record.unit.unit_abrv)
            summary_data[key]['total_weight'] += weight_kg
            
            # Add estimated hectare
            if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
                summary_data[key]['total_hectare'] += record.transaction.farm_land.estimated_area or 0
            
            if record.record_status and record.record_status.acc_status == 'Verified':
                summary_data[key]['verified_count'] += 1
            else:
                summary_data[key]['pending_count'] += 1
        
        writer = csv.writer(response)
        writer.writerow([
            'Commodity', 'Location', 'Total Records', 'Total Weight (kg)', 'Total Estimated Hectare',
            'Verified Records', 'Pending Records'
        ])
        
        for data in summary_data.values():
            writer.writerow([
                data['commodity'],
                data['location'],
                data['total_records'],
                f"{data['total_weight']:.2f}",
                f"{data['total_hectare']:.2f}",
                data['verified_count'],
                data['pending_count']
            ])
        
        return response
    elif format_type == 'pdf':
        return generate_harvest_records_summary_pdf(records, filename, request)

def export_plant_records_csv(records, filename, format_type='csv', request=None):
    """Export plant records to CSV or PDF format"""
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date Created', 'Farmer Name', 'Commodity', 'Plant Date', 
            'Min Expected (kg)', 'Max Expected (kg)', 'Estimated Hectare', 'Location', 'Status', 'Verified By', 'Date Verified'
        ])
        
        for record in records:
            # Get estimated hectare
            estimated_hectare = 0
            if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
                estimated_hectare = record.transaction.farm_land.estimated_area or 0
            
            writer.writerow([
                record.transaction.transaction_date.strftime('%Y-%m-%d %H:%M'),
                f"{record.transaction.account_id.userinfo_id.lastname}, {record.transaction.account_id.userinfo_id.firstname}",
                record.commodity_id.name,
                record.plant_date.strftime('%Y-%m-%d'),
                record.min_expected_harvest,
                record.max_expected_harvest,
                f"{estimated_hectare:.2f}",
                record.transaction.get_location_display(),
                record.record_status.acc_status if record.record_status else 'N/A',
                f"{record.verified_by.userinfo_id.lastname}, {record.verified_by.userinfo_id.firstname}" if record.verified_by else 'Not Verified',
                record.date_verified.strftime('%Y-%m-%d %H:%M') if record.date_verified else 'Not Verified'
            ])
        
        return response
    elif format_type == 'pdf':
        return generate_plant_records_pdf(records, filename, request)

def export_plant_records_summary_csv(records, filename, format_type='csv'):
    """Export plant records summary to CSV or PDF format"""
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        # Group by commodity and municipality for summary
        summary_data = {}
        for record in records:
            commodity = record.commodity_id.name
            location = record.transaction.get_location_display()
            key = f"{commodity} - {location}"
            
            if key not in summary_data:
                summary_data[key] = {
                    'commodity': commodity,
                    'location': location,
                    'total_records': 0,
                    'total_expected_min': 0,
                    'total_expected_max': 0,
                    'total_hectare': 0,
                    'verified_count': 0,
                    'pending_count': 0
                }
            
            summary_data[key]['total_records'] += 1
            summary_data[key]['total_expected_min'] += float(record.min_expected_harvest)
            summary_data[key]['total_expected_max'] += float(record.max_expected_harvest)
            
            # Add estimated hectare
            if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
                summary_data[key]['total_hectare'] += record.transaction.farm_land.estimated_area or 0
            
            if record.record_status and record.record_status.acc_status == 'Verified':
                summary_data[key]['verified_count'] += 1
            else:
                summary_data[key]['pending_count'] += 1
        
        writer = csv.writer(response)
        writer.writerow([
            'Commodity', 'Location', 'Total Records', 'Total Min Expected (kg)', 'Total Max Expected (kg)', 'Total Estimated Hectare',
            'Verified Records', 'Pending Records'
        ])
        
        for data in summary_data.values():
            writer.writerow([
                data['commodity'],
                data['location'],
                data['total_records'],
                f"{data['total_expected_min']:.2f}",
                f"{data['total_expected_max']:.2f}",
                f"{data['total_hectare']:.2f}",
                data['verified_count'],
                data['pending_count']
            ])
        
        return response
    elif format_type == 'pdf':
        return generate_plant_records_summary_pdf(records, filename)

def export_accounts_csv(accounts, filename, format_type='csv', request=None):
    """Export accounts to CSV or PDF format"""
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        # Get assigned municipality for record count filtering
        assigned_municipality = None
        if request and request.user.is_authenticated:
            try:
                user_info = UserInformation.objects.get(auth_user=request.user)
                admin_info = AdminInformation.objects.get(userinfo_id=user_info)
                municipality_assigned = admin_info.municipality_incharge
                is_superuser = request.user.is_superuser
                is_pk14 = municipality_assigned.pk == 14
                
                if not is_superuser and not is_pk14:
                    assigned_municipality = municipality_assigned
            except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
                pass
        
        writer = csv.writer(response)
        writer.writerow([
            'Account ID', 'Full Name', 'Email', 'Contact Number', 'Municipality', 'Barangay',
            'Account Type', 'Status', 'Registration Date', 'Verified Date', 'Verified By',
            'Records in Assigned Municipality', 'Farmland Area in Municipality (ha)'
        ])
        
        for account in accounts:
            # Format contact number as string and handle empty values
            contact_number = account.userinfo_id.contact_number
            if contact_number:
                contact_number_str = str(contact_number)
            else:
                contact_number_str = "Not provided"
            
            # Calculate records in assigned municipality
            records_count = 0
            total_farmland_area = 0
            
            if assigned_municipality:
                # Count records in assigned municipality
                records_count = RecordTransaction.objects.filter(
                    account_id=account
                ).filter(
                    Q(farm_land__municipality=assigned_municipality) |
                    Q(manual_municipality=assigned_municipality)
                ).count()
                
                # Calculate total farmland area in assigned municipality
                farmlands = FarmLand.objects.filter(
                    userinfo_id=account.userinfo_id,
                    municipality=assigned_municipality
                )
                total_farmland_area = sum(f.estimated_area or 0 for f in farmlands)
            else:
                # For superusers/administrators, show total records and farmlands
                records_count = RecordTransaction.objects.filter(account_id=account).count()
                farmlands = FarmLand.objects.filter(userinfo_id=account.userinfo_id)
                total_farmland_area = sum(f.estimated_area or 0 for f in farmlands)
                
            writer.writerow([
                account.account_id,
                f"{account.userinfo_id.lastname}, {account.userinfo_id.firstname} {account.userinfo_id.middlename}".strip(),
                account.userinfo_id.user_email,
                contact_number_str,
                account.userinfo_id.municipality_id.municipality,
                account.userinfo_id.barangay_id.barangay,
                account.account_type_id.account_type,
                account.acc_status_id.acc_status,
                account.account_register_date.strftime('%Y-%m-%d %H:%M') if account.account_register_date else 'N/A',
                account.account_verified_date.strftime('%Y-%m-%d %H:%M') if account.account_verified_date else 'Not Verified',
                f"{account.account_verified_by.userinfo_id.lastname}, {account.account_verified_by.userinfo_id.firstname}" if account.account_verified_by else 'Not Verified',
                records_count,
                f"{total_farmland_area:.2f}"
            ])
        
        return response
    elif format_type == 'pdf':
        return generate_accounts_pdf(accounts, filename, request)

def export_accounts_summary_csv(accounts, filename, format_type='csv', request=None):
    """Export accounts summary to CSV or PDF format"""
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        # Group by municipality and status for summary
        summary_data = {}
        for account in accounts:
            municipality = account.userinfo_id.municipality_id.municipality
            status = account.acc_status_id.acc_status
            account_type = account.account_type_id.account_type
            key = f"{municipality} - {account_type}"
            
            if key not in summary_data:
                summary_data[key] = {
                    'municipality': municipality,
                    'account_type': account_type,
                    'total_accounts': 0,
                    'verified_count': 0,
                    'pending_count': 0,
                    'rejected_count': 0,
                    'other_count': 0
                }
            
            summary_data[key]['total_accounts'] += 1
            
            if status == 'Verified':
                summary_data[key]['verified_count'] += 1
            elif status == 'Pending':
                summary_data[key]['pending_count'] += 1
            elif status == 'Rejected':
                summary_data[key]['rejected_count'] += 1
            else:
                summary_data[key]['other_count'] += 1
        
        writer = csv.writer(response)
        writer.writerow([
            'Municipality', 'Account Type', 'Total Accounts', 'Verified', 'Pending', 'Rejected', 'Other'
        ])
        
        for data in summary_data.values():
            writer.writerow([
                data['municipality'],
                data['account_type'],
                data['total_accounts'],
                data['verified_count'],
                data['pending_count'],
                data['rejected_count'],
                data['other_count']
            ])
        
        return response
    elif format_type == 'pdf':
        return generate_accounts_summary_pdf(accounts, filename)

def export_verified_harvest_records_csv(records, filename, format_type='csv'):
    """Export verified harvest records to CSV or PDF format"""
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Record ID', 'Commodity', 'Harvest Date', 'Total Weight (kg)',
            'Municipality', 'Barangay', 'Date Verified', 'Verified By', 'Remarks'
        ])
        
        for record in records:
            writer.writerow([
                record.id,
                record.commodity_id.name,
                record.harvest_date.strftime('%Y-%m-%d'),
                record.total_weight_kg,
                record.municipality.municipality if record.municipality else 'N/A',
                record.barangay.barangay if record.barangay else 'N/A',
                record.date_verified.strftime('%Y-%m-%d %H:%M'),
                f"{record.verified_by.userinfo_id.lastname}, {record.verified_by.userinfo_id.firstname}" if record.verified_by else 'N/A',
                record.remarks or 'No remarks'
            ])
        
        return response
    elif format_type == 'pdf':
        return generate_verified_harvest_records_pdf(records, filename)

def export_verified_harvest_records_summary_csv(records, filename, format_type='csv'):
    """Export verified harvest records summary to CSV or PDF format"""
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        # Group by commodity and municipality for summary
        summary_data = {}
        for record in records:
            commodity = record.commodity_id.name
            municipality = record.municipality.municipality if record.municipality else 'Unknown'
            key = f"{commodity} - {municipality}"
            
            if key not in summary_data:
                summary_data[key] = {
                    'commodity': commodity,
                    'municipality': municipality,
                    'total_records': 0,
                    'total_weight': 0,
                    'avg_weight_per_unit': 0,
                    'weight_count': 0
                }
            
            summary_data[key]['total_records'] += 1
            summary_data[key]['total_weight'] += float(record.total_weight_kg)
            summary_data[key]['avg_weight_per_unit'] += float(record.weight_per_unit_kg)
            summary_data[key]['weight_count'] += 1
        
        writer = csv.writer(response)
        writer.writerow([
            'Commodity', 'Municipality', 'Total Records', 'Total Weight (kg)', 'Average Weight per Unit (kg)'
        ])
        
        for data in summary_data.values():
            avg_weight_per_unit = data['avg_weight_per_unit'] / data['weight_count'] if data['weight_count'] > 0 else 0
            writer.writerow([
                data['commodity'],
                data['municipality'],
                data['total_records'],
                f"{data['total_weight']:.2f}",
                f"{avg_weight_per_unit:.2f}"
            ])
        
        return response
    elif format_type == 'pdf':
        return generate_verified_harvest_records_summary_pdf(records, filename)

# PDF Generation Functions
def generate_harvest_records_pdf(records, filename, request=None):
    """Generate PDF for harvest records"""
    if not PDF_AVAILABLE:
        # Fallback to CSV if ReportLab is not available
        return export_harvest_records_csv(records, filename + '_fallback', 'csv')
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    # Create PDF document
    doc = SimpleDocTemplate(response, pagesize=landscape(letter), 
                          rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=10,
        alignment=1  # Center alignment
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=20,
        alignment=1,
        textColor=colors.grey
    )
    
    # Add title
    title = Paragraph("Harvest Records Report", title_style)
    elements.append(title)
    
    # Add municipality information if available
    if request and request.user.is_authenticated:
        try:
            user_info = UserInformation.objects.get(auth_user=request.user)
            admin_info = AdminInformation.objects.get(userinfo_id=user_info)
            municipality_assigned = admin_info.municipality_incharge
            is_superuser = request.user.is_superuser
            is_pk14 = municipality_assigned.pk == 14
            
            if not is_superuser and not is_pk14:
                subtitle = Paragraph(f"(with {municipality_assigned.municipality} records)", subtitle_style)
                elements.append(subtitle)
        except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
            pass
    
    elements.append(Spacer(1, 12))
    
    # Prepare data for table
    data = [['Date Created', 'Farmer Name', 'Commodity', 'Harvest Date', 
             'Total Weight (kg)', 'Est. Hectare', 'Location', 'Status']]
    
    for record in records:
        # Get estimated hectare
        estimated_hectare = 0
        if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
            estimated_hectare = record.transaction.farm_land.estimated_area or 0
            
        # Convert weight to kg
        weight_kg = convert_to_kg(record.total_weight, record.unit.unit_abrv)
        
        # Format farmer name and location with line breaks if too long
        farmer_name = f"{record.transaction.account_id.userinfo_id.lastname}, {record.transaction.account_id.userinfo_id.firstname}"
        location = record.transaction.get_location_display()
        
        # Use Paragraph for text wrapping in cells
        farmer_name_para = Paragraph(farmer_name, styles['Normal']) if len(farmer_name) > 20 else farmer_name
        location_para = Paragraph(location, styles['Normal']) if len(location) > 15 else location
        
        row = [
            record.transaction.transaction_date.strftime('%Y-%m-%d'),
            farmer_name_para,
            record.commodity_id.name,
            record.harvest_date.strftime('%Y-%m-%d'),
            f"{weight_kg:.2f}",
            f"{estimated_hectare:.2f}",
            location_para,
            record.record_status.acc_status if record.record_status else 'N/A'
        ]
        data.append(row)
    
    # Create table with appropriate column widths
    col_widths = [80, 120, 80, 80, 80, 80, 120, 80]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    return response

def generate_harvest_records_summary_pdf(records, filename, request=None):
    """Generate PDF for harvest records summary"""
    if not PDF_AVAILABLE:
        return export_harvest_records_summary_csv(records, filename + '_fallback', 'csv')
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                fontSize=16, spaceAfter=10, alignment=1)
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=20,
        alignment=1,
        textColor=colors.grey
    )
    
    title = Paragraph("Harvest Records Summary Report", title_style)
    elements.append(title)
    
    # Add municipality information if available
    if request and request.user.is_authenticated:
        try:
            user_info = UserInformation.objects.get(auth_user=request.user)
            admin_info = AdminInformation.objects.get(userinfo_id=user_info)
            municipality_assigned = admin_info.municipality_incharge
            is_superuser = request.user.is_superuser
            is_pk14 = municipality_assigned.pk == 14
            
            if not is_superuser and not is_pk14:
                subtitle = Paragraph(f"(with {municipality_assigned.municipality} records)", subtitle_style)
                elements.append(subtitle)
        except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
            pass
    
    elements.append(Spacer(1, 12))
    
    # Group by commodity and municipality for summary
    summary_data = {}
    for record in records:
        commodity = record.commodity_id.name
        location = record.transaction.get_location_display()
        key = f"{commodity} - {location}"
        
        if key not in summary_data:
            summary_data[key] = {
                'commodity': commodity, 'location': location, 'total_records': 0,
                'total_weight': 0, 'total_hectare': 0, 'verified_count': 0, 'pending_count': 0
            }
        
        summary_data[key]['total_records'] += 1
        
        # Convert weight to kg and add estimated hectare
        weight_kg = convert_to_kg(record.total_weight, record.unit.unit_abrv)
        summary_data[key]['total_weight'] += weight_kg
        
        # Add estimated hectare
        if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
            summary_data[key]['total_hectare'] += record.transaction.farm_land.estimated_area or 0
        
        if record.record_status and record.record_status.acc_status == 'Verified':
            summary_data[key]['verified_count'] += 1
        else:
            summary_data[key]['pending_count'] += 1
    
    data = [['Commodity', 'Location', 'Total Records', 'Total Weight (kg)', 'Total Hectare', 'Verified', 'Pending']]
    for item in summary_data.values():
        data.append([item['commodity'], item['location'][:20], item['total_records'], 
                    f"{item['total_weight']:.2f}", f"{item['total_hectare']:.2f}",
                    item['verified_count'], item['pending_count']])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response

def generate_plant_records_pdf(records, filename, request=None):
    """Generate PDF for plant records"""
    if not PDF_AVAILABLE:
        return export_plant_records_csv(records, filename + '_fallback', 'csv')
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(letter), 
                          rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                fontSize=16, spaceAfter=10, alignment=1)
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=20,
        alignment=1,
        textColor=colors.grey
    )
    
    title = Paragraph("Plant Records Report", title_style)
    elements.append(title)
    
    # Add municipality information if available
    if request and request.user.is_authenticated:
        try:
            user_info = UserInformation.objects.get(auth_user=request.user)
            admin_info = AdminInformation.objects.get(userinfo_id=user_info)
            municipality_assigned = admin_info.municipality_incharge
            is_superuser = request.user.is_superuser
            is_pk14 = municipality_assigned.pk == 14
            
            if not is_superuser and not is_pk14:
                subtitle = Paragraph(f"(with {municipality_assigned.municipality} records)", subtitle_style)
                elements.append(subtitle)
        except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
            pass
    
    elements.append(Spacer(1, 12))
    
    data = [['Date Created', 'Farmer Name', 'Commodity', 'Plant Date', 
             'Min Expected (kg)', 'Max Expected (kg)', 'Est. Hectare', 'Location']]
    
    for record in records:
        # Get estimated hectare
        estimated_hectare = 0
        if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
            estimated_hectare = record.transaction.farm_land.estimated_area or 0
        
        # Format farmer name and location with line breaks if too long
        farmer_name = f"{record.transaction.account_id.userinfo_id.lastname}, {record.transaction.account_id.userinfo_id.firstname}"
        location = record.transaction.get_location_display()
        
        # Use Paragraph for text wrapping in cells
        farmer_name_para = Paragraph(farmer_name, styles['Normal']) if len(farmer_name) > 20 else farmer_name
        location_para = Paragraph(location, styles['Normal']) if len(location) > 15 else location
            
        row = [
            record.transaction.transaction_date.strftime('%Y-%m-%d'),
            farmer_name_para,
            record.commodity_id.name,
            record.plant_date.strftime('%Y-%m-%d'),
            str(record.min_expected_harvest),
            str(record.max_expected_harvest),
            f"{estimated_hectare:.2f}",
            location_para
        ]
        data.append(row)
    
    # Create table with appropriate column widths
    col_widths = [80, 120, 80, 80, 80, 80, 80, 120]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response

def generate_plant_records_summary_pdf(records, filename):
    """Generate PDF for plant records summary"""
    if not PDF_AVAILABLE:
        return export_plant_records_summary_csv(records, filename + '_fallback', 'csv')
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                fontSize=16, spaceAfter=30, alignment=1)
    
    title = Paragraph("Plant Records Summary Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    summary_data = {}
    for record in records:
        commodity = record.commodity_id.name
        location = record.transaction.get_location_display()
        key = f"{commodity} - {location}"
        
        if key not in summary_data:
            summary_data[key] = {
                'commodity': commodity, 'location': location, 'total_records': 0,
                'total_expected_min': 0, 'total_expected_max': 0, 'total_hectare': 0,
                'verified_count': 0, 'pending_count': 0
            }
        
        summary_data[key]['total_records'] += 1
        summary_data[key]['total_expected_min'] += float(record.min_expected_harvest)
        summary_data[key]['total_expected_max'] += float(record.max_expected_harvest)
        
        # Add estimated hectare
        if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
            summary_data[key]['total_hectare'] += record.transaction.farm_land.estimated_area or 0
        
        if record.record_status and record.record_status.acc_status == 'Verified':
            summary_data[key]['verified_count'] += 1
        else:
            summary_data[key]['pending_count'] += 1
    
    data = [['Commodity', 'Location', 'Total Records', 'Total Min Expected  (kg)', 'Total Max Expected  (kg)', 'Total Hectare', 'Verified', 'Pending']]
    for item in summary_data.values():
        data.append([item['commodity'], item['location'][:20], item['total_records'], 
                    f"{item['total_expected_min']:.2f}", f"{item['total_expected_max']:.2f}",
                    f"{item['total_hectare']:.2f}", item['verified_count'], item['pending_count']])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response

def generate_accounts_pdf(accounts, filename, request=None):
    """Generate PDF for accounts"""
    if not PDF_AVAILABLE:
        return export_accounts_csv(accounts, filename + '_fallback', 'csv', request)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(letter), 
                          rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                fontSize=16, spaceAfter=10, alignment=1)
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=20,
        alignment=1,
        textColor=colors.grey
    )
    
    title = Paragraph("Accounts Report", title_style)
    elements.append(title)
    
    # Get assigned municipality for record count filtering
    assigned_municipality = None
    if request and request.user.is_authenticated:
        try:
            user_info = UserInformation.objects.get(auth_user=request.user)
            admin_info = AdminInformation.objects.get(userinfo_id=user_info)
            municipality_assigned = admin_info.municipality_incharge
            is_superuser = request.user.is_superuser
            is_pk14 = municipality_assigned.pk == 14
            
            if not is_superuser and not is_pk14:
                assigned_municipality = municipality_assigned
                subtitle = Paragraph(f"(with {municipality_assigned.municipality} records)", subtitle_style)
                elements.append(subtitle)
        except (UserInformation.DoesNotExist, AdminInformation.DoesNotExist):
            pass
    
    elements.append(Spacer(1, 12))
    
    data = [['ID', 'Full Name', 'Email', 'Contact', 'Municipality', 'Type', 'Status', 'Reg Date', 'Records', 'Farmland (ha)']]
    
    for account in accounts:
        # Format contact number as string and handle empty values
        contact_number = account.userinfo_id.contact_number
        if contact_number:
            contact_number_str = str(contact_number)
        else:
            contact_number_str = "Not provided"
        
        # Calculate records in assigned municipality
        records_count = 0
        total_farmland_area = 0
        
        if assigned_municipality:
            # Count records in assigned municipality
            records_count = RecordTransaction.objects.filter(
                account_id=account
            ).filter(
                Q(farm_land__municipality=assigned_municipality) |
                Q(manual_municipality=assigned_municipality)
            ).count()
            
            # Calculate total farmland area in assigned municipality
            farmlands = FarmLand.objects.filter(
                userinfo_id=account.userinfo_id,
                municipality=assigned_municipality
            )
            total_farmland_area = sum(f.estimated_area or 0 for f in farmlands)
        else:
            # For superusers/administrators, show total records and farmlands
            records_count = RecordTransaction.objects.filter(account_id=account).count()
            farmlands = FarmLand.objects.filter(userinfo_id=account.userinfo_id)
            total_farmland_area = sum(f.estimated_area or 0 for f in farmlands)
        
        # Use Paragraph for text wrapping
        full_name = f"{account.userinfo_id.lastname}, {account.userinfo_id.firstname}"
        full_name_para = Paragraph(full_name, styles['Normal']) if len(full_name) > 20 else full_name
        email_para = Paragraph(account.userinfo_id.user_email, styles['Normal']) if len(account.userinfo_id.user_email) > 20 else account.userinfo_id.user_email
            
        row = [
            account.account_id,
            full_name_para,
            email_para,
            contact_number_str[:16],
            account.userinfo_id.municipality_id.municipality[:15],
            account.account_type_id.account_type,
            account.acc_status_id.acc_status,
            account.account_register_date.strftime('%Y-%m-%d') if account.account_register_date else 'N/A',
            records_count,
            f"{total_farmland_area:.2f}"
        ]
        data.append(row)
    
    # Create table with appropriate column widths
    col_widths = [30, 100, 120, 80, 80, 60, 60, 70, 50, 60]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response

def generate_accounts_summary_pdf(accounts, filename):
    """Generate PDF for accounts summary"""
    if not PDF_AVAILABLE:
        return export_accounts_summary_csv(accounts, filename + '_fallback', 'csv')
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                fontSize=16, spaceAfter=30, alignment=1)
    
    title = Paragraph("Accounts Summary Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    summary_data = {}
    for account in accounts:
        municipality = account.userinfo_id.municipality_id.municipality
        status = account.acc_status_id.acc_status
        account_type = account.account_type_id.account_type
        key = f"{municipality} - {account_type}"
        
        if key not in summary_data:
            summary_data[key] = {
                'municipality': municipality, 'account_type': account_type, 'total_accounts': 0,
                'verified_count': 0, 'pending_count': 0, 'rejected_count': 0, 'other_count': 0
            }
        
        summary_data[key]['total_accounts'] += 1
        
        if status == 'Verified':
            summary_data[key]['verified_count'] += 1
        elif status == 'Pending':
            summary_data[key]['pending_count'] += 1
        elif status == 'Rejected':
            summary_data[key]['rejected_count'] += 1
        else:
            summary_data[key]['other_count'] += 1
    
    data = [['Municipality', 'Account Type', 'Total Accounts', 'Verified', 'Pending', 'Rejected', 'Other']]
    for item in summary_data.values():
        data.append([item['municipality'], item['account_type'], item['total_accounts'], 
                    item['verified_count'], item['pending_count'], item['rejected_count'], item['other_count']])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response

def generate_verified_harvest_records_pdf(records, filename):
    """Generate PDF for verified harvest records"""
    if not PDF_AVAILABLE:
        return export_verified_harvest_records_csv(records, filename + '_fallback', 'csv')
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(letter), 
                          rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                fontSize=16, spaceAfter=30, alignment=1)
    
    title = Paragraph("Verified Harvest Records Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    data = [['Record ID', 'Commodity', 'Harvest Date', 'Total Weight (kg)', 'Municipality', 'Verified By']]
    
    for record in records:
        row = [
            str(record.id),
            record.commodity_id.name,
            record.harvest_date.strftime('%Y-%m-%d'),
            str(record.total_weight_kg),
            record.municipality.municipality if record.municipality else 'N/A',
            f"{record.verified_by.userinfo_id.lastname}, {record.verified_by.userinfo_id.firstname}"[:20] if record.verified_by else 'N/A'
        ]
        data.append(row)
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response

def generate_verified_harvest_records_summary_pdf(records, filename):
    """Generate PDF for verified harvest records summary"""
    if not PDF_AVAILABLE:
        return export_verified_harvest_records_summary_csv(records, filename + '_fallback', 'csv')
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                fontSize=16, spaceAfter=30, alignment=1)
    
    title = Paragraph("Verified Harvest Records Summary Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    summary_data = {}
    for record in records:
        commodity = record.commodity_id.name
        municipality = record.municipality.municipality if record.municipality else 'Unknown'
        key = f"{commodity} - {municipality}"
        
        if key not in summary_data:
            summary_data[key] = {
                'commodity': commodity, 'municipality': municipality, 'total_records': 0,
                'total_weight': 0, 'avg_weight_per_unit': 0, 'weight_count': 0
            }
        
        summary_data[key]['total_records'] += 1
        summary_data[key]['total_weight'] += float(record.total_weight_kg)
        summary_data[key]['avg_weight_per_unit'] += float(record.weight_per_unit_kg)
        summary_data[key]['weight_count'] += 1
    
    data = [['Commodity', 'Municipality', 'Total Records', 'Total Weight (kg)', 'Avg Weight/Unit (kg)']]
    for item in summary_data.values():
        avg_weight_per_unit = item['avg_weight_per_unit'] / item['weight_count'] if item['weight_count'] > 0 else 0
        data.append([item['commodity'], item['municipality'], item['total_records'], 
                    f"{item['total_weight']:.2f}", f"{avg_weight_per_unit:.2f}"])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response
                
#                 return redirect('administrator:accinfo')                
        
#         else:
#             form = EditUserInformation(instance=userinfo)

#         return render(request, 'loggedin/account_edit.html', {'form': form})
#     else :
#         return render(request, 'home.html', {})  