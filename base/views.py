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
import json
#from .forms import CustomUserCreationForm  # make sure this is imported
from django.http import JsonResponse
from django.db import transaction

from .models import *
from dashboard.models import *
from .forms import UserContactAndAccountForm, CustomUserInformationForm, EditUserInformation, HarvestRecordCreate, PlantRecordCreate, RecordTransactionCreate


# @login_required > btw i made this not required so that it doesn't require the usr to login just to view the home page


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
            context = {
                'user_firstname' : userinfo.firstname,
                'user_role_id' : accinfo.account_type_id.account_type_id
            }
            return render(request, 'loggedin/home.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')         
    else:        
        return render(request, 'home.html', {})
     

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
                key = record.commodity_type
                commodity_data[key] = commodity_data.get(key, 0) + 1

            # Dataset 2: by location
            location_data = {}
            for record in initHarvestRecord.objects.all():
                key = record.harvest_municipality
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
        key = record.commodity_type
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
            
            
            if view_to_show == "harvest":
                form = HarvestRecordCreate(request.POST or None)
                transaction_form = RecordTransactionCreate(request.POST or None, user=request.user)
                context['form'] = form
                context['transaction_form'] = transaction_form

                with open('static/geojson/BATAAN_MUNICIPALITY.geojson', 'r') as f:
                    barangay_data = json.load(f)
                
                harvest_data = VerifiedHarvestRecord.objects.all()
                
                
                if request.method == "POST" and form.is_valid():
                    # Get the current list from session or empty list
                    pending_records = request.session.get('pending_harvest_records', [])                    
                    record_data = form.cleaned_data.copy()
                    record_data['harvest_barangay'] = request.POST.get('harvest_barangay')
                    record_data['record_type'] = 'harvest'
                    print(f"succesfully added {record_data['record_type']}")
                    
                    for key, value in record_data.items():
                        if isinstance(value,date):
                            record_data[key] = value.isoformat() # Converts date to 'YYYY-MM-DD' string
                        if isinstance(value, Decimal):
                            record_data[key] = float(value)
                            
                    
                    pending_records.append(record_data)

                    # Save back to session
                    request.session['pending_harvest_records'] = pending_records
                    request.session.modified = True
                    request.session['current_record_type'] = record_data['record_type']
                    print(f"about to redirect to list {record_data['record_type']}")
                    

                    return redirect(f"{reverse('base:newrecord')}?view=transaction_list")  
                
            elif view_to_show == "plant":
                form = PlantRecordCreate(request.POST or None)
                context['form'] = form
                
                with open('static/geojson/Barangays.json', 'r') as f:
                    barangay_data = json.load(f)
                
                plant_data = VerifiedPlantRecord.objects.all()
                
                if request.method == "POST" and form.is_valid():
                    pending_records = request.session.get('pending_plant_records', [])
                    record_data = form.cleaned_data.copy()
                    record_data['plant_barangay'] = request.POST.get('plant_barangay')
                    record_data['record_type'] = 'plant'
                    
                    
                    for key, value in record_data.items():
                        if isinstance(value, date):
                            record_data[key] = value.isoformat()
                        if isinstance(value, Decimal):
                            record_data[key] = float(value)

                    pending_records.append(record_data)
                    request.session['pending_plant_records'] = pending_records
                    request.session['current_record_type'] = record_data['record_type']
                    
                    request.session.modified = True
                    context = {
                        'map_data': json.dumps(barangay_data),
                    }

                    return redirect(f"{reverse('base:newrecord')}?view=transaction_list", context)
                
            elif view_to_show == "transaction_list":
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

            elif view_to_show == "farmland_list":
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

    if not request.user.is_authenticated:
        return redirect('base:home')

    if request.session.get('pending_plant_records'):
        record_type = 'plant'
    elif request.session.get('pending_harvest_records'):
        record_type = 'harvest'
    else:
        print("❌ No pending records found!")
        return redirect('base:transaction_recordlist')
    
    print(f"Record Type: {record_type}")
    if record_type not in ['harvest', 'plant']:
        # print(f"not in harvest or plant {record_type}")        
        # print(f"Not in ['harvest', 'plant']: {record_type}") 
        return redirect('base:transaction_recordlist')  # Fallback

    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
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
                transaction_id=transaction,
                harvest_date=data['harvest_date'],
                commodity_type=data['commodity_type'],
                commodity_spec=data['commodity_spec'],
                total_weight=data['total_weight'],
                unit=data['unit'],
                weight_per_unit=data['weight_per_unit'],
                harvest_municipality=data['harvest_municipality'],
                harvest_barangay=data['harvest_barangay'],
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
    return redirect(f"{reverse('base:newrecord')}?view=choose")



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

    return redirect(f"{reverse('base:newrecord')}?view=transaction_list")



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



def transaction_history(request):
    if not request.user.is_authenticated:
        return redirect('base:home')

    try:
        # print("account is testing rn:", userinfo_id)        
        userinfo_id = request.session.get('userinfo_id')
        accountinfo = AccountsInformation.objects.get(userinfo_id=userinfo_id)
    except AccountsInformation.DoesNotExist:
        print("❌ AccountInfo not found for userinfo_id:", userinfo_id)
        return render(request, 'loggedin/transaction/transaction_history.html', {
            'transactions': [],
            'user_firstname': 'Unknown',
        })

    transactions = RecordTransaction.objects.filter(account_id=accountinfo).order_by('-transaction_date')

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






def plantrecord(request):
    print("🔥 DEBUG: newrecord view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
        
            context = {
                'user_firstname' : userinfo.firstname,
            }            
            return render(request, 'loggedin/transaction/plant_record.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('home')   
    else :
        return render(request, 'home.html', {}) 


def get_barangays(request):
    municipality_id = request.GET.get('municipality_id')
    barangays = BarangayName.objects.filter(municipality_id=municipality_id).values('id', 'barangay_name')
    return JsonResponse(list(barangays), safe=False)


def about(request):
    print("🔥 DEBUG: about view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        return render(request, 'loggedin/about.html', {})
    else :
        return render(request, 'about.html', {})  


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
                
                return redirect('base:accinfo')                
        
        else:
            form = EditUserInformation(instance=userinfo)

        return render(request, 'loggedin/account_edit.html', {'form': form})
    else :
        return render(request, 'home.html', {})  


def accinfo(request):
    print("🔥 DEBUG: account view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
        
            context = {
                'user_firstname' : userinfo.firstname,
                'user_middlename' : userinfo.middlename,
                'user_lastname' : userinfo.lastname,
                'user_nameext' : userinfo.nameextension,
                'user_sex' : userinfo.sex,
                'user_dob' : userinfo.birthdate,
                'user_emperson' : userinfo.emergency_contact_person,
                'user_emcontact' : userinfo.emergency_contact_number,
                'user_address_details' : userinfo.address_details,
                'user_barangay' : userinfo.barangay_id,
                'user_municipality' : userinfo.municipality_id,
                'user_contactno' : userinfo.contact_number,
                'user_email' : userinfo.user_email,
                'user_religion' : userinfo.religion,
                'user_civil_status' : userinfo.civil_status,
                'user_rsbsa_ref_number' : userinfo.rsbsa_ref_number,
            }            
            return render(request, 'loggedin/account_info.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('home') #dapat redirect si user sa guest home
    else :
        return render(request, 'home.html', {})   
    

def login_success(request):
    print("🔥 Login successful! Redirecting...")  # Debugging log
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        return render(request, 'loggedin/home.html', {})
    else:        
        return render(request, 'home.html', {})
    # return redirect("base:home")  
    # Redirect to home *manually*

def get_barangays(request, municipality_id):
    barangays = BarangayName.objects.filter(municipality_id=municipality_id).values('barangay_id', 'barangay')
    return JsonResponse([{'id': b['barangay_id'], 'name': b['barangay']} for b in barangays], safe=False)
    
def register_step1(request):
    if request.user.is_authenticated: 
        return render(request, 'loggedin/home.html', {})

    else:
        if request.method == "POST":
            form = CustomUserInformationForm(request.POST)
            if form.is_valid():
                step1_data = form.cleaned_data.copy()

                if isinstance(step1_data.get("birthdate"), date):
                    step1_data["birthdate"] = step1_data["birthdate"].isoformat()

                barangay_obj = step1_data.get("barangay_id")
                municipality_obj = step1_data.get("municipality_id")

                step1_data["barangay_id"] = barangay_obj.pk if barangay_obj else None
                step1_data["municipality_id"] = municipality_obj.pk if municipality_obj else None

                request.session['step1_data'] = step1_data
                
                return redirect('base:register_step2')
        else:
            step1_data = request.session.get('step1_data')
            if step1_data:
                # Convert stored PKs back into objects
                if step1_data.get("barangay_id"):
                    step1_data["barangay_id"] = BarangayName.objects.get(pk=step1_data["barangay_id"])
                if step1_data.get("municipality_id"):
                    step1_data["municipality_id"] = MunicipalityName.objects.get(pk=step1_data["municipality_id"])
            form = CustomUserInformationForm(initial=request.session.get('step1_data'))

        return render(request, 'registration/register_step1.html', {'form': form})


def register_step2(request):
    print("STEP 2 FORM HIT:", request.method)  # Debug
    if 'step1_data' not in request.session:
        return redirect('base:register_step1')
        return redirect('base:register_step1')  # magredirect sa unang page so users wouldnt skip p1
    
    if request.method == "POST":
        form = UserContactAndAccountForm(request.POST)
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
        form = UserContactAndAccountForm()

    return render(request, 'registration/register_step2.html', {'form': form})

 
def custom_login(request):
    
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
                login(request, user)
                
                try:
                    user_info = UserInformation.objects.get(auth_user=request.user)
                    account_info = AccountsInformation.objects.get(userinfo_id__auth_user=user)
                    
                    
                    UserLoginLog.objects.create(
                        account_id=account_info, 
                        )
                    
                    request.session['account_id'] = account_info.account_id
                    request.session['userinfo_id'] = user_info.userinfo_id
                     
                    print("🔥 Logged IN...logged to userloginlog")  # Debugging log
                
                except AccountsInformation.DoesNotExist:
                    print("no acc info record for this user")
                    messages.error(request, 'Account not registered')  
                    
                return redirect('base:home')
            else:
                messages.error(request, 'Invalid email/phone or password.')  
                print("🔥 Login failed...")  # Debugging log
                
        except ValueError:
            messages.error(request, "Invalid input for phone number.")

        return render(request, 'registration/login.html')

    return render(request, 'registration/login.html')


# def registerauth(request):
#     form = CustomUserCreationForm()
    
#     if request.method == "POST":
#         form = CustomUserCreationForm(request.POST)
#         if form.is_valid():
#             form.save()
#             return redirect('base:login')
    
#     context = {'form': form}
#     return render(request, 'registration/signup.html', context)
    
# def custom_login(request):
#     if request.method == 'POST':
#         contact = request.POST['email_or_contact']
#         password = request.POST['password']
#         if contact.isdigit():
#             user = authenticate(request, username=contact, password=password)  # Phone login
#         else:
#             user = authenticate(request, username=contact, password=password)  # Email login

#         print("🔥 Login processing...")  # Debugging log
#         print("🔥 DEBUG: POST Data ->", request.POST)
#         if user is not None:
#             login(request, user)
#             messages.success(request, 'You are now logged in!') 
#             print("🔥 Logged IN...")  # Debugging log
                       
#             return redirect('base:home')
#         else:
#             messages.error(request, 'Invalid email/phone or password.')  
#             print("🔥 Login failed...")  # Debugging log
                      
#             return render(request, 'registration/login.html')
#     return render(request, 'registration/login.html')    


# def authView(request):
#     if request.method == "POST":
#         form = UserCreationForm(request.POST or None)
#         if form.is_valid():
#             form.save()
#             return redirect("base:login")
#     else : 
#         form = UserCreationForm()
#     return render(request, 'registration/signup.html', {'form' : form})

# def register_step1(request):
#     if request.method == "POST":
#         form = CustomUserInformationForm(request.POST)
#         if form.is_valid():
#             # userinfo = form.save(commit=False)  # Don't save yet
#             # userinfo.save()  # Save the first step of user info
#             # request.session['userinfo_id'] = userinfo.id  # Store userinfo id in session
#             # return redirect('register_step2')
#             # request.session['step1_data'] = form.cleaned_data  # 🔐 Save input to session
            

#         # Cleaned version of form data, with date fields converted to string
#             step1_data = form.cleaned_data.copy()

#             # Convert date objects to strings manually (you can also loop over fields to detect types, but this is safer & explicit)
#             if isinstance(step1_data.get("birthdate"), date):
#                 step1_data["birthdate"] = step1_data["birthdate"].isoformat()

#             request.session['step1_data'] = step1_data
            
#             return redirect('base:register_step2')
#     else:
#         form = CustomUserInformationForm(initial=request.session.get('step1_data'))

#     return render(request, 'registration/register_step1.html', {'form': form})


# def register_step2(request):
    # if request.method == "POST":
    #     userinfo_id = request.session.get('userinfo_id')
    #     userinfo = UserInformation.objects.get(id=userinfo_id)

    #     form = UserContactAndAccountForm(request.POST)
    #     if form.is_valid():
    #         user = form.save(commit=False)
    #         userinfo.user_email = form.cleaned_data['user_email']
    #         userinfo.contact_number = form.cleaned_data['contact_number']
    #         userinfo.save()  # Save the additional user info

    #         # Create Account Information
    #         account_info = AccountsInformation.objects.create(
    #             userinfo_id=userinfo,
    #             account_register_date=form.cleaned_data['password1'],  # For example, password1 used here just for demonstration
    #             account_isverified=False,  # Set to False until verified by admin
    #         )

    #         # Create user in auth_user table
    #         auth_user = models.User.objects.create_user(username=userinfo.user_email, password=form.cleaned_data['password1'])
    #         login(request, auth_user)  # Log the user in
            
    #         return redirect('success')  # Redirect to success or homepage after registration
    # else:
    #     form = UserContactAndAccountForm()

    # return render(request, 'registration/register_step2.html', {'form': form})
    
    
# def loginauth(request):
#     if request.method=="POST":
#         username = request.POST.get('username')
#         password = request.POST.get('password')
        
#         user = authenticate(request, username=username, password=password)
        
#         if user is not None:
#             login(request, user)
#             return redirect('base:home')
#         else :
#             messages.error(request, 'user or pass incorrect')
    
#     context = {}
#     return render(request, 'login.html',context)


# def transaction_recordlist(request): NOT NECESSARY ANYMORE
#     if not request.user.is_authenticated:
#         return redirect('base:home')
    
#     pending_harvest = request.session.get('pending_harvest_records', [])
#     pending_plant = request.session.get('pending_plant_records', [])
    
#     if pending_harvest:
#         record_type = 'harvest'
#         pending_records = pending_harvest
#     elif pending_plant:
#         record_type = 'plant'
#         pending_records = pending_plant
#     else:
#         # Default to harvest if none are present (or you can show an empty message)
#         record_type = 'none'
#         pending_records = []
#     print(f"record type new is {record_type}")
    
    
#     userinfo_id = request.session.get('userinfo_id')
#     userinfo = UserInformation.objects.get(pk=userinfo_id)

#     # Get the correct records from the session (harvest or plant)
#     record_type = request.GET.get("record_type") or request.session.get("current_record_type","harvest")
#     print(f"record type updated is {record_type}")
    
#     if record_type == "plant":
#         pending_records = request.session.get('pending_plant_records', [])
#     else:
#         pending_records = request.session.get('pending_harvest_records', [])

#     userinfo_id = request.session.get('userinfo_id')
#     userinfo = UserInformation.objects.get(pk=userinfo_id)
#     print(f"record type is {record_type}")
#     context = {
#         'pending_records': pending_records,
#         'user_firstname': userinfo.firstname,
#         'record_type': record_type, 
#     }

#     return render(request, 'loggedin/transaction/transaction_recordlist.html', context)



# def transaction_recordlist(request):
#     if not request.user.is_authenticated:
#         return redirect('base:home')

#     pending_records = request.session.get('pending_harvest_records', [])
#     userinfo_id = request.session.get('userinfo_id')
#     userinfo = UserInformation.objects.get(pk=userinfo_id)

#     context = {
#         'pending_records': pending_records,
#         'user_firstname': userinfo.firstname,
#     }

#     return render(request, 'loggedin/transaction/transaction_recordlist.html', context)

# @require_POST
# def finalize_transaction(request):   OLD
#     if not request.user.is_authenticated:
#         return redirect('base:home')

#     account_id = request.session.get('account_id')
#     userinfo_id = request.session.get('userinfo_id')
#     accountinfo = AccountsInformation.objects.get(pk=account_id)
#     userinfo = UserInformation.objects.get(pk=userinfo_id)
    
#     records = request.session.get('pending_harvest_records', [])

#     if not records:
#         return redirect('base:transaction_recordlist')  # Nothing to save

#     transaction = Transaction.objects.create(
#         account_id=accountinfo,
#         transaction_type="Harvest",
#         notes="Submitted via transaction cart",
#         item_status_id=ItemStatus.objects.get(item_status_id=3) #value is Pending sa itemstatus table
#     )

#     for data in records:
#         HarvestRecord.objects.create(
#             transaction_id=transaction,
#             harvest_date=data['harvest_date'],
#             commodity_type=data['commodity_type'],
#             commodity_spec=data['commodity_spec'],
#             total_weight=data['total_weight'],
#             unit=data['unit'],
#             weight_per_unit=data['weight_per_unit'],
#             harvest_location=data['harvest_location'],
#             remarks=data.get('remarks', '')
#         )

#     # Clear session
#     del request.session['pending_harvest_records']
#     return redirect(f"{reverse('base:newrecord')}?view=choose")  # Or a success page


# @require_POST OLD
# def remove_pending_record(request, index):
#     if not request.user.is_authenticated:
#         return redirect('base:home')

#     pending_records = request.session.get('pending_harvest_records', [])
#     if 0 <= index < len(pending_records):
#         del pending_records[index]
#         request.session['pending_harvest_records'] = pending_records
#         request.session.modified = True

#     return redirect(f"{reverse('base:newrecord')}?view=transaction_list")


# def edit_pending_record(request, index):      OLD
#     if not request.user.is_authenticated:
#         return redirect('base:home')

#     pending_records = request.session.get('pending_harvest_records', [])
#     if index < 0 or index >= len(pending_records):
#         return redirect(f"{reverse('base:newrecord')}?view=transaction_list")

#     record_data = pending_records[index]

#     # Convert stored ISO dates/strings back to usable values
#     form = HarvestRecordCreate(initial=record_data)

#     if request.method == "POST":
#         form = HarvestRecordCreate(request.POST)
#         if form.is_valid():
#             updated_data = form.cleaned_data.copy()
#             # Convert again
#             for key, value in updated_data.items():
#                 if isinstance(value, date):
#                     updated_data[key] = value.isoformat()
#                 if isinstance(value, Decimal):
#                     updated_data[key] = float(value)
#             pending_records[index] = updated_data
#             request.session['pending_harvest_records'] = pending_records
#             request.session.modified = True
#             return redirect(f"{reverse('base:newrecord')}?view=transaction_list")
        
        
#     from_transactionedit = request.GET.get("from") == "transactionedit"
#     # Pass the same context you use in `newrecord`
#     context = {
#         'form': form,
#         'view_to_show': 'harvest',
#         'pending_records': pending_records,
#         'from_transactionedit' : from_transactionedit,
#     }
#     return render(request, 'loggedin/transaction/transaction.html', context)


# def newrecord(request):           WORKING HARVESTRECORD SUBMISSION
#     print("🔥 DEBUG: newrecord view called!")  
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
#             accountinfo = AccountsInformation.objects.get(pk=account_id)
#             view_to_show = request.GET.get("view", "") #for showing another page within another page ()yung transaction and harves/plant

#             form = None
#             if view_to_show == "harvest":
#                 form = HarvestRecordCreate(request.POST or None)
                
#                 if request.method == "POST" and form.is_valid():
#                     transaction = Transaction.objects.create(
#                         account_id=accountinfo,
#                         transaction_type="Harvest",
#                         notes=form.cleaned_data.get("remarks","")
#                     ) 
                    
#                     harvest = form.save(commit=False)
#                     harvest.transaction_id = transaction
#                     harvest.user_info = userinfo
#                     harvest.save()
                    
#                     return redirect('base:home')  

#             context = {
#                 'user_firstname': userinfo.firstname,
#                 'view_to_show': view_to_show,
#                 'form': form,
#             }
#             return render(request, 'loggedin/transaction/transaction.html', context)
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('base:home')
#     else:
#         return render(request, 'home.html', {})


# def newrecord(request):     #e2 po for transaction / creating new records  ACTUALLY OLD VER
#     print("🔥 DEBUG: newrecord view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:            
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
            
#             view_to_show = request.GET.get("view", "") # for transaction na page, displaying other pages with include kineme
        
#             context = {
#                 'user_firstname' : userinfo.firstname,
#                 'view_to_show' : view_to_show,
#             }            
            
#             return render(request, 'loggedin/transaction/transaction.html', context)
        
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('base:home')   
#     else :
#         return render(request, 'home.html', {}) 


# def harvestrecord(request):    OLD VERSION (nimove over to newrecord() kase i just included the harvestrecord.html within the transaciton.html, not redirected to the page, so this function isnt really happening)
#     print("🔥 DEBUG: newrecord harvest view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
#             form = HarvestRecordCreate(request.POST or None)

#             if request.method == "POST" and form.is_valid():
#                 form.instance.user_info = userinfo  # Set FK if needed
#                 form.save()
#                 return redirect('some_success_url')  # TODO: change this
            
#             context = {
#                 'user_firstname': userinfo.firstname,
#                 'form': form
#             }

#             return render(request, 'loggedin/transaction/harvest_record.html', context)
#         else:
#             print("⚠️ account_id or userinfo_id missing in session!")
#             return redirect('base:home')   
#     else :
#         return render(request, 'home.html', {}) 

