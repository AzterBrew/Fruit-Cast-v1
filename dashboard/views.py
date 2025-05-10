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

#from .forms import CustomUserCreationForm  # make sure this is imported

from base.models import *
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
            

            # Example data: commodity_type counts
            # Dataset 1: by commodity type
            commodity_data = {}
            for record in HarvestRecord.objects.all():
                key = record.commodity_type
                commodity_data[key] = commodity_data.get(key, 0) + 1

            # Dataset 2: by location
            location_data = {}
            for record in HarvestRecord.objects.all():
                key = record.harvest_location
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
