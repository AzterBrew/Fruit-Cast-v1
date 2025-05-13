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
import pandas as pd
from collections import defaultdict, OrderedDict
import random
from django.db.models.functions import TruncMonth, ExtractYear, ExtractMonth
import calendar
from prophet import Prophet
from datetime import datetime
import json
from shapely.geometry import shape
from dashboard.utils import generate_notifications, get_current_month

#from .forms import CustomUserCreationForm  # make sure this is imported

from base.models import *
from dashboard.models import *
from dashboard.forms import CommodityTypeForm

def notifications(request):
    account_id = request.session.get('account_id')
    crops = []

    if account_id:
        plant_records = VerifiedPlantRecord.objects.filter(
            prev_record__transaction_id__account_id=account_id
        ).values_list('commodity_type', flat=True).distinct()
        
        crops = [crop for crop in plant_records if crop]  # Remove nulls or blanks if needed

    notifications = generate_notifications(crops)

    return render(request, 'notifications.html', {
        'notifications': notifications,
    })

def create_verification_notification(user, record_type):
    message = f"Your {record_type} record has been verified!"
    Notification.objects.create(user=user, message=message)

def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'notifications.html', {'notifications': notifications})


# Create your views here.
# def home(request):
#     print("🔥 DEBUG: Home view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

#     if request.user.is_authenticated:
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
            
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
        
#             context = {
#                 'user_firstname' : userinfo.firstname,
#             }            
#             return render(request, 'loggedin/home.html', context)
        
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('base:home')         
#     else:        
#         return render(request, 'home.html', {})
     
fruit_seasons = {
    "Mango": ("March", "June"),
    "Banana": ("All Year", "All Year"),
    "Papaya": ("All Year", "All Year"),
    "Pineapple": ("March", "June"),
    "Lanzones": ("September", "November"),
    "Rambutan": ("August", "October"),
    "Guava": ("August", "October"),
    "Durian": ("August", "October"),
    "Mangosteen": ("July", "September"),
    "Calamansi": ("August", "October"),
    "Watermelon": ("March", "July"),
    "Avocado": ("July", "September"),
    "Pomelo": ("August", "October"),
}

def forecast(request):
    print("🔥 DEBUG: forecast view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    
    if request.user.is_authenticated:
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')

        if userinfo_id and account_id:
            userinfo = UserInformation.objects.get(pk=userinfo_id)

            selected_commodity = request.GET.get('commodity_type')
            qs = VerifiedHarvestRecord.objects.all()
            commodity_types = qs.values_list('commodity_type', flat=True).distinct()

            if selected_commodity:
                qs = qs.filter(commodity_type=selected_commodity)
            else:
                selected_commodity = commodity_types.first() if commodity_types else None
                if selected_commodity:
                    qs = qs.filter(commodity_type=selected_commodity)

            qs = qs.values('harvest_date', 'total_weight_kg', 'weight_per_unit_kg', 'commodity_type', 'harvest_barangay', 'harvest_municipality')

            forecast_data = None
            if qs.exists():
                df = pd.DataFrame.from_records(qs)
                df['ds'] = pd.to_datetime(df['harvest_date'])
                df['y'] = df['total_weight_kg'] / df['weight_per_unit_kg']

                df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
                df['ds'] = df['ds'].dt.to_timestamp()

                model = Prophet()
                model.fit(df)

                future = model.make_future_dataframe(periods=12, freq='M')  # Forecast 12 months
                forecast = model.predict(future)

                # Adjust forecast based on peak season
                # For simplicity, we assume the boost factor is 1.5 for peak months
                peak_months = fruit_seasons.get(selected_commodity)
                if peak_months and peak_months != ("All Year", "All Year"):
                    peak_start, peak_end = peak_months
                    peak_start = datetime.strptime(peak_start, '%B').month
                    peak_end = datetime.strptime(peak_end, '%B').month

                    forecast['adjusted_yhat'] = forecast['yhat']

                    # Boost forecast for the peak months
                    for i, row in forecast.iterrows():
                        month = row['ds'].month
                        if peak_start <= month <= peak_end:
                            forecast.at[i, 'adjusted_yhat'] = forecast.at[i, 'yhat'] * 1.5  #  1.5 yung multiplier

                labels = forecast['ds'].dt.strftime('%B %Y').tolist()
                values = forecast['adjusted_yhat'].round().tolist()
                combined_forecast = list(zip(labels, values))  

                forecast_data = {
                    'labels': labels,
                    'forecasted_count': values,
                    'combined': combined_forecast  # Add zipped list here
                }
                
            # 2D MAPPING STUFF
            
            with open('static/geojson/Barangays.json', 'r') as f:
                geojson_data = json.load(f)
            
            
            map_data = []

            for feature in geojson_data['features']:
                # Get the geometry (polygon)
                geom = shape(feature['geometry'])
                # Calculate the centroid of the polygon
                centroid = geom.centroid
                latitude = centroid.y
                longitude = centroid.x

                # Extract relevant properties (barangay, municipality)
                barangay = feature['properties']['NAME_3']
                municipality = feature['properties']['NAME_2']
                province = feature['properties']['PROVINCE']

                # Add the centroid coordinates to the map_data list
                map_data.append({
                    'latitude': latitude,
                    'longitude': longitude,
                    'barangay': barangay,
                    'municipality': municipality,
                    'province': province,
                    'forecasted_amount': 0
                })

            # Now we update the map_data with forecast information
            if qs.exists():
                df = pd.DataFrame.from_records(qs)
                df['ds'] = pd.to_datetime(df['harvest_date'])
                df['y'] = df['total_weight_kg'].apply(float) / df['weight_per_unit_kg'].apply(float)

                df['month'] = df['ds'].dt.month
                df['year'] = df['ds'].dt.year
                df = df.groupby(['month', 'year', 'commodity_type', 'harvest_barangay', 'harvest_municipality'])['y'].sum().reset_index()

                # Optionally filter by selected month and commodity_type
                if selected_commodity:
                    df = df[df['commodity_type'] == selected_commodity]

                # Create map data entries with forecasted amounts
                for index, forecast_row in df.iterrows():
                    barangay = forecast_row['harvest_barangay']
                    forecasted_amount = forecast_row['y']  # Or your forecast logic
                    # Find the matching barangay in the map data
                    for item in map_data:
                        if item['barangay'] == barangay:
                            item['forecasted_amount'] = forecasted_amount
                            break 

            context = {
                'user_firstname': userinfo.firstname,
                'forecast_data': forecast_data,
                'commodity_types': commodity_types,
                'selected_commodity': selected_commodity,
                'map_data': map_data,  
            }
            
            return render(request, 'forecasting/forecast.html', context)

        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')

    else:
        return render(request, 'home.html', {})


# def forecast(request):        LAST LATEST VER
#     print("🔥 DEBUG: forecast view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
            
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
            
#             selected_commodity = request.GET.get('commodity_type')
#             qs = VerifiedHarvestRecord.objects.all()
#             commodity_types = qs.values_list('commodity_type', flat=True).distinct()

#             if selected_commodity:
#                 qs = qs.filter(commodity_type=selected_commodity)
#             else:
#                 selected_commodity = commodity_types.first() if commodity_types else None
#                 if selected_commodity:
#                     qs = qs.filter(commodity_type=selected_commodity)

#             qs = qs.values('harvest_date', 'total_weight_kg', 'weight_per_unit_kg')

#             forecast_data = None
#             if qs.exists():
#                 df = pd.DataFrame.from_records(qs)
#                 df['ds'] = pd.to_datetime(df['harvest_date'])
#                 df['y'] = df['total_weight_kg'] / df['weight_per_unit_kg']

#                 df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
#                 df['ds'] = df['ds'].dt.to_timestamp()

#                 model = Prophet()
#                 model.fit(df)

#                 future = model.make_future_dataframe(periods=12, freq='M')  # Forecast 12 months
#                 forecast = model.predict(future)

#                 forecast_data = {
#                     'labels': forecast['ds'].dt.strftime('%B %Y').tolist(),
#                     'forecasted_count': forecast['yhat'].round().tolist()
#                 }

#             context = {
#                 'user_firstname': userinfo.firstname,
#                 'forecast_data': forecast_data,
#                 'commodity_types': commodity_types,
#                 'selected_commodity': selected_commodity,
#             }
            
#             return render(request, 'forecasting/forecast.html', context)
        
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('base:home')                
            
#     else :
#         return render(request, 'home.html', {})  



COLORS = [
    'rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)',
    'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)',
    'rgba(153, 102, 255, 0.7)', 'rgba(255, 159, 64, 0.7)'
]
    
def monitor(request):
    print("🔥 DEBUG: monitor view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        userinfo = UserInformation.objects.get(pk=userinfo_id)
        
        if userinfo_id and account_id:
            
            # FOR FILTER
            
            
            selected_month = request.GET.get('month')  # expected format: '2025-04'                
            harvest_records = VerifiedHarvestRecord.objects.all()            
            selected_year = request.GET.get('year')
            
            # if selected_year:
            #     harvest_records = harvest_records.filter(harvest_date__year=selected_year)
            #     print(harvest_records)
            
            available_months = []
            if selected_year:
                months = (
                    VerifiedHarvestRecord.objects
                    .filter(harvest_date__year=selected_year)
                    .annotate(month=ExtractMonth('harvest_date'))
                    .values_list('month', flat=True)
                    .distinct()
                    .order_by('month')
                )
                available_months = [(f"{selected_year}-{str(month).zfill(2)}", calendar.month_name[month]) for month in months]
                
                
            years = (VerifiedHarvestRecord.objects
                .annotate(year=ExtractYear('harvest_date'))  # or your date field
                .values_list('year', flat=True)
                .distinct()
                .order_by('year')
                )
            
            if selected_month:
                # Parse and filter to the selected month
                try:
                    year, month = map(int, selected_month.split('-'))
                    harvest_records = harvest_records.filter(harvest_date__year=year, harvest_date__month=month)
                except:
                    pass  
                
            if selected_year:
                harvest_records = harvest_records.filter(harvest_date__year=selected_year)

            if selected_month:
                try:
                    year, month = map(int, selected_month.split('-'))
                    harvest_records = harvest_records.filter(harvest_date__year=year, harvest_date__month=month)
                except:
                    pass  
            
            
            print(harvest_records)

            # Group and sum by month
            harvest_data = (
                harvest_records
                .annotate(month=TruncMonth('harvest_date'))
                .values('month')
                .annotate(total_weight=Sum('total_weight_kg'))
                .order_by('month')
            )

            # Prepare labels and values FOR Chart.js
            
            labels = [data['month'].strftime('%B %Y') for data in harvest_data]
            weights = [float(data['total_weight']) for data in harvest_data]

            harvest_df = pd.DataFrame(list(harvest_records.values()))
            plant_df = pd.DataFrame(list(VerifiedPlantRecord.objects.values()))

            chart_data = defaultdict(dict)

            if not harvest_df.empty:
                harvest_df['harvest_date'] = pd.to_datetime(harvest_df['harvest_date'])
                harvest_df['month'] = harvest_df['harvest_date'].dt.strftime('%B')

                # Harvest weight per commodity
                hc = harvest_df.groupby('commodity_type')['total_weight_kg'].sum()
                harvest__weights_bycomm_json = [float(weight) for weight in hc.values.tolist()]
                
                chart_data['harvest_commodity'] = {
                    'labels': hc.index.tolist(),
                    'values': harvest__weights_bycomm_json
                }

                # Monthl    y harvest trends
                mh = harvest_df.groupby('month')['total_weight_kg'].sum()
                harvest_weights_json = [float(weight) for weight in mh.values.tolist()]  #converting from decimal to float since di kwan sa javascript
                
                chart_data['monthly_harvest'] = {
                    'labels': mh.index.tolist(),
                    'values': harvest_weights_json
                }

                # Average weight per unit by commodity
                avgw = harvest_df.groupby('commodity_type')['weight_per_unit_kg'].mean()
                harvest_avg_weights_json = [float(weight) for weight in avgw.values.tolist()]
                
                chart_data['avg_weight'] = {
                    'labels': avgw.index.tolist(),
                    'values': harvest_avg_weights_json
                }

                # Harvest count per location
                # locs = harvest_df['harvest_location'].value_counts()
                # chart_data['harvest_location'] = {
                #     'labels': locs.index.tolist(),
                #     'values': locs.values.tolist(),
                #     'colors': random.choices(COLORS, k=len(locs))
                # }
                
                locs = harvest_df.groupby('harvest_municipality')['total_weight_kg'].sum()
                harvest_weight_byloc_json = [float(weight) for weight in locs.values.tolist()]
                chart_data['harvest_municipality'] = {
                    'labels': locs.index.tolist(),
                    'values': harvest_weight_byloc_json,
                    'colors': random.choices(COLORS, k=len(locs))
                }

            if not plant_df.empty:
                plant_df['plant_date'] = pd.to_datetime(plant_df['plant_date'])
                plant_df['month'] = plant_df['plant_date'].dt.strftime('%B')

                # Count per commodity
                pc = plant_df['commodity_type'].value_counts()
                chart_data['plant_commodity'] = {
                    'labels': pc.index.tolist(),
                    'values': pc.values.tolist()
                }

                # Estimated weight per commodity
                ew = plant_df.groupby('commodity_type')['estimated_weight_kg'].sum()
                estimated_weight_json = [float(weight) for weight in ew.values.tolist()]
                chart_data['estimated_weight'] = {
                    'labels': ew.index.tolist(),
                    'values': estimated_weight_json
                }

                # Avg land area per commodity
                la = plant_df.groupby('commodity_type')['land_area'].mean()
                chart_data['avg_land_area'] = {
                    'labels': la.index.tolist(),
                    'values': la.values.tolist()
                }

                # Plantings per month
                pm = plant_df['month'].value_counts()
                plant_weights_json = [float(weight) for weight in pm.values.tolist()]
                
                chart_data['monthly_plantings'] = {
                    'labels': pm.index.tolist(),
                    'values': plant_weights_json
                }
                
                # plant count per location
                pl = plant_df['plant_municipality'].value_counts()
                chart_data['plant_by_location'] = {
                    'labels' : pl.index.tolist(),
                    'values': pl.values.tolist()
                    
                }
                
                print(chart_data['harvest_municipality'])
                
            context = {
                'user_firstname' : userinfo.firstname,
                'chart_data': chart_data,
                'harvest_labels': labels,
                'harvest_weights': weights,
                'selected_month': selected_month or '',
                'years': years,
                'selected_year': selected_year,
                'available_months': available_months,

            }

            return render(request, 'monitoring/overall_dashboard.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')                
            
    else :
        return render(request, 'home.html', {})  


def commoditytype_collect(request):
    harvest_entries = VerifiedHarvestRecord.objects.all()
    plant_entries = VerifiedPlantRecord.objects.all()

    # Create a set for distinct commodity types
    commodity_list = set()

    # Collect commodity types from both harvest and plant records
    commodity_list.update(VerifiedHarvestRecord.objects.values_list('commodity_type', flat=True))
    commodity_list.update(VerifiedPlantRecord.objects.values_list('commodity_type', flat=True))

    # Now let's associate the commodity types with their respective seasons
    commodity_seasons = {}

    for commodity in commodity_list:
        # Get the related months for each commodity (from the CommodityType model)
        commodity_type_instance = CommodityType.objects.filter(name=commodity).first()
        if commodity_type_instance:
            commodity_seasons[commodity] = [month.name for month in commodity_type_instance.seasonal_months.all()]

    print("Commodity Seasons:", commodity_seasons)
    return commodity_seasons




def add_commodity(request):
    if request.method == 'POST':
        form = CommodityTypeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('base:home')     # or anywhere else
    else:
        form = CommodityTypeForm()
    
    return render(request, 'forecasting/commodity_add.html', {'form': form})


# def forecast(request):
#     print("🔥 DEBUG: forecast view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
            
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
            
#             qs = VerifiedHarvestRecord.objects.all().values('harvest_date', 'total_weight_kg', 'weight_per_unit_kg')

#             df = pd.DataFrame.from_records(qs)

#             # Safety check for empty df
#             forecast_data = None
#             if not df.empty:
#                 df['ds'] = pd.to_datetime(df['harvest_date'])
#                 df['y'] = df['total_weight_kg'] / df['weight_per_unit_kg']  # unit count

#                 # Optional: group by month for smoother trends
#                 df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
#                 df['ds'] = df['ds'].dt.to_timestamp()

#                 # Forecasting using Prophet
#                 model = Prophet()
#                 model.fit(df)

#                 future = model.make_future_dataframe(periods=6, freq='M')  # forecast 6 future months
#                 forecast = model.predict(future)

#                 # Only extract what's needed for Chart.js (or your frontend)
#                 forecast_data = {
#                     'labels': forecast['ds'].dt.strftime('%B %Y').tolist(),
#                     'forecasted_count': forecast['yhat'].round().tolist()
#                 }
#                 print('success ')
        
#             context = {
#                 'user_firstname' : userinfo.firstname,
#                 'forecast_data': forecast_data,
#             }            
            
#             return render(request, 'forecasting/forecast.html', context)
        
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('base:home')                
            
#     else :
#         return render(request, 'home.html', {})  