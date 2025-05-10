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
from django.db.models import Sum, Avg
from django.http import JsonResponse

#from .forms import CustomUserCreationForm  # make sure this is imported

from base.models import *
from dashboard.models import *
from base.forms import UserContactAndAccountForm, CustomUserInformationForm, EditUserInformation, HarvestRecordCreate, PlantRecordCreate

# Create your views here.
def home(request):
    print("🔥 DEBUG: Home view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
        
            context = {
                'user_firstname' : userinfo.firstname,
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
            return redirect('base:home')                
            
    else :
        return render(request, 'home.html', {})  
    
    
def monitor(request):
    print("🔥 DEBUG: monitor view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            context = {
                
            }

            # Example data: commodity_type counts
            # Dataset 1: by commodity type
            
            # harvest_by_commodity = (
            #     VerifiedHarvestRecord.objects
            #     .values('commodity_type')
            #     .annotate(
            #         total_weight=Sum('total_weight_kg'),
            #         avg_weight_per_unit=Avg('weight_per_unit_kg')
            #     )
            # )

            # commodity_labels = []
            # commodity_values = []
            # commodity_avg_weight = []

            # for entry in harvest_by_commodity:
            #     commodity_labels.append(entry['commodity_type'])
            #     commodity_values.append(float(entry['total_weight']))
            #     commodity_avg_weight.append(float(entry['avg_weight_per_unit'] or 0))

            # # Harvest by Location (for doughnut chart)
            # harvest_by_location = (
            #     VerifiedHarvestRecord.objects
            #     .values('harvest_location')
            #     .annotate(total=Sum('total_weight_kg'))
            # )

            # location_labels = [entry['harvest_location'] for entry in harvest_by_location]
            # location_values = [float(entry['total']) for entry in harvest_by_location]

            # context = {
            #     'commodity_labels': commodity_labels,
            #     'commodity_values': commodity_values,
            #     'commodity_avg_weight': commodity_avg_weight,
            #     'location_labels': location_labels,
            #     'location_values': location_values,
            # }
            
            
            # for x in recordentry:
            #     for y in commodity_list:
            #         finalrep[y]=get
          
            # return render(request, 'monitoring/overall_dashboard.html', context)
            return render(request, 'monitoring/overall_dashboard.html')
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')                
            
    else :
        return render(request, 'home.html', {})  

# def dashboard_view(request):
#     last_7_days = now().date() - timedelta(days=7)
#     recent_records = HarvestRecord.objects.filter(harvest_date__gte=last_7_days)

#     # Example data: commodity_type counts
#     data = {}
#     for record in recent_records:
#         key = record.commodity_type
#         data[key] = data.get(key, 0) + 1

#     context = {
#         'labels': list(data.keys()),
#         'values': list(data.values()),
#     }
#     return render(request, 'loggedin/dashboard.html', context)

def commoditytype_collect(request) : #pang kuha ng distinct commodity type sa verified_harvest at plant record
    recordentry = VerifiedHarvestRecord.objects.all()
    finalrep= {}
            
    def get_commodity_type(recordentry) :
        return recordentry.commodity_type
            
    commodity_list = list(set(map(get_commodity_type,recordentry))) #gets the commodity type in every record in harvestrecord and then list it out (no repetitions because of set function)
    print("attempt sa query ")
          
    print(commodity_list)