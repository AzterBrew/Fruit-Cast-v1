from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.forms import inlineformset_factory
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.core.mail import send_mail, EmailMessage
from django.utils.crypto import get_random_string
from django.conf import settings
import json, time
from dateutil.relativedelta import relativedelta
#from .forms import CustomUserCreationForm  # make sure this is imported
from django.http import JsonResponse
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
import random
from .models import *
from dashboard.models import *
from .forms import RegistrationForm, EditUserInformation, HarvestRecordCreate, PlantRecordCreate, RecordTransactionCreate, FarmlandRecordCreate
from .utils import get_alternative_recommendations
from django.core.files.storage import default_storage

# Format number with commas and 2 decimal places
def format_number(value):
    """Format a number with commas and 2 decimal places"""
    if value is None:
        return "0.00"
    try:
        # Convert to float first to handle Decimal objects
        num_value = float(value)
        return f"{num_value:,.2f}"
    except (ValueError, TypeError):
        return "0.00"

# @login_required > btw i made this not required so that it doesn't require the usr to login just to view the home page

def schedule_monthly_fruit_recommendations(account, municipality_id):
    """
    Schedule monthly fruit recommendation notifications for a specific municipality.
    Checks for existing notifications to avoid duplicates and handles dynamic scheduling.
    """
    try:
        current_time = timezone.now()
        
        # Determine target month and year for recommendations
        # If it's past the 1st of the current month, target next month
        # If it's before or on the 1st, target current month
        if current_time.day > 1:
            target_month = current_time + relativedelta(seconds=2)
        else:
            target_month = current_time
            
        recommendations = get_alternative_recommendations(
            selected_month=target_month.month,
            selected_year=target_month.year,
            selected_municipality_id=municipality_id
        )
        
        # Get municipality name for the message
        municipality = MunicipalityName.objects.get(pk=municipality_id)
        
        # Check if notification already exists for this target month and municipality
        existing_notification = Notification.objects.filter(
            account=account,
            notification_type="fruit_recommendation",
            scheduled_for__month=target_month.month,
            scheduled_for__year=target_month.year,
            message__icontains=municipality.municipality
        ).first()
        
        if existing_notification:
            print(f"Notification already exists for {municipality.municipality} in {target_month.strftime('%B %Y')} - skipping duplicate")
            return False
        
        # Create notifications for both short-term and long-term recommendations
        all_recommendations = recommendations.get('short_term', []) + recommendations.get('long_term', [])
        
        if all_recommendations:
            # Create a combined message for all recommendations for this municipality
            fruit_names = [rec['commodity_name'] for rec in all_recommendations]
            message = f"🌱 {target_month.strftime('%B')} {target_month.year} Fruit Recommendations for {municipality.municipality}: Consider planting {', '.join(fruit_names[:3])}{'...' if len(fruit_names) > 3 else ''} based on forecasted low supply trends."
            
            # Dynamic scheduling logic:
            # If target is current month and we're past the 1st, schedule immediately
            # Otherwise, schedule for the 1st of the target month at 8 AM
            if target_month.month == current_time.month and target_month.year == current_time.year and current_time.day > 1:
                scheduled_datetime = current_time  # Immediate delivery for late account creation
                print(f"Scheduling immediate notification for {municipality.municipality} (account created mid-month)")
            else:
                scheduled_datetime = target_month.replace(day=1, hour=8, minute=0, second=0, microsecond=0)
                print(f"Scheduling notification for {municipality.municipality} on {scheduled_datetime}")
            
            Notification.objects.create(
                account=account,
                message=message,
                notification_type="fruit_recommendation",
                scheduled_for=scheduled_datetime,
                redirect_url=reverse('base:home'),
            )
            return True
        else:
            print(f"No recommendations available for {municipality.municipality} in {target_month.strftime('%B %Y')}")
            return False
        
    except Exception as e:
        print(f"Error scheduling fruit recommendations for municipality {municipality_id}: {e}")
        return False


def schedule_immediate_fruit_recommendations(account, municipality_id):
    """
    Schedule immediate fruit recommendation notifications for testing purposes
    """
    try:
        # Get recommendations for current month
        current_time = timezone.now()
        recommendations = get_alternative_recommendations(
            selected_month=current_time.month,
            selected_year=current_time.year,
            selected_municipality_id=municipality_id
        )
        
        # Get municipality name for the message
        municipality = MunicipalityName.objects.get(pk=municipality_id)
        
        # Create notifications for both short-term and long-term recommendations
        all_recommendations = recommendations.get('short_term', []) + recommendations.get('long_term', [])
        
        if all_recommendations:
            # Create a combined message for all recommendations for this municipality
            fruit_names = [rec['commodity_name'] for rec in all_recommendations]
            message = f"🌱 Fruit Recommendations for {municipality.municipality}: Consider planting {', '.join(fruit_names)} based on forecasted low supply trends."
            
            # Schedule for immediate delivery (current time)
            scheduled_datetime = current_time
            
            Notification.objects.create(
                account=account,
                message=message,
                notification_type="fruit_recommendation",
                scheduled_for=scheduled_datetime,
                redirect_url=reverse('base:home'),
            )
            print(f"Created immediate fruit recommendation notification for {municipality.municipality}")
            return True
        else:
            print(f"No recommendations available for {municipality.municipality}")
            return False
        
    except Exception as e:
        print(f"Error creating immediate fruit recommendations for municipality {municipality_id}: {e}")
        return False


def home(request):
    print("🔥 DEBUG: Home view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')        
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
            accinfo = AccountsInformation.objects.get(account_id=account_id)
            print(accinfo.account_type_id.account_type_id)
            
            now = timezone.now()
            current_year = now.year

            # Check if user has farmland records and get distinct municipalities
            user_farmlands = FarmLand.objects.filter(userinfo_id=userinfo)
            if user_farmlands.exists():
                print(f"🌾 Found {user_farmlands.count()} farmland records for user")
                # Get distinct municipality IDs from user's farmlands
                distinct_municipality_ids = user_farmlands.values_list('municipality_id', flat=True).distinct()
                print(f"🗺️ User has farmlands in {len(distinct_municipality_ids)} distinct municipalities")
                
                # Schedule fruit recommendation notifications for each municipality
                scheduled_count = 0
                for municipality_id in distinct_municipality_ids:
                    municipality_name = user_farmlands.filter(municipality_id=municipality_id).first().municipality.municipality
                    print(f"📅 Attempting to schedule notifications for {municipality_name} (ID: {municipality_id})")
                    success = schedule_monthly_fruit_recommendations(accinfo, municipality_id)
                    if success:
                        scheduled_count += 1
                
                print(f"✅ Successfully scheduled {scheduled_count}/{len(distinct_municipality_ids)} notifications")
                
                # Show current notification status
                current_notifications = Notification.objects.filter(
                    account=accinfo,
                    notification_type="fruit_recommendation"
                ).count()
                print(f"📢 Total fruit recommendation notifications for this user: {current_notifications}")

            else : 
                print("No farmland records found for user; skipping fruit recommendation scheduling.")
            
            # Define the year range for the dropdown
            year_range = range(current_year - 1, current_year + 3) # Example: past year to next two years
            municipalities = MunicipalityName.objects.exclude(pk=14)
            # --- NEW CODE FOR RECOMMENDATIONS ---
                # Call the utility function to get recommendations
                
                
            context = {
                'user_firstname': userinfo.firstname,
                'user_role_id': accinfo.account_type_id.account_type_id,
                'now': now,
                'months': Month.objects.all(),
                'years': year_range,
                'municipalities': municipalities,   
            }
            return render(request, 'loggedin/home.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')         
    else:        
        return render(request, 'home.html', {})


def get_recommendations_api(request):
    """
    API endpoint to fetch fruit recommendations asynchronously.
    """
    if request.user.is_authenticated:
        month = request.GET.get('month')
        year = request.GET.get('year')
        municipality_id_str = request.GET.get('municipality_id')

        if not (month and year):
            return JsonResponse({"error": "Missing month or year"}, status=400)
        
        try:
            # Handle potential missing municipality_id
            municipality_id = int(municipality_id_str) if municipality_id_str else None
            
            recommendations = get_alternative_recommendations(
                selected_month=month, 
                selected_year=year,
                selected_municipality_id=municipality_id
            )
            return JsonResponse(recommendations)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Unauthorized"}, status=403)


def forecast(request):
    print("🔥 DEBUG: forecast view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
        
            context = {
                'user_firstname' : userinfo.firstname,
            }            
            return render(request, 'forecasting/forecast.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('home')                
            
    else :
        return render(request, 'home.html', {})  
    
    
def monitor(request):
    print("🔥 DEBUG: monitor view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            

            # Example data: commodity_type counts
            # Dataset 1: by commodity type
            commodity_data = {}
            for record in initHarvestRecord.objects.all():
                key = record.commodity_id.name if record.commodity_id else "Unknown"
                commodity_data[key] = commodity_data.get(key, 0) + 1

            # Dataset 2: by location
            location_data = {}
            for record in initHarvestRecord.objects.all():
                if record.transaction:
                    if record.transaction.location_type == 'farm_land' and record.transaction.farm_land:
                        key = record.transaction.farm_land.municipality.municipality
                    elif record.transaction.manual_municipality:
                        key = record.transaction.manual_municipality.municipality
                    else:
                        key = "Unknown Location"
                else:
                    key = "Unknown Location"
                location_data[key] = location_data.get(key, 0) + 1

            context = {
                'commodity_labels': list(commodity_data.keys()),
                'commodity_values': list(commodity_data.values()),
                'location_labels': list(location_data.keys()),
                'location_values': list(location_data.values()),
            }
          
            return render(request, 'monitoring/overall_dashboard.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('home')                
            
    else :
        return render(request, 'home.html', {})  

def dashboard_view(request):
    last_7_days = now().date() - timedelta(days=7)
    recent_records = initHarvestRecord.objects.filter(harvest_date__gte=last_7_days)

    # Example data: commodity_type counts
    data = {}
    for record in recent_records:
        key = record.commodity_id.name if record.commodity_id else "Unknown"
        data[key] = data.get(key, 0) + 1

    context = {
        'labels': list(data.keys()),
        'values': list(data.values()),
    }
    return render(request, 'loggedin/dashboard.html', context)


def newrecord(request):         #opreations ng saving ng records (pero di pa magrecord sa database mismo till masubmit as a whole transaction mismo)
    print("🔥 DEBUG: newrecord view called!")  
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            userinfo = UserInformation.objects.get(pk=userinfo_id)
            accountinfo = AccountsInformation.objects.get(pk=account_id)
            view_to_show = request.GET.get("view", "") #for showing another page within another page ()yung transaction and harves/plant

            form = None
            transaction_form = None
            # transactions = None
            records = []
            selected_transaction = None
            from_transaction = request.GET.get("from") == "transaction"
            
            context = {
                'user_firstname': userinfo.firstname,
                'view_to_show': view_to_show,
                'form': form,
                'transaction_form': transaction_form,
                'pending_records': request.session.get('pending_harvest_records',[]),
                'from_transaction' : from_transaction,
            }

            if view_to_show == "transaction_list":
                record_type = request.GET.get("record_type") or request.session.get("current_record_type", "harvest")
                print("tranrecordlist")
                print({record_type})
                
                if record_type == "plant":
                    pending_records = request.session.get('pending_plant_records', [])
                else:
                    pending_records = request.session.get('pending_harvest_records', [])

                context['record_type'] = record_type
                context['pending_records'] = pending_records
            
            elif view_to_show == "transaction_history":
                transactions = RecordTransaction.objects.filter(account_id=accountinfo).order_by('-transaction_date')
                context['transactions'] = transactions
                
                return render(request, 'loggedin/transaction/transaction.html', context)

            elif view_to_show == "farmland_record":
                transactions = RecordTransaction.objects.filter(account_id=accountinfo).order_by('-transaction_date')
                context['transactions'] = transactions
                
                return render(request, 'loggedin/transaction/transaction.html', context)
            
            elif view_to_show == "transaction_recordhistory":
                transaction_id = request.GET.get("id")
                print("tranrecordhistory")
                
                try:
                    selected_transaction = RecordTransaction.objects.get(pk=transaction_id)
                except RecordTransaction.DoesNotExist:
                    selected_transaction = None
                    
                records = []
                
                if selected_transaction:
                    if selected_transaction.transaction_type.lower()=="harvest":
                        records = initHarvestRecord.objects.filter(transaction_id=selected_transaction)
                    elif selected_transaction.transaction_type.lower()=="plant":
                        records = initPlantRecord.objects.filter(transaction_id=selected_transaction)
                
                context['records'] = records
                context['selected_transaction'] = selected_transaction            
            
            return render(request, 'loggedin/transaction/transaction.html', context)
        else:
            print("⚠️ account_id missing in session!")
            return redirect('home')
    else:
        return render(request, 'home.html', {})

@login_required
def plant_record_view(request):
    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    if not (account_id and userinfo_id):
        return redirect('base:home')
    userinfo = UserInformation.objects.get(pk=userinfo_id)
    accountinfo = AccountsInformation.objects.get(pk=account_id)
    pending_status = AccountStatus.objects.get(acc_status__iexact="Pending")

    if request.method == "POST":
        plant_form = PlantRecordCreate(request.POST, user=request.user)
        transaction_form = RecordTransactionCreate(request.POST, user=request.user)
        
        municipality_id = request.POST.get('manual_municipality')
        if municipality_id:
            transaction_form.fields['manual_barangay'].queryset = BarangayName.objects.filter(municipality_id=municipality_id)
        else:
            transaction_form.fields['manual_barangay'].queryset = BarangayName.objects.none()
        
        if plant_form.is_valid() and transaction_form.is_valid():
            # Create the transaction first
            transaction = transaction_form.save(commit=False)
            transaction.account_id = accountinfo
            transaction.plant_status = pending_status
            transaction.item_status_id = AccountStatus.objects.get(acc_stat_id=3)  # Pending

            # Handle location fields
            if transaction.location_type == "manual":
                transaction.manual_municipality = transaction_form.cleaned_data.get('manual_municipality')
                transaction.manual_barangay = transaction_form.cleaned_data.get('manual_barangay')
                transaction.farm_land = None
            elif transaction.location_type == "farm_land":
                transaction.farm_land = transaction_form.cleaned_data.get('farm_land')
                transaction.manual_municipality = None
                transaction.manual_barangay = None

            transaction.save()

            # Create the plant record linked to the transaction
            plant_record = plant_form.save(commit=False)
            plant_record.transaction = transaction
            plant_record.record_status = pending_status  # Set to pending (pk=3)
            plant_record.save()
            print("may nasave pala")
            
            from dashboard.views import schedule_harvest_notification
            schedule_harvest_notification(plant_record)

            return redirect('base:transaction_recordlist', transaction_id=transaction.transaction_id)
        else:
            print("Transaction form errors:", transaction_form.errors)
            print("walang plant record na nasave")
            print("Plant form errors:", plant_form.errors)
    else:       
        plant_form = PlantRecordCreate(user=request.user)
        transaction_form = RecordTransactionCreate(user=request.user)

    context = {
        'user_firstname': userinfo.firstname,
        'view_to_show': 'plant',
        'form': plant_form,
        'transaction_form': transaction_form,
    }
    return render(request, 'loggedin/transaction/transaction.html', context)


@login_required
def harvest_record_for_plant_view(request, transaction_id):
    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    if not (account_id and userinfo_id):
        return redirect('base:home')
    userinfo = UserInformation.objects.get(pk=userinfo_id)
    transaction = RecordTransaction.objects.get(pk=transaction_id)

# this is the code for checking if yung transaction id is matched with your account id
    if transaction.account_id.pk != account_id:
        return HttpResponseForbidden("Unauthorized access to this transaction.")

    try:
        plant_record = initPlantRecord.objects.get(transaction=transaction)
    except initPlantRecord.DoesNotExist:
        plant_record = None

    try:
        harvest_record = initHarvestRecord.objects.get(transaction=transaction)
    except initHarvestRecord.DoesNotExist:
        harvest_record = None
    # Pre-fill initial data from plant record
    pending_status = AccountStatus.objects.get(acc_status__iexact="Pending")
    
    initial = {}
    if plant_record:
        initial['commodity_id'] = plant_record.commodity_id
        initial['commodity_custom'] = plant_record.commodity_custom

    if request.method == "POST":
        harvest_form = HarvestRecordCreate(request.POST, user=request.user)
        if harvest_form.is_valid():
            harvest_record = harvest_form.save(commit=False)
            harvest_record.transaction = transaction
            transaction.harvest_status = pending_status            
            harvest_record.save()
            return redirect('base:transaction_recordlist', transaction_id=transaction.transaction_id)
    else:
        harvest_form = HarvestRecordCreate(initial=initial, user=request.user)

    context = {
        'user_firstname': userinfo.firstname,
        'view_to_show': 'harvest',
        'form': harvest_form,
        'transaction_form': None,  # Not needed here
        'transaction': transaction,
        'plant_record': plant_record,
        'harvest_record': harvest_record,
        'from_transaction': True,  # So you can customize the template if needed
    }
    return render(request, 'loggedin/transaction/transaction.html', context)


@login_required
def solo_harvest_record_view(request):
    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    if not (account_id and userinfo_id):
        return redirect('base:home')
    userinfo = UserInformation.objects.get(pk=userinfo_id)
    accountinfo = AccountsInformation.objects.get(pk=account_id)
    pending_status = AccountStatus.objects.get(acc_status__iexact="Pending")

    if request.method == "POST":
        harvest_form = HarvestRecordCreate(request.POST, user=request.user)
        transaction_form = RecordTransactionCreate(request.POST, user=request.user)
        manual_municipality_id = request.POST.get('manual_municipality')
        if manual_municipality_id:
            transaction_form.fields['manual_barangay'].queryset = BarangayName.objects.filter(municipality_id=manual_municipality_id)
        else:
            transaction_form.fields['manual_barangay'].queryset = BarangayName.objects.none()

        if harvest_form.is_valid() and transaction_form.is_valid():
            try:
                transaction = transaction_form.save(commit=False)
                transaction.account_id = accountinfo
                if transaction.location_type == "manual":
                    transaction.manual_municipality = transaction_form.cleaned_data.get('manual_municipality')
                    transaction.manual_barangay = transaction_form.cleaned_data.get('manual_barangay')
                elif transaction.location_type == "farm_land":
                    transaction.farm_land = transaction_form.cleaned_data.get('farm_land')
                transaction.save()
                harvest_record = harvest_form.save(commit=False)
                harvest_record.transaction = transaction
                harvest_record.record_status = pending_status
                harvest_record.save()
                print("✅ Solo harvest record saved successfully")
                return redirect('base:transaction_recordlist', transaction_id=transaction.transaction_id)
            except Exception as e:
                print(f"❌ Error saving solo harvest record: {e}")
                messages.error(request, f"Error saving record: {str(e)}")
        else:
            print("❌ Form validation failed")
            print("Harvest form errors:", harvest_form.errors)
            print("Transaction form errors:", transaction_form.errors)
        # If form is invalid, fall through to re-render with errors
    else:
        print("📝 Displaying solo harvest record form")
        harvest_form = HarvestRecordCreate(user=request.user)
        transaction_form = RecordTransactionCreate(user=request.user)

    context = {
        'user_firstname': userinfo.firstname,
        'view_to_show': 'harvest',
        'form': harvest_form,
        'transaction_form': transaction_form,
    }
    return render(request, 'loggedin/transaction/transaction.html', context)


@login_required
def transaction_recordlist(request, transaction_id):
    transaction = RecordTransaction.objects.get(pk=transaction_id)
    session_account_id = request.session.get('account_id')
    if session_account_id != transaction.account_id.pk:
        return HttpResponseForbidden("Unauthorized access to this transaction.")
    
    plant_record = None
    harvest_records = []

    try:
        plant_record = initPlantRecord.objects.get(transaction=transaction)
    except initPlantRecord.DoesNotExist:
        pass

    # Get all harvest records for this transaction
    harvest_records = initHarvestRecord.objects.filter(transaction=transaction).order_by('-harvest_date')
    
    plant_notification = None
    if plant_record:
        plant_notification = Notification.objects.filter(
            linked_plant_record=plant_record,
            is_read=True
        ).order_by('-created_at').first()

    context = {
        'transaction': transaction,
        'plant_record': plant_record,
        'harvest_record': harvest_records,  # Changed to support multiple records
        'view_to_show': 'recordlist',  # So transaction.html knows what to include
        'user_firstname': transaction.account_id.userinfo_id.firstname,
        'plant_notification': plant_notification,
        'format_number': format_number  # Add the formatting function to context
    }
    return render(request, 'loggedin/transaction/transaction.html', context)

@login_required
def farmland_record_view(request):
    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    if not (account_id and userinfo_id):
        return redirect('base:home')
    userinfo = UserInformation.objects.get(pk=userinfo_id)

    if request.method == "POST":
        form = FarmlandRecordCreate(request.POST)
        municipality_id = request.POST.get('municipality')
        if municipality_id:
            form.fields['barangay'].queryset = BarangayName.objects.filter(municipality_id=municipality_id)
        else:
            form.fields['barangay'].queryset = BarangayName.objects.none()

        if form.is_valid():
            farmland = form.save(commit=False)
            farmland.userinfo_id = userinfo
            farmland.save()
            return redirect('base:farmland_owned')  # or wherever you want to redirect after save
    else:
        form = FarmlandRecordCreate()
        form.fields['barangay'].queryset = BarangayName.objects.none()

    # Calculate total farmlands for the current user
    total_farmlands = FarmLand.objects.filter(userinfo_id=userinfo).count()

    context = {
        'form': form,
        'user_firstname': userinfo.firstname,
        'view_to_show': 'farmland_record',
        'total_farmlands': total_farmlands,
    }
    return render(request, 'loggedin/transaction/transaction.html', context)


@login_required
def farmland_record_edit_view(request, farminfo_id):
    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    if not (account_id and userinfo_id):
        return redirect('base:home')
    userinfo = UserInformation.objects.get(pk=userinfo_id)
    farmland = FarmLand.objects.get(pk=farminfo_id, userinfo_id=userinfo)

    if request.method == "POST":
        form = FarmlandRecordCreate(request.POST, instance=farmland)
        municipality_id = request.POST.get('municipality')
        if municipality_id:
            form.fields['barangay'].queryset = BarangayName.objects.filter(municipality_id=municipality_id)
        else:
            form.fields['barangay'].queryset = BarangayName.objects.none()

        if form.is_valid():
            form.save()
            return redirect('base:farmland_owned')
    else:
        form = FarmlandRecordCreate(instance=farmland)
        # Set barangay queryset based on current municipality
        if farmland.municipality:
            form.fields['barangay'].queryset = BarangayName.objects.filter(municipality_id=farmland.municipality.pk)
        else:
            form.fields['barangay'].queryset = BarangayName.objects.none()

    context = {
        'form': form,
        'user_firstname': userinfo.firstname,
        'view_to_show': 'farmland_record',
        'edit_mode': True,
        'farmland': farmland,
    }
    return render(request, 'loggedin/transaction/transaction.html', context)


@login_required
def transaction_history(request):
    account_id = request.session.get('account_id')
    if not account_id:
        return redirect('base:home')

    accountinfo = AccountsInformation.objects.get(pk=account_id)
    transactions = RecordTransaction.objects.filter(account_id=accountinfo).order_by('-transaction_date')

    context = {
        'transactions': transactions,
        'user_firstname': accountinfo.userinfo_id.firstname,
        'view_to_show': 'transaction_history',  # So transaction.html knows what to include
    }
    return render(request, 'loggedin/transaction/transaction.html', context)

@login_required
def account_panel_view(request):
    userinfo_id = request.session.get('userinfo_id')
    
    if not userinfo_id:
        return redirect('base:home')
        
    try:
        # Use select_related to optimize database queries
        userinfo = UserInformation.objects.select_related(
            'barangay_id', 'municipality_id'
        ).get(pk=userinfo_id)
        
        context = {
            'user_firstname': userinfo.firstname,
            'user_middlename': userinfo.middlename,
            'user_lastname': userinfo.lastname,
            'user_nameext': userinfo.nameextension,
            'user_sex': userinfo.sex,
            'user_dob': userinfo.birthdate,
            'user_emperson': userinfo.emergency_contact_person or 'Not Specified',
            'user_emcontact': userinfo.emergency_contact_number or 'Not Specified',
            'user_address_details': userinfo.address_details,
            'user_barangay': userinfo.barangay_id.barangay,
            'user_municipality': userinfo.municipality_id.municipality,
            'user_contactno': userinfo.contact_number,
            'user_email': userinfo.user_email,
            'user_religion': userinfo.religion,
            'user_civil_status': userinfo.civil_status,
            'user_rsbsa_ref_number': userinfo.rsbsa_ref_number or 'Not Provided',
            'view_to_show': 'info',
        }            
        return render(request, 'loggedin/account_panel.html', context)
        
    except UserInformation.DoesNotExist:
        return redirect('base:home') 

@login_required
def account_edit_view(request):
    userinfo_id = request.session.get('userinfo_id')
    
    if not userinfo_id:
        return redirect('base:home')
        
    try:
        # Use select_related to optimize database queries
        userinfo = UserInformation.objects.select_related(
            'barangay_id', 'municipality_id'
        ).get(pk=userinfo_id)
        
        if request.method == "POST":
            form = EditUserInformation(request.POST, instance=userinfo)
            if form.is_valid():
                updated_info = form.save(commit=False)
                # Update the associated auth user email if it changed
                if updated_info.user_email != request.user.email:
                    request.user.email = updated_info.user_email
                    request.user.save()
                
                updated_info.save()
                messages.success(request, 'Your account information has been updated successfully!')
                return redirect('base:account_info_panel')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = EditUserInformation(instance=userinfo)

        context = {
            'form': form,
            'user_firstname': userinfo.firstname,
            'userinfo': userinfo, 
            'view_to_show': 'edit',
        }
        return render(request, 'loggedin/account_panel.html', context)
        
    except UserInformation.DoesNotExist:
        messages.error(request, 'User information not found.')
        return redirect('base:home') 


@login_required
def farmland_owned_view(request):
    userinfo_id = request.session.get('userinfo_id')
    if not userinfo_id:
        return redirect('base:home')
    
    try:
        userinfo = UserInformation.objects.get(pk=userinfo_id)
        farmlands = FarmLand.objects.filter(userinfo_id=userinfo).select_related('municipality', 'barangay')

        # Calculate total area and unique municipalities
        total_area = sum(farm.estimated_area or 0 for farm in farmlands)
        unique_municipalities = set(farm.municipality.municipality for farm in farmlands)

        # Add transaction count for each farmland
        farmlands_with_stats = []
        for farmland in farmlands:
            # Count total transactions (harvest + plant records) for this farmland
            # Use the correct relationship: transaction__farm_land
            harvest_count = initHarvestRecord.objects.filter(transaction__farm_land=farmland).count()
            plant_count = initPlantRecord.objects.filter(transaction__farm_land=farmland).count()
            total_transactions = harvest_count + plant_count
            
            farmlands_with_stats.append({
                'farmland': farmland,
                'harvest_records': harvest_count,
                'plant_records': plant_count,
                'total_transactions': total_transactions,
            })

        context = {
            'farmlands': farmlands,
            'farmlands_with_stats': farmlands_with_stats,
            'total_area': total_area if total_area > 0 else None,
            'unique_municipalities': unique_municipalities,
            'user_firstname': userinfo.firstname,
            'view_to_show': 'farmland_owned',
        }
        return render(request, 'loggedin/account_panel.html', context)
        
    except UserInformation.DoesNotExist:
        return redirect('base:home')


UNIT_CONVERSION_TO_KG = {
    "kg": 1,
    "g": 0.001,
    "ton": 1000,
    "lbs": 0.453592,
}

def convert_to_kg(weight, unit):
    return float(weight) * UNIT_CONVERSION_TO_KG.get(unit, 1)



@require_POST
def finalize_transaction(request):
    print(f"Pending records: {request.session.get('pending_harvest_records', [])}")
    
    record_type = request.POST.get('record_type', 'harvest')  # Default to harvest if not provided
    
    if record_type not in ['harvest', 'plant']:
        return redirect('base:transaction_recordlist')  # Fallback

    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    
    if not (account_id and userinfo_id):
        return redirect('base:home')
        
    accountinfo = AccountsInformation.objects.get(pk=account_id)
    userinfo = UserInformation.objects.get(pk=userinfo_id)

    session_key = f'pending_{record_type}_records'
    records = request.session.get(session_key, [])

    if not records:
        print("No records found in session")
        return redirect('base:transaction_recordlist')

    transaction = RecordTransaction.objects.create(
        account_id=accountinfo,
        transaction_type=record_type.capitalize(),
        item_status_id=AccountStatus.objects.get(acc_status_id=3)
    )

    for data in records:
        if record_type == 'harvest':
            
            initHarvestRecord.objects.create(
                transaction=transaction,
                harvest_date=data['harvest_date'],
                commodity_id=data['commodity_id'],
                commodity_custom=data.get('commodity_custom', ''),
                total_weight=data['total_weight'],
                unit=data['unit'],
                weight_per_unit=data['weight_per_unit'],
                remarks=data.get('remarks', '')
            )
            #  this is for verified harvests
        # if record_type == 'harvest':
        #     total_weight_kg = convert_to_kg(data['total_weight'], data['unit'])
            
        #     HarvestRecord.objects.create(
        #         transaction_id=transaction,
        #         harvest_date=data['harvest_date'],
        #         commodity_type=data['commodity_type'],
        #         commodity_spec=data['commodity_spec'],
        #         total_weight=total_weight_kg,
        #         unit='kg',
        #         weight_per_unit=data['weight_per_unit'],
        #         harvest_location=data['harvest_location'],
        #         remarks=data.get('remarks', '')
        #     )
        
        elif record_type == 'plant':
            initPlantRecord.objects.create(
                transaction_id=transaction,
                plant_date=data['plant_date'],
                commodity_type=data['commodity_type'],
                commodity_spec=data['commodity_spec'],
                expected_harvest_date=data['expected_harvest_date'],
                plant_municipality=data['plant_municipality'],
                min_expected_harvest=data['min_expected_harvest'],
                max_expected_harvest=data['max_expected_harvest'],
                land_area=data['land_area'],
                remarks=data.get('remarks', '')
            )

    print("Transaction finalized, records saved")

    del request.session[session_key]
    return redirect('base:newrecord')



@require_POST
def remove_pending_record(request, index):
    if not request.user.is_authenticated:
        return redirect('base:home')

    record_type = request.POST.get("record_type", "harvest")  # fallback
    session_key = f'pending_{record_type}_records'

    pending_records = request.session.get(session_key, [])
    if 0 <= index < len(pending_records):
        del pending_records[index]
        request.session[session_key] = pending_records
        request.session.modified = True

    return redirect('base:newrecord')



def edit_pending_record(request, index):
    if not request.user.is_authenticated:
        return redirect('base:home')

    # 👉 Determine whether it's a plant or harvest record
    record_type = request.GET.get("record_type", "harvest")  # default to harvest
    print("edit_pending1")

    if record_type == "plant":
        session_key = 'pending_plant_records'
        form_class = PlantRecordCreate
        view_to_show = 'plant'
    else:
        session_key = 'pending_harvest_records'
        form_class = HarvestRecordCreate
        view_to_show = 'harvest'

    # 👉 Access the correct pending records list
    pending_records = request.session.get(session_key, [])

    if index < 0 or index >= len(pending_records):
        return redirect(f"{reverse('base:newrecord')}?view=transaction_list")

    record_data = pending_records[index]
    form = form_class(initial=record_data)

    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            updated_data = form.cleaned_data.copy()
            for key, value in updated_data.items():
                if isinstance(value, date):
                    updated_data[key] = value.isoformat()
                if isinstance(value, Decimal):
                    updated_data[key] = float(value)
            pending_records[index] = updated_data
            request.session[session_key] = pending_records
            request.session.modified = True
            return redirect(f"{reverse('base:newrecord')}?view=transaction_list")

    from_transactionedit = request.GET.get("from") == "transactionedit"
    print("edit_pending2")

    context = {
        'form': form,
        'view_to_show': view_to_show,
        'pending_records': pending_records,
        'from_transactionedit': from_transactionedit,
    }
    print("edit_pending3")

    return render(request, 'loggedin/transaction/transaction.html', context)



# def transaction_history(request):
#     if not request.user.is_authenticated:
#         return redirect('base:home')

#     try:
#         # print("account is testing rn:", userinfo_id)        
#         userinfo_id = request.session.get('userinfo_id')
#         accountinfo = AccountsInformation.objects.get(userinfo_id=userinfo_id)
#     except AccountsInformation.DoesNotExist:
#         print("❌ AccountInfo not found for userinfo_id:", userinfo_id)
#         return render(request, 'loggedin/transaction/transaction_history.html', {
#             'transactions': [],
#             'user_firstname': 'Unknown',
#         })

#     transactions = RecordTransaction.objects.filter(account_id=accountinfo).order_by('-transaction_date')

    print(f"✅ Found {transactions.count()} transactions for account {accountinfo.account_id}")

    return render(request, 'loggedin/transaction/transaction_history.html', {
        'transactions': transactions,
        'user_firstname': accountinfo.userinfo_id.firstname,
    })

def transaction_recordhistory(request, transaction_id):
    if not request.user.is_authenticated:
        return redirect('base:home')

    try:
        transaction = RecordTransaction.objects.get(transaction_id=transaction_id)
    except RecordTransaction.DoesNotExist:
        return HttpResponse("Transaction not found", status=404)

    # Make sure this is the user’s transaction
    session_account_id = request.session.get('account_id')
    if session_account_id != transaction.account_id.pk:
        return HttpResponseForbidden("Unauthorized access to this transaction.")

    # Get the related records based on transaction type
    if transaction.transaction_type.lower() == "harvest":
        records = initHarvestRecord.objects.filter(transaction_id=transaction)
    elif transaction.transaction_type.lower() == "plant":
        records = initPlantRecord.objects.filter(transaction_id=transaction)
    else:
        records = []

    return render(request, 'loggedin/transaction/transaction_recordhistory.html', {
        'transaction': transaction,
        'records': records,
    })






# def plantrecord(request):
#     print("🔥 DEBUG: newrecord view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
            
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
        
#             context = {
#                 'user_firstname' : userinfo.firstname,
#             }            
#             return render(request, 'loggedin/transaction/plant_record.html', context)
        
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('home')   
#     else :
#         return render(request, 'home.html', {}) 


# def get_barangays(request):
#     municipality_id = request.GET.get('municipality_id')
#     barangays = BarangayName.objects.filter(municipality_id=municipality_id).values('id', 'barangay_name')
#     return JsonResponse(list(barangays), safe=False)


def about(request):
    print("🔥 DEBUG: about view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        return render(request, 'loggedin/about.html', {})
    else :
        return render(request, 'about.html', {})  


# @login_required
# def editacc(request):
    # userinfo_id = request.session.get('userinfo_id')
    
    # if not userinfo_id:
    #     return redirect('base:home')
        
    # try:
    #     # Use select_related to optimize database queries
    #     userinfo = UserInformation.objects.select_related(
    #         'barangay_id', 'municipality_id'
    #     ).get(pk=userinfo_id)
        
    #     if request.method == "POST":
    #         form = EditUserInformation(request.POST, instance=userinfo)
    #         if form.is_valid():
    #             updated_info = form.save(commit=False)
    #             # Update the associated auth user email if it changed
    #             if updated_info.user_email != request.user.email:
    #                 request.user.email = updated_info.user_email
    #                 request.user.save()
                
    #             updated_info.save()
    #             messages.success(request, 'Your account information has been updated successfully!')
    #             return redirect('base:accinfo')
    #         else:
    #             messages.error(request, 'Please correct the errors below.')
    #     else:
    #         form = EditUserInformation(instance=userinfo)

    #     context = {
    #         'form': form,
    #         'user_firstname': userinfo.firstname,
    #         'userinfo': userinfo,  # Add full userinfo for reference
    #     }
    #     return render(request, 'loggedin/account_edit.html', context)
        
    # except UserInformation.DoesNotExist:
    #     messages.error(request, 'User information not found.')
    #     return redirect('base:home')  


# def accinfo(request):
#     if request.user.is_authenticated: 
#         userinfo_id = request.session.get('userinfo_id')
        
#         if not userinfo_id:
#             return redirect('base:home')
            
#         try:
#             # Use select_related to optimize database queries
#             userinfo = UserInformation.objects.select_related(
#                 'barangay_id', 'municipality_id'
#             ).get(pk=userinfo_id)
            
#             context = {
#                 'user_firstname': userinfo.firstname,
#                 'user_middlename': userinfo.middlename,
#                 'user_lastname': userinfo.lastname,
#                 'user_nameext': userinfo.nameextension,
#                 'user_sex': userinfo.sex,
#                 'user_dob': userinfo.birthdate,
#                 'user_emperson': userinfo.emergency_contact_person or 'Not Specified',
#                 'user_emcontact': userinfo.emergency_contact_number or 'Not Specified',
#                 'user_address_details': userinfo.address_details,
#                 'user_barangay': userinfo.barangay_id.barangay,
#                 'user_municipality': userinfo.municipality_id.municipality,
#                 'user_contactno': userinfo.contact_number,
#                 'user_email': userinfo.user_email,
#                 'user_religion': userinfo.religion,
#                 'user_civil_status': userinfo.civil_status,
#                 'user_rsbsa_ref_number': userinfo.rsbsa_ref_number or 'Not Provided',
#             }            
#             return render(request, 'loggedin/account_info.html', context)
            
#         except UserInformation.DoesNotExist:
#             return redirect('base:home')
        
#     else:
#         return render(request, 'home.html', {})   
    

def login_success(request):
    print("🔥 Login successful! Redirecting...")  # Debugging log
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        try:
            userinfo = request.user.userinformation
            account_info = AccountsInformation.objects.get(userinfo_id=userinfo)
            print(f"Account Type ID: {account_info.account_type_id.pk}")  # Debugging log
            if account_info.account_type_id.pk == 2 or account_info.account_type_id.pk == 3:
                return redirect('administrator:admin_dashboard')
            else:
                return redirect('base:home') 
        except Exception as e:
            print("Login redirect error:", e)
            return redirect('base:home')
    else:
        return redirect('base:home')

def get_barangays(request, municipality_id):
    # Debug: Special logging for Orani (municipality_id=9)
    if municipality_id == 9:
        print("\n" + "🏘️"*30)
        print("🔍 BARANGAY FETCH DEBUG - ORANI (pk=9)")
        print("🏘️"*30)
    
    try:
        # Get municipality info
        municipality = MunicipalityName.objects.get(pk=municipality_id)
        print(f"🏘️ Municipality: {municipality.municipality} (ID: {municipality_id})")
        
        # Get barangays
        barangays = BarangayName.objects.filter(municipality_id=municipality_id).values('barangay_id', 'barangay')
        barangay_list = [{'id': b['barangay_id'], 'barangay': b['barangay']} for b in barangays]
        
        print(f"🏠 Found {len(barangay_list)} barangays for {municipality.municipality}:")
        for barangay in barangay_list:
            print(f"   🔸 {barangay['barangay']} (ID: {barangay['id']})")
            
        if municipality_id == 9:
            print("🏘️"*30)
            
        return JsonResponse(barangay_list, safe=False)
        
    except MunicipalityName.DoesNotExist:
        print(f"❌ Municipality with ID {municipality_id} does not exist!")
        return JsonResponse([], safe=False)
    except Exception as e:
        print(f"❌ Error fetching barangays for municipality {municipality_id}: {str(e)}")
        return JsonResponse([], safe=False)

def register_email(request):
    email_error = None
    password_error = None
    if request.method == "GET":
        # User is starting over, clear any previous registration session data
        for key in ['verification_code', 'verification_email', 'verification_password', 'verification_code_time', 'email_verified']:
            if key in request.session:
                del request.session[key]
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        
        # Check if email already exists (excluding removed accounts pk=7)
        if AuthUser.objects.filter(email=email).exists():
            # Check if this email belongs to a removed account (pk=7)
            try:
                existing_user = AuthUser.objects.get(email=email)
                user_info = UserInformation.objects.get(auth_user=existing_user)
                account_info = AccountsInformation.objects.get(userinfo_id=user_info)
                
                # If account is removed (pk=7), allow registration with this email
                if account_info.acc_status_id.acc_stat_id != 7:
                    return render(request, "registration/register_email.html", {"email_error": "Email already registered."})
                # If it's a removed account, we allow the registration to proceed
            except (UserInformation.DoesNotExist, AccountsInformation.DoesNotExist):
                # If user exists but no account info, treat as existing registration
                return render(request, "registration/register_email.html", {"email_error": "Email already registered."})
        # Generate verification code
        
        if password != confirm_password:
            password_error = "Passwords do not match."
        else:
            # Save email and password to session, send verification code, etc.
            request.session["reg_email"] = email
            request.session["reg_password"] = password
            verification_code = str(random.randint(100000, 999999))
            request.session["reg_code"] = verification_code
            request.session['verification_code_time'] = int(time.time())  # Store timestamp
            # Send email
            subject = "Confirm Your Fruit Cast Account Registration"
            
            # HTML message
            html_message = """
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="color: #416e3f; padding: 20px; text-align: center; border-radius: 6px;">
                    <a href="https://fruitcast-spro7.ondigitalocean.app/" style="text-decoration: none; color: #416e3f;">
                        <img src="https://raw.githubusercontent.com/AzterBrew/fruitcast-logo/refs/heads/main/3.png" style="max-height: 100px;">
                        <h1 style="margin: 0; font-size: 24px; font-weight: 700">FRUIT CAST REGISTRATION</h1>
                    </a>
                </div>
                <div style="padding: 30px; background: white;">
                    <div style="background: #fffadc;border-left: 4px solid #416e3f;padding: 20px;margin-bottom: 25px;">
                        <h2 style="margin: 0 0 10px;color: #104e0d;font-size: 20px;">⚠️ Action Required</h2>
                        <p style="margin: 0; color: #104e0d;">Your Fruit Cast account needs verification to continue</p>
                    </div>
                    <p style="font-size: 16px; color: #333; margin-bottom: 20px;">Hello Farmer,</p>
                    <p style="font-size: 15px; color: #555; line-height: 1.6;">
                        We've detected a new account registration from your email address. To ensure security and activate your access to our farming intelligence platform, please verify your identity using the code below.
                    </p>
                    <div style="background: #f4f4f4; border: 1px solid #ddd; border-radius: 6px; padding: 25px; text-align: center; margin: 25px 0;">
                        <div style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 10px;">Verification Code</div>
                        <div style="font-family: Courier, monospace; font-size: 24px; font-weight: bold; color: #2c3e50;">
                            {verification_code}
                        </div>
                        <div style="color: #999; font-size: 11px; margin-top: 10px;">Expires: 10 minutes from now</div>
                    </div>
                    <div style="background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #2d5a27;">
                            <strong>🎯 Next Steps:</strong> Enter this code on the verification page to continue your registration.
                        </p>
                    </div>
                    <div style="border-top: 1px solid #eee; padding-top: 20px; margin-top: 30px;">
                        <p style="font-size: 12px; color: #888; text-align: center;">
                            If you didn't register for Fruit Cast, please disregard this notification.
                        </p>
                    </div>
                </div>
                <div style="background: #f8f8f8; padding: 15px; text-align: center;">
                    <p style="margin: 0; color: #666; font-size: 13px;">
                        🌱 &copy; 2025 Fruit Cast. All rights reserved.
                    </p>
                </div>
            </div>
            """.format(verification_code=verification_code)
            
            # Use EmailMessage for HTML email
            try:
                email_msg = EmailMessage(
                    subject=subject,
                    body=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,  # Use settings instead of hardcoded email
                    to=[email],
                )
                email_msg.content_subtype = "html"  # Set the content type to HTML
                email_msg.send()
                
                return redirect("base:register_verify_code")
                
            except Exception as e:
                print(f"Email sending error: {e}")  # For debugging
                return render(request, "registration/register_email.html", {
                    "email_error": "Failed to send verification email. Please try again later.",
                    "password_error": password_error,
                })
        
        # MODIFY THIS EMAIL PAGKA OKS NA
    return render(request, "registration/register_email.html", {"email_error": email_error,"password_error": password_error,})


def register_verify_code(request):
    if not request.session.get("reg_email") or not request.session.get("reg_code"):
        # User hasn't started registration properly
        return redirect("base:register_email")
    code_error = None
    if request.method == "POST":
        input_code = request.POST.get("code")
        session_code = request.session.get("reg_code")
        if input_code == session_code:
            request.session["reg_verified"] = True
            return redirect("base:register_step1")
        else:
            code_error = "Invalid verification code. Please check your email and try again."
        
        code_time = request.session.get('verification_code_time')
        if not code_time or (int(time.time()) - code_time > 600):  # 600 seconds = 10 minutes
            code_error = "Verification code has expired. Please request a new one."
            # Optionally clear session here
            return render(request, 'registration/register_verify.html', {'code_error': code_error})
    return render(request, "registration/register_verify.html", {"code_error": code_error})

    
def register_step1(request):
    if request.user.is_authenticated: 
        return redirect('base:home')
    reg_email = request.session.get('reg_email')
    reg_password = request.session.get('reg_password') 
    
    if not reg_email:
        return redirect('base:register_email')

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        
        # Debug: Print form data
        print("\n" + "="*50)
        print("🔍 REGISTRATION DEBUG - FORM SUBMISSION")
        print("="*50)
        print(f"📧 Registration Email: {reg_email}")
        print(f"📝 Form Data: {dict(request.POST)}")
        print(f"🏘️ Municipality Selected: {request.POST.get('municipality_id')} (should be 9 for Orani)")
        print(f"🏠 Barangay Selected: {request.POST.get('barangay_id')}")
        print(f"✅ Form Valid: {form.is_valid()}")
        
        if not form.is_valid():
            print("❌ FORM VALIDATION ERRORS:")
            for field, errors in form.errors.items():
                print(f"   🔸 {field}: {errors}")
            print("🔍 Non-field errors:", form.non_field_errors())
        
        if form.is_valid():
            print("✅ Form validation passed, proceeding with database operations...")
            try:
                with transaction.atomic():
                    print("🔄 Starting database transaction...")
                    
                    # Create AuthUser
                    print(f"👤 Creating AuthUser with email: {reg_email}")
                    auth_user = AuthUser.objects.create_user(email=reg_email, password=reg_password)
                    print(f"✅ AuthUser created successfully with ID: {auth_user.id}")
                    
                    # Prepare UserInformation
                    print("📋 Preparing UserInformation...")
                    user_info = form.save(commit=False)
                    user_info.auth_user = auth_user
                    user_info.user_email = reg_email  # Set email from session
                    
                    # Debug municipality and barangay info
                    print(f"🏘️ Municipality ID: {user_info.municipality_id} (Type: {type(user_info.municipality_id)})")
                    print(f"🏠 Barangay ID: {user_info.barangay_id} (Type: {type(user_info.barangay_id)})")
                    
                    if user_info.municipality_id:
                        print(f"🏘️ Municipality Name: {user_info.municipality_id.municipality}")
                    if user_info.barangay_id:
                        print(f"🏠 Barangay Name: {user_info.barangay_id.barangay}")
                    
                    print("💾 Saving UserInformation...")
                    user_info.save()
                    print(f"✅ UserInformation saved successfully with ID: {user_info.userinfo_id}")
                    
                    # Create AccountsInformation (Pending, Farmer by default)
                    print("🔍 Getting AccountType and AccountStatus...")
                    
                    # Check if required objects exist
                    farmer_types = AccountType.objects.filter(account_type__iexact="Farmer")
                    verified_statuses = AccountStatus.objects.filter(acc_status__iexact="Verified")
                    
                    print(f"🔍 Found {farmer_types.count()} AccountType(s) matching 'Farmer':")
                    for at in farmer_types:
                        print(f"   🔸 {at.account_type} (ID: {at.account_type_id})")
                    
                    print(f"🔍 Found {verified_statuses.count()} AccountStatus(es) matching 'Verified':")
                    for vs in verified_statuses:
                        print(f"   🔸 {vs.acc_status} (ID: {vs.acc_stat_id})")
                    
                    if farmer_types.count() == 0:
                        raise Exception("No AccountType with type 'Farmer' found in database!")
                    if verified_statuses.count() == 0:
                        raise Exception("No AccountStatus with status 'Verified' found in database!")
                    
                    account_type_instance = farmer_types.first()
                    item_status_instance = verified_statuses.first()
                    print(f"📋 Using Account Type: {account_type_instance.account_type} (ID: {account_type_instance.account_type_id})")
                    print(f"📊 Using Account Status: {item_status_instance.acc_status} (ID: {item_status_instance.acc_stat_id})")
                    
                    print("📝 Creating AccountsInformation...")
                    account_info = AccountsInformation.objects.create(
                        userinfo_id=user_info,
                        account_type_id=account_type_instance,
                        acc_status_id=item_status_instance,
                        account_register_date=timezone.now()
                    )
                    print(f"✅ AccountsInformation created successfully with ID: {account_info.account_id}")
                    
                    # Success message
                    print("\n🎉 REGISTRATION SUCCESSFUL!")
                    print(f"👤 User: {user_info.firstname} {user_info.lastname}")
                    print(f"📧 Email: {reg_email}")
                    print(f"🏘️ Municipality: {user_info.municipality_id.municipality}")
                    print(f"🏠 Barangay: {user_info.barangay_id.barangay}")
                    print("="*50)
                    
                    # Optionally: clear session registration vars
                    for key in ['reg_email', 'reg_code', 'reg_password', 'reg_verified']:
                        if key in request.session:
                            del request.session[key]
                    return redirect('base:login')
                    
            except IntegrityError as ie:
                print("\n" + "🚫"*50)
                print("❌ DATABASE INTEGRITY ERROR!")
                print("🚫"*50)
                print(f"🔴 Integrity Error: {str(ie)}")
                print(f"📧 Email: {reg_email}")
                print(f"🏘️ Municipality Selected: {request.POST.get('municipality_id')}")
                print(f"🏠 Barangay Selected: {request.POST.get('barangay_id')}")
                print("🔍 This error suggests a database constraint violation")
                print("   Possible causes:")
                print("   - Duplicate email address")
                print("   - Duplicate RSBSA reference number")
                print("   - Foreign key constraint violation")
                print("🚫"*50)
                
                if 'email' in str(ie).lower():
                    error_msg = "This email address is already registered. Please use a different email."
                elif 'rsbsa' in str(ie).lower():
                    error_msg = "This RSBSA reference number is already in use. Please check your RSBSA number."
                else:
                    error_msg = f"Database integrity error: {str(ie)}"
                
                return render(request, 'registration/register_step1.html', {
                    'form': form,
                    'error_message': error_msg
                })
                
            except ValidationError as ve:
                print("\n" + "⚠️"*50)
                print("❌ VALIDATION ERROR!")
                print("⚠️"*50)
                print(f"🔴 Validation Error: {str(ve)}")
                print(f"📧 Email: {reg_email}")
                print(f"🏘️ Municipality Selected: {request.POST.get('municipality_id')}")
                print(f"🏠 Barangay Selected: {request.POST.get('barangay_id')}")
                print("⚠️"*50)
                
                return render(request, 'registration/register_step1.html', {
                    'form': form,
                    'error_message': f"Validation error: {str(ve)}"
                })
                    
            except Exception as e:
                print("\n" + "💥"*50)
                print("❌ REGISTRATION ERROR OCCURRED!")
                print("💥"*50)
                print(f"🔴 Exception Type: {type(e).__name__}")
                print(f"🔴 Exception Message: {str(e)}")
                print(f"📧 Email: {reg_email}")
                print(f"🏘️ Municipality Selected: {request.POST.get('municipality_id')}")
                print(f"🏠 Barangay Selected: {request.POST.get('barangay_id')}")
                
                # More detailed error info
                import traceback
                print(f"🔍 Full Traceback:")
                traceback.print_exc()
                print("💥"*50)
                
                form.add_error(None, f"Registration failed: {str(e)}. Please try again or contact support.")
        else:
            print("❌ Form validation failed, not proceeding with registration.")
            print("="*50)
    else:
        form = RegistrationForm()
    
    context = {
        'form': form,
        'reg_email': request.session.get('reg_email')
    }
    return render(request, 'registration/register_step1.html', context)


def register_step2(request):
    print("STEP 2 FORM HIT:", request.method)  # Debug
    if 'step1_data' not in request.session:
        return redirect('base:register_step1')
        return redirect('base:register_step1')  # magredirect sa unang page so users wouldnt skip p1
    
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():  # Everything inside here must succeed or nothing will be saved
                    
                    
                    auth_user = AuthUser.objects.create_user(
                        email=form.cleaned_data['user_email'],
                        password=form.cleaned_data['password1']
                    )

                    # Merge and save UserInformation na table
                    step1_data = request.session['step1_data']
                    
                    step1_data['barangay_id'] = BarangayName.objects.get(pk=step1_data['barangay_id'])
                    step1_data['municipality_id'] = MunicipalityName.objects.get(pk=step1_data['municipality_id'])
                    
                    if 'birthdate' in step1_data:
                        from datetime import date
                        if isinstance(step1_data['birthdate'], str):
                            step1_data['birthdate'] = date.fromisoformat(step1_data['birthdate'])
                    
                    userinfo = UserInformation.objects.create(
                        auth_user=auth_user,
                        contact_number=form.cleaned_data['contact_number'],
                        user_email=form.cleaned_data['user_email'],
                        civil_status=form.cleaned_data['civil_status'],
                        religion=form.cleaned_data['religion'],
                        rsbsa_ref_number=form.cleaned_data['rsbsa_ref_number'],
                        emergency_contact_person=form.cleaned_data['emergency_contact_person'],
                        emergency_contact_number=form.cleaned_data['emergency_contact_number'],
                        **step1_data  # merges all step 1 fields
                    )
                    account_type_instance = AccountType.objects.get(account_type_id=1) #1 = agriculturist
                    item_status_instance = AccountStatus.objects.get(acc_stat_id=3) # #3 = pending

                    AccountsInformation.objects.create(
                        userinfo_id = userinfo,
                        account_type_id = account_type_instance,
                        acc_status_id = item_status_instance,
                        account_register_date = timezone.now()
                    )

                    del request.session['step1_data']  # delete sesh
                    return redirect('base:login') 
            except Exception as e:
                print("Exception:", str(e))  # <-- Add this to see the real issue
                form.add_error(None, "Something went wrong during registration. Please try again.")
    else:
        form = RegistrationForm()

    return render(request, 'registration/register_step2.html', {'form': form})


def cancel_registration(request):
    """
    Cancel the current registration process by clearing all registration session data.
    Redirects user back to the email registration page.
    """
    # Clear all registration-related session data
    session_keys_to_clear = [
        'reg_email',
        'reg_password', 
        'reg_code',
        'step1_data',
        'email_verified'
    ]
    
    for key in session_keys_to_clear:
        if key in request.session:
            del request.session[key]
    
    # Add a success message
    messages.success(request, 'Registration cancelled successfully. You can now start over with a new email.')
    
    # Redirect to the email registration page
    return redirect('base:home')
 
  
def custom_login(request):
    if request.method == 'POST':
        email_or_contact = request.POST.get('email_or_contact')
        password = request.POST.get('password')
        
        # Authenticate user
        user = authenticate(request, username=email_or_contact, password=password)
        
        if user is not None:
            login(request, user)
            try:
                userinfo = UserInformation.objects.get(auth_user=user)
                account_info = AccountsInformation.objects.get(userinfo_id=userinfo)
                
                # Log user login
                UserLoginLog.objects.create(account_id=account_info)
                
                # Store session data
                request.session['userinfo_id'] = userinfo.userinfo_id
                request.session['account_id'] = account_info.account_id
                
                # Check account type and redirect accordingly
                if account_info.account_type_id.account_type in ['Administrator', 'Agriculturist']:
                    return redirect('administrator:admin_dashboard')
                else:
                    return redirect('base:home')
                    
            except (UserInformation.DoesNotExist, AccountsInformation.DoesNotExist):
                messages.error(request, 'Account information not found.')
                return redirect('base:login')
        else:
            messages.error(request, 'Invalid email or password.')
    
    return render(request, 'registration/login.html')


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
        
        # Check if email exists
        try:
            user = AuthUser.objects.get(email=email)
        except AuthUser.DoesNotExist:
            messages.error(request, "No account found with this email address.")
            return render(request, 'registration/forgot_password.html')
        
        # Generate OTP code
        verification_code = str(random.randint(100000, 999999))
        request.session["forgot_pwd_email"] = email
        request.session["forgot_pwd_code"] = verification_code
        request.session['forgot_pwd_code_time'] = int(time.time())
        
        # Send email with updated HTML format to match register_email
        subject = "Fruit Cast Password Reset Verification"
        
        html_message = """
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="color: #416e3f; padding: 20px; text-align: center; border-radius: 6px;">
                <a href="https://fruitcast-spro7.ondigitalocean.app/" style="text-decoration: none; color: #416e3f;">
                    <img src="https://raw.githubusercontent.com/AzterBrew/fruitcast-logo/refs/heads/main/3.png" style="max-height: 100px;">
                    <h1 style="margin: 0; font-size: 24px; font-weight: 700">FRUIT CAST PASSWORD RESET</h1>
                </a>
            </div>
            <div style="padding: 30px; background: white;">
                <div style="background: #fffadc;border-left: 4px solid #416e3f;padding: 20px;margin-bottom: 25px;">
                    <h2 style="margin: 0 0 10px;color: #104e0d;font-size: 20px;">🔓 Password Reset Request</h2>
                    <p style="margin: 0; color: #104e0d;">Your account password reset requires verification</p>
                </div>
                <p style="font-size: 16px; color: #333; margin-bottom: 20px;">Hello Farmer,</p>
                <p style="font-size: 15px; color: #555; line-height: 1.6;">
                    We've received a request to reset your account password. To ensure security and authorize this reset, please verify your identity using the code below.
                </p>
                <div style="background: #f4f4f4; border: 1px solid #ddd; border-radius: 6px; padding: 25px; text-align: center; margin: 25px 0;">
                    <div style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 10px;">Verification Code</div>
                    <div style="font-family: Courier, monospace; font-size: 24px; font-weight: bold; color: #2c3e50;">
                        {verification_code}
                    </div>
                    <div style="color: #999; font-size: 11px; margin-top: 10px;">Expires: 10 minutes from now</div>
                </div>
                <div style="background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; font-size: 14px; color: #2d5a27;">
                        <strong>🎯 Next Steps:</strong> Enter this code on the verification page to continue your password reset.
                    </p>
                </div>
                <div style="border-top: 1px solid #eee; padding-top: 20px; margin-top: 30px;">
                    <p style="font-size: 12px; color: #888; text-align: center;">
                        If you didn't request a password reset, please disregard this notification and ensure your account is secure.
                    </p>
                </div>
            </div>
            <div style="background: #f8f8f8; padding: 15px; text-align: center;">
                <p style="margin: 0; color: #666; font-size: 13px;">
                    🌱 &copy; 2025 Fruit Cast. All rights reserved.
                </p>
            </div>
        </div>
        """.format(verification_code=verification_code)
        
        # Send email with proper error handling
        try:
            email_msg = EmailMessage(
                subject=subject,
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,  # Use settings instead of hardcoded email
                to=[email],
            )
            email_msg.content_subtype = "html"
            email_msg.send()
            
            messages.success(request, f"Verification code sent to {email}. Please check your email.")
            return redirect("base:forgot_password_verify")
            
        except Exception as e:
            print(f"Email sending error: {e}")  # For debugging
            messages.error(request, "Failed to send verification email. Please try again later.")
            return render(request, 'registration/forgot_password.html')
    
    return render(request, 'registration/forgot_password.html')


def forgot_password_verify(request):
    if not request.session.get("forgot_pwd_email") or not request.session.get("forgot_pwd_code"):
        return redirect("base:forgot_password")
    
    if request.method == "POST":
        input_code = request.POST.get("otp_code")
        session_code = request.session.get("forgot_pwd_code")
        
        # Check if code has expired
        code_time = request.session.get('forgot_pwd_code_time')
        if not code_time or (int(time.time()) - code_time > 600):
            messages.error(request, "Verification code has expired. Please request a new one.")
            for key in ['forgot_pwd_email', 'forgot_pwd_code', 'forgot_pwd_code_time']:
                if key in request.session:
                    del request.session[key]
            return redirect("base:forgot_password")
        
        if input_code == session_code:
            request.session["forgot_pwd_verified"] = True
            return redirect("base:reset_password")
        else:
            messages.error(request, "Invalid verification code. Please try again.")
    
    email = request.session.get("forgot_pwd_email")
    return render(request, 'registration/forgot_password_verify.html', {'email': email})


def reset_password(request):
    if not request.session.get("forgot_pwd_verified"):
        return redirect("base:forgot_password")
    
    if request.method == "POST":
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        
        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'registration/reset_password.html')
        
        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, 'registration/reset_password.html')
        
        # Get the user and update password
        email = request.session.get("forgot_pwd_email")
        user = AuthUser.objects.get(email=email)
        user.set_password(new_password)
        user.save()
        
        # Clear session
        for key in ['forgot_pwd_email', 'forgot_pwd_code', 'forgot_pwd_code_time', 'forgot_pwd_verified']:
            if key in request.session:
                del request.session[key]
        
        messages.success(request, "Your password has been reset successfully! You can now login with your new password.")
        return redirect("base:login")
    
    return render(request, 'registration/reset_password.html')


def user_login(request):
    if request.method == 'POST':
        contact = request.POST['email_or_contact']
        password = request.POST['password']

        print("🔥 Login processing...")  
        print("🔥 DEBUG: POST Data ->", request.POST)

        # Check if the input is a numeric phone number or an email
        try:
            if contact.isdigit():  # If it's a number, use PhoneAuthBackend
                user = authenticate(request, username=contact, password=password)  
            else:  # Otherwise, use EmailAuthBackend
                user = authenticate(request, username=contact, password=password)  

            if user is not None:
                
                # First check if user has account information
                try:
                    user_info = UserInformation.objects.get(auth_user=user)
                    account_info = AccountsInformation.objects.get(userinfo_id=user_info)
                    
                    # Check account status before allowing login
                    if account_info.acc_status_id.acc_stat_id == 6:  # Suspended
                        messages.error(request, 'Your account has been suspended. Please contact the administrators to make an appeal to unsuspend your account.')
                        return render(request, 'registration/login.html')
                    
                    elif account_info.acc_status_id.acc_stat_id == 5:  # Archived - change to verified
                        verified_status = AccountStatus.objects.get(pk=2)  # Verified
                        account_info.acc_status_id = verified_status
                        account_info.save()
                        print("🔥 Account status changed from Archived to Verified")
                    
                    elif account_info.acc_status_id.acc_stat_id != 2:  # Only allow verified accounts (pk=2)
                        messages.error(request, 'Your account is not verified. Please contact administrators for assistance.')
                        return render(request, 'registration/login.html')
                    
                except (UserInformation.DoesNotExist, AccountsInformation.DoesNotExist):
                    # Handle superuser case or create missing account info
                    if user.is_superuser:
                        # Check if UserInformation exists for this user
                        if not UserInformation.objects.filter(auth_user=user).exists():
                            admin_type = AccountType.objects.get(account_type='Administrator')
                            active_status = AccountStatus.objects.get(pk=2)  # Verified
                            barangay = BarangayName.objects.get(pk=1)
                            municipality = MunicipalityName.objects.get(pk=1)
                            municipality_assigned = MunicipalityName.objects.get(pk=14)  # Adjust if needed

                            userinfo = UserInformation.objects.create(
                                auth_user=user,
                                firstname='Admin',
                                lastname='User',
                                middlename='',
                                nameextension='',
                                sex='',
                                contact_number='',
                                user_email=user.email,
                                birthdate='1950-01-01',
                                emergency_contact_person='',
                                emergency_contact_number='',
                                address_details='',
                                barangay_id=barangay,
                                municipality_id=municipality,
                                religion='None',
                                civil_status='Single',
                            )

                            account_info = AccountsInformation.objects.create(
                                userinfo_id=userinfo,
                                account_type_id=admin_type,
                                acc_status_id=active_status,
                                account_isverified=True,
                                account_register_date=timezone.now(),
                            )

                            admin_info = AdminInformation.objects.create(
                                userinfo_id=userinfo,
                                municipality_incharge=municipality_assigned,
                            )
                            
                            user_info = userinfo  # Set for session creation below
                    else:
                        print("no acc info record for this user")
                        messages.error(request, 'Account not registered')
                        return render(request, 'registration/login.html')
                
                # Login the user after all checks pass
                login(request, user)
                
                # Create login log and set session variables
                UserLoginLog.objects.create(
                    account_id=account_info, 
                )
                
                request.session['account_id'] = account_info.account_id
                request.session['userinfo_id'] = user_info.userinfo_id
                 
                print("🔥 Logged IN...logged to userloginlog")  # Debugging log

                if account_info.account_type_id.account_type_id == 2 or account_info.account_type_id.account_type_id == 3:
                    return redirect('administrator:admin_dashboard')
                else:                    
                    return redirect('base:home')
            else:
                messages.error(request, 'Invalid email/phone or password.')  
                print("🔥 Login failed...")  # Debugging log
                
        except ValueError:
            messages.error(request, "Invalid input for phone number.")

        return render(request, 'registration/login.html')

    return render(request, 'registration/login.html')


@login_required
def change_password(request):
    """First step: Enter current password"""
    if request.method == "POST":
        current_password = request.POST.get("current_password")
        confirm_password = request.POST.get("confirm_password")
        
        if current_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'loggedin/change_password.html')
        
        # Check if current password is correct
        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return render(request, 'loggedin/change_password.html')
        
        # Store email in session and generate OTP
        request.session["change_pwd_email"] = request.user.email
        verification_code = str(random.randint(100000, 999999))
        request.session["change_pwd_code"] = verification_code
        request.session['change_pwd_code_time'] = int(time.time())  # Store timestamp
        
        # Send email with similar format to register_email
        subject = "Fruit Cast Password Change Verification"
        
        # HTML message
        html_message = """
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="color: #416e3f; padding: 20px; text-align: center; border-radius: 6px;">
                <a href="https://fruitcast-spro7.ondigitalocean.app/" style="text-decoration: none; color: #416e3f;">
                    <img src="https://raw.githubusercontent.com/AzterBrew/fruitcast-logo/refs/heads/main/3.png" style="max-height: 100px;">
                    <h1 style="margin: 0; font-size: 24px; font-weight: 700">FRUIT CAST PASSWORD CHANGE</h1>
                </a>
            </div>
            <div style="padding: 30px; background: white;">
                <div style="background: #fffadc;border-left: 4px solid #416e3f;padding: 20px;margin-bottom: 25px;">
                    <h2 style="margin: 0 0 10px;color: #104e0d;font-size: 20px;">🔐 Password Change Request</h2>
                    <p style="margin: 0; color: #104e0d;">Your account password change requires verification</p>
                </div>
                <p style="font-size: 16px; color: #333; margin-bottom: 20px;">Hello Farmer,</p>
                <p style="font-size: 15px; color: #555; line-height: 1.6;">
                    We've received a request to change your account password. To ensure security and authorize this change, please verify your identity using the code below.
                </p>
                <div style="background: #f4f4f4; border: 1px solid #ddd; border-radius: 6px; padding: 25px; text-align: center; margin: 25px 0;">
                    <div style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 10px;">Verification Code</div>
                    <div style="font-family: Courier, monospace; font-size: 24px; font-weight: bold; color: #2c3e50;">
                        {verification_code}
                    </div>
                    <div style="color: #999; font-size: 11px; margin-top: 10px;">Expires: 10 minutes from now</div>
                </div>
                <div style="background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; font-size: 14px; color: #2d5a27;">
                        <strong>🎯 Next Steps:</strong> Enter this code on the verification page to continue your password change.
                    </p>
                </div>
                <div style="border-top: 1px solid #eee; padding-top: 20px; margin-top: 30px;">
                    <p style="font-size: 12px; color: #888; text-align: center;">
                        If you didn't request a password change, please disregard this notification and ensure your account is secure.
                    </p>
                </div>
            </div>
            <div style="background: #f8f8f8; padding: 15px; text-align: center;">
                <p style="margin: 0; color: #666; font-size: 13px;">
                    🌱 &copy; 2025 Fruit Cast. All rights reserved.
                </p>
            </div>
        </div>
        """.format(verification_code=verification_code)
        
        # Use EmailMessage for HTML email
        email_msg = EmailMessage(
            subject=subject,
            body=html_message,
            from_email="fruitcast.bataan@gmail.com",
            to=[request.user.email],
        )
        email_msg.content_subtype = "html"
        
        try:
            email_msg.send()
            messages.success(request, f"Verification code sent to {request.user.email}. Please check your email.")
            return redirect("base:change_password_verify")
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Email sending failed: {str(e)}")
            
            # If email fails, provide error message but still allow user to proceed for development
            if settings.DEBUG:  # Only in development mode
                messages.warning(request, f"Email service temporarily unavailable. Your verification code is: {verification_code}")
                messages.info(request, "Please use this code to continue (Development Mode)")
                print(f"🔐 PASSWORD CHANGE VERIFICATION CODE: {verification_code}")  # Console log for debugging
                return redirect("base:change_password_verify")
            else:
                # In production, show error and don't proceed
                messages.error(request, "Email service is currently unavailable. Please try again later or contact support.")
                # Clear session data
                for key in ['change_pwd_email', 'change_pwd_code', 'change_pwd_code_time']:
                    if key in request.session:
                        del request.session[key]
                return render(request, 'loggedin/change_password.html')
    
    return render(request, 'loggedin/change_password.html')


@login_required 
def change_password_verify(request):
    """Second step: Verify OTP code"""
    if not request.session.get("change_pwd_email") or not request.session.get("change_pwd_code"):
        # User hasn't started password change properly
        return redirect("base:change_password")
    
    if request.method == "POST":
        input_code = request.POST.get("otp_code")
        session_code = request.session.get("change_pwd_code")
        
        # Check if code has expired (10 minutes)
        code_time = request.session.get('change_pwd_code_time')
        if not code_time or (int(time.time()) - code_time > 600):  # 600 seconds = 10 minutes
            messages.error(request, "Verification code has expired. Please request a new one.")
            # Clear session
            for key in ['change_pwd_email', 'change_pwd_code', 'change_pwd_code_time']:
                if key in request.session:
                    del request.session[key]
            return redirect("base:change_password")
        
        if input_code == session_code:
            request.session["change_pwd_verified"] = True
            return redirect("base:change_password_new")
        else:
            messages.error(request, "Invalid verification code. Please check your email and try again.")
    
    email = request.session.get("change_pwd_email")
    return render(request, 'loggedin/change_password_verify.html', {'email': email})


@login_required
def change_password_new(request):
    """Third step: Enter new password"""
    if not request.session.get("change_pwd_verified"):
        # User hasn't completed verification
        return redirect("base:change_password")
    
    if request.method == "POST":
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        
        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'loggedin/change_password_new.html')
        
        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, 'loggedin/change_password_new.html')
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        # Clear session
        for key in ['change_pwd_email', 'change_pwd_code', 'change_pwd_code_time', 'change_pwd_verified']:
            if key in request.session:
                del request.session[key]
        
        messages.success(request, "Your password has been reset successfully! You can now login with your new password.")
        return redirect("base:account_info_panel")
    
    return render(request, 'loggedin/change_password_new.html')


def custom_logout(request):
    """
    Custom logout view that redirects to the guest home page instead of login page
    """
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('base:home')  # Redirect to the guest home page




