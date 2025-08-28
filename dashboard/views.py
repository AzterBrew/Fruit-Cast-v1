from urllib import request
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
from django.db.models import Sum, Avg, Max
from django.http import JsonResponse
from prophet import Prophet
import pandas as pd
import json, joblib,csv, os
from collections import defaultdict, OrderedDict
import random
from django.db.models.functions import TruncMonth, ExtractYear, ExtractMonth
import calendar
from datetime import datetime
from django.utils import timezone
from shapely.geometry import shape
# from dashboard.utils import generate_notifications, get_current_month
from calendar import monthrange
from pathlib import Path

#from .forms import CustomUserCreationForm  # make sure this is imported

from base.models import *
from dashboard.models import *
# from dashboard.forms import CommodityTypeForm

def notifications(request):
    account_id = request.session.get('account_id')
    crops = []

    if account_id:
        plant_records = VerifiedPlantRecord.objects.filter(
            prev_record__transaction_id__account_id=account_id
        ).values_list('commodity_id', flat=True).distinct()
        
        crops = [crop for crop in plant_records if crop]  # Remove nulls or blanks if needed

    # notifications = generate_notifications(crops)

    # return render(request, 'notifications.html', {
    #     'notifications': notifications,
    # })
    return render(request, 'notifications.html')
    

def create_verification_notification(user, record_type):
    message = f"Your {record_type} record has been verified!"
    Notification.objects.create(user=user, message=message)

def schedule_harvest_notification(plant_record):
    commodity = plant_record.commodity_id
    years_to_mature = commodity.years_to_mature or 0
    plant_date = plant_record.plant_date

    # Calculate initial expected harvest date
    expected_harvest_date = plant_date + timedelta(days=float(years_to_mature) * 365.25)

    # Adjust to nearest in-season month (if any)
    in_season_months = list(commodity.seasonal_months.values_list('number', flat=True))
    if in_season_months:
        # Find the next in-season month after expected_harvest_date
        month = expected_harvest_date.month
        year = expected_harvest_date.year
        future_months = sorted([m for m in in_season_months if m >= month])
        if future_months:
            target_month = future_months[0]
        else:
            # If none left this year, pick the first in next year
            target_month = min(in_season_months)
            year += 1
        expected_harvest_date = expected_harvest_date.replace(year=year, month=target_month, day=1)

    # Schedule notification 2 weeks before expected harvest and also kwan 2 mins after bago magnotif
    notify_datetime = datetime.combine(
        expected_harvest_date, datetime.min.time()
    ).replace(hour=8, tzinfo=timezone.get_current_timezone()) - timedelta(days=14)

    min_notify_time = timezone.now() + timedelta(minutes=2)
    if notify_datetime < min_notify_time:
        notify_datetime = min_notify_time

    # Find the user's account
    account = AccountsInformation.objects.filter(userinfo_id=plant_record.transaction.account_id.userinfo_id).first()

    notifications = Notification.objects.filter(
        account=account,
        scheduled_for__lte=timezone.now()
    ).order_by('-created_at')[:10]
    
    redirect_url = reverse('base:transaction_recordlist', args=[plant_record.transaction.transaction_id])
    # Create the notification
    Notification.objects.create(
        account=account,
        message=f"Your planting of {commodity.name} is expected to be ready for harvest around {expected_harvest_date.strftime('%B %Y')}.",
        notification_type="harvest_reminder",
        scheduled_for=notify_datetime,
        linked_plant_record=plant_record,
        redirect_url=redirect_url,  # Optionally, link to the plant record detail page
    )

@require_POST
def mark_notification_read(request):
    notif_id = request.POST.get('notif_id')
    if notif_id and request.user.is_authenticated:
        try:
            notif = Notification.objects.get(pk=notif_id, account__account_id=request.session.get('account_id'))
            notif.is_read = True
            notif.save()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            pass
    return JsonResponse({'success': False}, status=400)


def notifications_view(request):
    account_id = request.session.get('account_id')
    if not account_id:
        return redirect('home')
    notifications = Notification.objects.filter(
        account__account_id=account_id
    ).order_by('-created_at')
    return render(request, 'notifications.html', {'notifications': notifications})
     
     
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
    if not request.user.is_authenticated:
        return render(request, 'home.html', {})

    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    if not (userinfo_id and account_id):
        return redirect('home')

    userinfo = UserInformation.objects.get(pk=userinfo_id)
    commodity_types = CommodityType.objects.exclude(pk=1)
    all_municipalities = MunicipalityName.objects.exclude(pk=14)
    
    selected_commodity_id = request.GET.get('commodity_id')
    selected_municipality_id = request.GET.get('municipality_id')
    selected_commodity_obj = None
    selected_municipality_obj = None

    if selected_commodity_id:
        try:
            selected_commodity_obj = CommodityType.objects.get(pk=selected_commodity_id)
        except CommodityType.DoesNotExist:
            selected_commodity_obj = None
    else:
        selected_commodity_obj = commodity_types.first()
        selected_commodity_id = selected_commodity_obj.commodity_id if selected_commodity_obj else None

    if selected_municipality_id:
        try:
            selected_municipality_obj = MunicipalityName.objects.get(pk=selected_municipality_id)
        except MunicipalityName.DoesNotExist:
            selected_municipality_obj = None
    else:
        selected_municipality_obj = all_municipalities.first()
        selected_municipality_id = selected_municipality_obj.municipality_id if selected_municipality_obj else None

    filter_month = request.GET.get('filter_month')
    filter_year = request.GET.get('filter_year')
    
    forecast_data = None
    if selected_commodity_id and selected_municipality_id:
        model_path = Path('prophet_models') / f'prophet_{selected_commodity_id}_{selected_municipality_id}.joblib'
        if model_path.exists():
            model = joblib.load(model_path)
            # Get historical data for chart
            qs = VerifiedHarvestRecord.objects.filter(
                commodity_id=selected_commodity_id,
                municipality_id=selected_municipality_id
            ).values('harvest_date', 'total_weight_kg').order_by('harvest_date')
            df = pd.DataFrame(list(qs))
            if not df.empty:
                df['ds'] = pd.to_datetime(df['harvest_date'])
                df['y'] = df['total_weight_kg'].astype(float)
                df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
                df['ds'] = df['ds'].dt.to_timestamp()
                hist_labels = df['ds'].dt.strftime('%b %Y').tolist()
                hist_values = df['y'].tolist()
            else:
                hist_labels, hist_values = [], []

            # Forecast for next 12 months
            future = model.make_future_dataframe(periods=12, freq='M')
            forecast = model.predict(future)
            # Only show forecasted months (not overlapping with history)
            last_hist_date = df['ds'].max() if not df.empty else None
            forecast_df = forecast[forecast['ds'] > last_hist_date] if last_hist_date is not None else forecast
            forecast_labels = forecast_df['ds'].dt.strftime('%b %Y').tolist()
            forecast_values = forecast_df['yhat'].clip(lower=0).round(2).tolist()

            # Combine for chart
            forecast_data = {
                'hist_labels': hist_labels,
                'hist_values': hist_values,
                'forecast_labels': forecast_labels,
                'forecast_values': forecast_values,
                'labels': hist_labels + forecast_labels,
                'forecasted_count': hist_values + forecast_values,
            }

    now_dt = datetime.now()
    current_year = now_dt.year
    available_years = [current_year, current_year + 1]
    months = Month.objects.order_by('number')
    # print(latest_batch)
    
    
    # CHOROPLETH 2D MAP TEST DATA
    # Set commodity_pk=4, month_pk=9 (September), year=2025
    commodity_pk = 4
    month_pk = 9
    year = 2025
    
    

    geojson_path = os.path.join('static', 'geojson', 'BATAAN_MUNICIPALITY.geojson')
    with open(geojson_path, encoding='utf-8') as f:
        geojson_data = json.load(f)

    # Build mapping: GeoJSON name -> list of OBJECTIDs
    geojson_name_to_objectids = {}
    for feature in geojson_data['features']:
        name = feature['properties']['MUNICIPALI'].strip().upper()
        objectid = feature['properties']['OBJECTID']
        geojson_name_to_objectids.setdefault(name, []).append(objectid)

    # Build mapping: MunicipalityName ID -> list of OBJECTIDs
    muni_id_to_objectids = {}
    for muni in MunicipalityName.objects.all():
        name_key = muni.municipality.strip().upper()
        objectids = geojson_name_to_objectids.get(name_key, [])
        muni_id_to_objectids[muni.municipality_id] = objectids

    # Build choropleth data: OBJECTID -> value
    
    # initial with predefined values
    # choropleth_data = {}
    # for muni_id, value in test_values.items():
    #     for objectid in muni_id_to_objectids.get(muni_id, []):
    #         choropleth_data[objectid] = value
    
    
    # # OLD WORKING 2D MAP RETRIEVING DATA FROM FORECASTRESULT MODEL
    # choropleth_data = {}
    
    # if filter_month and filter_year and selected_commodity_id:
    #     results = ForecastResult.objects.filter(
    #         commodity_id=selected_commodity_id,
    #         forecast_month__number=filter_month,
    #         forecast_year=filter_year
    #     ).values('municipality__municipality_id').annotate(
    #         forecasted_kg=Sum('forecasted_amount_kg')
    #     )
        
    #     for res in results:
    #         choropleth_data[str(res['municipality__municipality_id'])] = round(float(res['forecasted_kg'] or 0),2)

    choropleth_data = []
    if selected_commodity_id and filter_month and filter_year:
        for muni in MunicipalityName.objects.exclude(pk=14):
            model_path = Path('prophet_models') / f'prophet_{selected_commodity_id}_{muni.municipality_id}.joblib'
            if not model_path.exists():
                continue
            model = joblib.load(model_path)
            # Generate enough future months to cover the requested date
            # Find the last date in the training data
            qs = VerifiedHarvestRecord.objects.filter(
                commodity_id=selected_commodity_id,
                municipality_id=muni.municipality_id
            ).values('harvest_date').order_by('harvest_date')
            if not qs.exists():
                continue
            last_hist_date = pd.to_datetime(qs.last()['harvest_date'])
            # Calculate how many months ahead the target date is
            target_date = pd.Timestamp(year=int(filter_year), month=int(filter_month), day=1)
            months_ahead = (target_date.year - last_hist_date.year) * 12 + (target_date.month - last_hist_date.month)
            if months_ahead < 1:
                months_ahead = 1
            # Generate future dataframe
            future = model.make_future_dataframe(periods=months_ahead, freq='M')
            forecast = model.predict(future)
            # Find the forecast for the selected month/year
            forecast['month'] = forecast['ds'].dt.month
            forecast['year'] = forecast['ds'].dt.year
            row = forecast[(forecast['month'] == int(filter_month)) & (forecast['year'] == int(filter_year))]
            if not row.empty:
                forecasted_kg = max(row.iloc[0]['yhat'], 0)  # Clip negative values
            else:
                forecasted_kg = 0
            choropleth_data.append({
                'municipality_id': muni.municipality_id,
                'municipality': muni.municipality,
                'forecasted_kg': forecasted_kg
            })
    
    else :
        choropleth_data = {
        1: 0,   # Abucay
        2: 0,    # Bagac
        3: 0,   # Balanga City
        4: 0,   # Dinalupihan
        5: 0,    # Hermosa
        6: 0,   # Limay
        7: 0,   # Mariveles
        8: 0,    # Morong
        9: 0,    # Orani
        11: 0,  # Orion
        12: 0,   # Pilar
        13: 0    # Samal
    }
        # for row in results:
        #     choropleth_data[str(row['municipality__municipality_id'])] = float(row['forecasted_kg'] or 0)
        #     print(f"Municipality ID: {row['municipality__municipality_id']}, Forecasted KG: {row['forecasted_kg']}")

    print("Choropleth Data:", choropleth_data)  # Debug print
    context = { 
        'user_firstname': userinfo.firstname,
        'forecast_data': forecast_data,
        'forecast_combined_json': json.dumps(forecast_data['combined']) if forecast_data else '[]',
        # 'forecast_summary': forecast_summary,
        # 'forecast_summary_chart': forecast_summary_chart if filter_month and filter_year else None,
        'commodity_types': commodity_types,
        'municipalities': all_municipalities,
        'selected_commodity_obj': selected_commodity_obj,
        'selected_commodity_id': selected_commodity_id,
        'selected_municipality_obj': selected_municipality_obj,
        'selected_municipality': selected_municipality_id,
        'filter_month': filter_month,
        'filter_year': filter_year,
        'available_years': available_years,
        'months': months,
        'choropleth_data' : choropleth_data
    }
    return render(request, 'forecasting/forecast.html', context)


def forecast_bycommodity(request):
    # Get filter params
    filter_month = request.GET.get('filter_month')
    filter_year = request.GET.get('filter_year')
    selected_municipality_id = request.GET.get('municipality_id')

    commodity_types = CommodityType.objects.exclude(pk=1)
    all_municipalities = MunicipalityName.objects.exclude(pk=14)
    months = Month.objects.order_by('number')
    now_dt = datetime.now()
    current_year = now_dt.year
    current_month = now_dt.month
    available_years = [current_year, current_year + 1]

    if filter_year and int(filter_year) == current_year:
        months = months.filter(number__gt=current_month)

    forecast_summary = None
    forecast_summary_chart = None

    if filter_month and filter_year:
        filter_month = int(filter_month)
        filter_year = int(filter_year)
        forecast_qs = ForecastResult.objects.filter(
            forecast_month__number=filter_month,
            forecast_year=filter_year
        )
        if selected_municipality_id and selected_municipality_id != "14":
            forecast_qs = forecast_qs.filter(municipality__municipality_id=selected_municipality_id)
        summary_dict = OrderedDict()
        for commodity in commodity_types:
            total = forecast_qs.filter(commodity=commodity).aggregate(
                total_kg=Sum('forecasted_amount_kg')
            )['total_kg']
            if total is not None:
                total_kg = round(total, 2)
            else:
                total_kg = 0
            summary_dict[commodity.name] = total_kg
        forecast_summary = [
            {'commodity': k, 'forecasted_kg': v} for k, v in summary_dict.items()
        ]
        forecast_summary_chart = {
            'labels': list(summary_dict.keys()),
            'values': list(summary_dict.values())
        }

    context = {
        'commodity_types': commodity_types,
        'all_municipalities': all_municipalities,
        'months': months,
        'available_years': available_years,
        'filter_month': filter_month,
        'filter_year': filter_year,
        'forecast_summary': forecast_summary,
        'forecast_summary_chart': forecast_summary_chart,
        'selected_municipality': selected_municipality_id,
    }
    return render(request, 'forecasting/forecast_bycommodity.html', context)


def forecast_csv(request):
    csv_type = request.GET.get('csv_type')
    response = HttpResponse(content_type='text/csv')
    writer = csv.writer(response)
    municipality_id = request.GET.get('municipality_id')
    commodity_id = request.GET.get('commodity_id')
    commodity_name = None
    batch_id = request.GET.get('batch_id')
    
    if commodity_id:
        try:
            commodity = CommodityType.objects.get(pk=commodity_id)
            commodity_name = commodity.name
        except CommodityType.DoesNotExist:
            commodity_name = None

    forecast_combined_raw = request.GET.get('forecast_combined')
    print("forecast_combined_raw:", forecast_combined_raw)  # Debug print

    forecast_combined = []
    if forecast_combined_raw:
        if isinstance(forecast_combined_raw, str):
            try:
                forecast_combined = json.loads(forecast_combined_raw)
            except Exception as e:
                print("Error decoding forecast_combined:", e)
                forecast_combined = []
        elif isinstance(forecast_combined_raw, list):
            forecast_combined = forecast_combined_raw

    print("csv_type:", csv_type)
    print("municipality_id:", municipality_id)
    print("commodity_id:", commodity_id)
    print("forecast_combined:", forecast_combined)
    
    
    if csv_type == 'by_month':
        if municipality_id == "14":
            # Parse the JSON string to get the data
            # combined = json.loads(forecast_combined)
            writer.writerow(['Commodity Type','Municipality','Month/Year', 'Forecasted Amount (kg)'])
            for month_year, forecast_kg in forecast_combined:
                writer.writerow([commodity_name, "All of Bataan", month_year, f"{float(forecast_kg):.2f}"])
            response['Content-Disposition'] = 'attachment; filename="overall_forecast.csv"'
            return response
        
        else : 
            if batch_id is not None and batch_id != "None":
                # Download for forecast.html (by month, by batch or filters)
                batch_id = request.GET.get('batch_id')
                commodity_id = request.GET.get('commodity_id')
                municipality_id = request.GET.get('municipality_id')
                # You may want to filter by batch_id if you use batches
                results = ForecastResult.objects.filter(
                    batch_id=batch_id,
                    commodity_id=commodity_id
                )
                if municipality_id and municipality_id != "14":
                    results = results.filter(municipality_id=municipality_id)
                results = results.order_by('forecast_year', 'forecast_month__number')
                response['Content-Disposition'] = 'attachment; filename="forecast_by_month.csv"'
                writer.writerow(['Commodity', 'Municipality', 'Month & Year', 'Forecasted Amount (kg)', 'Forecasted Count (units)'])
                for r in results:
                    writer.writerow([
                        r.commodity.name,
                        r.municipality.municipality,
                        f"{r.forecast_month.name} {r.forecast_year}",
                        round(r.forecasted_amount_kg,2) or 0,
                        r.forecasted_count_units
                    ])
                
    elif csv_type == 'by_commodity':
        # Download for forecast_bycommodity.html (summary by commodity)
        filter_month = request.GET.get('filter_month')
        filter_year = request.GET.get('filter_year')
        municipality_id = request.GET.get('municipality_id')
        response['Content-Disposition'] = 'attachment; filename="forecast_by_commodity.csv"'
        writer.writerow(['Commodity', 'Forecasted Amount (kg)'])
        commodities = CommodityType.objects.exclude(pk=1)
        for commodity in commodities:
            qs = ForecastResult.objects.filter(
                commodity_id=commodity.commodity_id,
                forecast_month__number=filter_month,
                forecast_year=filter_year
            )
            if municipality_id and municipality_id != "14":
                qs = qs.filter(municipality_id=municipality_id)
            agg = qs.aggregate(total=Sum('forecasted_amount_kg'))
            total_kg = agg['total'] if agg['total'] is not None else 0
            writer.writerow([commodity.name, round(total_kg, 2)])
    else:
        response['Content-Disposition'] = 'attachment; filename="forecast.csv"'
        writer.writerow(['No data'])
    return response






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

            harvest_df = pd.DataFrame(list(VerifiedHarvestRecord.objects.values('id', 'harvest_date', 'total_weight_kg', 'weight_per_unit_kg', 'commodity_id','municipality', 'barangay')))
            plant_df = pd.DataFrame(list(VerifiedPlantRecord.objects.values('id', 'plant_date', 'commodity_id', 'min_expected_harvest', 'max_expected_harvest','average_harvest_units', 'estimated_weight_kg', 'remarks', 'municipality', 'barangay')))
            
            
            chart_data = defaultdict(dict)

            if not harvest_df.empty and 'commodity_id' in harvest_df.columns:
                harvest_df['harvest_date'] = pd.to_datetime(harvest_df['harvest_date'])
                harvest_df['month'] = harvest_df['harvest_date'].dt.strftime('%B')
                
                record_ids = harvest_df['id'].tolist()
                records = VerifiedHarvestRecord.objects.in_bulk(record_ids)
                harvest_df['harvest_municipality'] = [get_verified_record_location(records[rid])[0] if rid in records else None for rid in record_ids]
                
                # Harvest weight per commodity
                hc = harvest_df.groupby('commodity_id')['total_weight_kg'].sum()
                harvest_weights_bycomm_json = [float(weight) for weight in hc.values.tolist()]
                harvest_commodity_ids = list(hc.index)
                harvest_commodity_names = [CommodityType.objects.get(pk=cid).name for cid in harvest_commodity_ids]
                chart_data['harvest_commodity'] = {
                    'labels': harvest_commodity_names,
                    'values': harvest_weights_bycomm_json
                }

                # Monthly harvest trends
                mh = harvest_df.groupby('month')['total_weight_kg'].sum()
                harvest_weights_json = [float(weight) for weight in mh.values.tolist()]  #converting from decimal to float since di kwan sa javascript
                
                chart_data['monthly_harvest'] = {
                    'labels': mh.index.tolist(),
                    'values': harvest_weights_json
                }

                # Average weight per unit by commodity
                avgw = harvest_df.groupby('commodity_id')['weight_per_unit_kg'].mean()
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

            if not plant_df.empty and 'commodity_id' in plant_df.columns:
                plant_df['plant_date'] = pd.to_datetime(plant_df['plant_date'])
                plant_df['month'] = plant_df['plant_date'].dt.strftime('%B')
                
                record_ids = plant_df['id'].tolist()
                records = VerifiedPlantRecord.objects.in_bulk(record_ids)
                plant_df['plant_municipality'] = [get_verified_record_location(records[rid])[0] if rid in records else None for rid in record_ids]

                # Count per commodity
                pc = plant_df['commodity_id'].value_counts()
                plant_commodity_ids = pc.index.tolist()
                plant_commodity_names = [CommodityType.objects.get(pk=cid).name for cid in plant_commodity_ids]
                chart_data['plant_commodity'] = {
                    'labels': plant_commodity_names,
                    'values': pc.values.tolist()
                }

                # Estimated weight per commodity
                ew = plant_df.groupby('commodity_id')['estimated_weight_kg'].sum()
                ew_ids = ew.index.tolist()
                ew_names = [CommodityType.objects.get(pk=cid).name for cid in ew_ids]
                estimated_weight_json = [float(weight) for weight in ew.values.tolist()]
                chart_data['estimated_weight'] = {
                    'labels': ew_names,
                    'values': estimated_weight_json
                }

                # Avg land area per commodity
                if 'land_area' in plant_df.columns:
                    la = plant_df.groupby('commodity_id')['land_area'].mean()
                    la_ids = la.index.tolist()
                    la_names = [CommodityType.objects.get(pk=cid).name for cid in la_ids]
                    chart_data['avg_land_area'] = {
                        'labels': la_names,
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
                
                # print(chart_data['estimated_weight'])
                
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
            return redirect('home')                
            
    else :
        return render(request, 'home.html', {})  


def get_verified_record_location(record):
    # record: VerifiedHarvestRecord or VerifiedPlantRecord
    if record.municipality and record.barangay:
        # Admin-uploaded
        return record.municipality.municipality, record.barangay.barangay
    elif record.prev_record:
        transaction = record.prev_record.transaction
        if transaction.location_type == 'manual':
            muni = transaction.manual_municipality.municipality if transaction.manual_municipality else None
            brgy = transaction.manual_barangay.barangay if transaction.manual_barangay else None
        elif transaction.location_type == 'farm_land' and transaction.farm_land:
            muni = transaction.farm_land.municipality.municipality
            brgy = transaction.farm_land.barangay.barangay
        else:
            muni = brgy = None
        return muni, brgy
    else:
        return None, None


def commoditytype_collect(request):
    harvest_entries = VerifiedHarvestRecord.objects.all()
    plant_entries = VerifiedPlantRecord.objects.all()

    # Create a set for distinct commodity types
    commodity_list = set()

    # Collect commodity types from both harvest and plant records
    commodity_list.update(VerifiedHarvestRecord.objects.values_list('commodity_id', flat=True))
    commodity_list.update(VerifiedPlantRecord.objects.values_list('commodity_id', flat=True))

    # Now let's associate the commodity types with their respective seasons
    commodity_seasons = {}

    for commodity in commodity_list:
        # Get the related months for each commodity (from the CommodityType model)
        commodity_type_instance = CommodityType.objects.filter(name=commodity).first()
        if commodity_type_instance:
            commodity_seasons[commodity] = [month.name for month in commodity_type_instance.seasonal_months.all()]

    print("Commodity Seasons:", commodity_seasons)
    return commodity_seasons




# def add_commodity(request):
    # THIS IS FOR ADDING COMMODITY TYPES BY ADMIN IN ADMIN PANEL, RETURN HERE PLS
    # if request.method == 'POST':
    #     form = CommodityTypeForm(request.POST)
    #     if form.is_valid():
    #         form.save()
    #         return redirect('base:home')     # or anywhere else
    # else:
    #     form = CommodityTypeForm()
    
    # return render(request, 'forecasting/commodity_add.html', {'form': form})


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



# def forecast(request):
#     if not request.user.is_authenticated:
#         return render(request, 'home.html', {})

#     account_id = request.session.get('account_id')
#     userinfo_id = request.session.get('userinfo_id')
#     if not (userinfo_id and account_id):
#         return redirect('home')

#     userinfo = UserInformation.objects.get(pk=userinfo_id)
#     commodity_types = CommodityType.objects.exclude(pk=1)
#     all_municipalities = MunicipalityName.objects.exclude(pk=14)

#     selected_commodity_id = request.GET.get('commodity_id')
#     selected_municipality_id = request.GET.get('municipality_id')
#     selected_commodity_obj = None
#     selected_municipality_obj = None
#     filter_month = request.GET.get('filter_month')
#     filter_year = request.GET.get('filter_year')
    
#     if selected_commodity_id == "1":
#         selected_commodity_obj = None
#         selected_commodity_id = None
#     elif selected_commodity_id:
#         try:
#             selected_commodity_obj = CommodityType.objects.get(pk=selected_commodity_id)
#         except CommodityType.DoesNotExist:
#             selected_commodity_obj = None
#     else:
#         selected_commodity_obj = commodity_types.first()
#         selected_commodity_id = selected_commodity_obj.commodity_id if selected_commodity_obj else None

#     if selected_municipality_id:
#         try:
#             selected_municipality_obj = MunicipalityName.objects.get(pk=selected_municipality_id)
#         except MunicipalityName.DoesNotExist:
#             selected_municipality_obj = None
    
    
#     # Only show municipalities with at least 2 months of data for the selected commodity
#     municipality_qs = VerifiedHarvestRecord.objects.filter(commodity_id=selected_commodity_id)
#     municipality_months = {}
#     for muni_id in all_municipalities.values_list('municipality_id', flat=True):
#         muni_records = municipality_qs.filter(municipality_id=muni_id)
#         months = muni_records.values_list('harvest_date', flat=True)
#         month_set = set((d.year, d.month) for d in months if d)
#         if len(month_set) >= 2:
#             municipality_months[muni_id] = True

#     municipalities = all_municipalities.filter(municipality_id__in=municipality_months.keys())

#     # Get in-season months for the selected commodity
#     in_season_months = set()
#     if selected_commodity_obj:
#         in_season_months = set(m.number for m in selected_commodity_obj.seasonal_months.all())

#     # Filter by commodity and municipality
#     qs = VerifiedHarvestRecord.objects.filter(commodity_id=selected_commodity_id)
#     if selected_municipality_id:
#         qs = qs.filter(municipality_id=selected_municipality_id)
#     qs = qs.values('harvest_date', 'total_weight_kg', 'weight_per_unit_kg', 'commodity_id', 'prev_record')

#     forecast_data = None
#     map_data = []

#     if qs.exists():
#         df = pd.DataFrame.from_records(qs)
#         df['ds'] = pd.to_datetime(df['harvest_date'])
#         df['y'] = df['total_weight_kg'].astype(float)

#         # Group by month for Prophet
#         df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
#         df['ds'] = df['ds'].dt.to_timestamp()

#         # Remove outliers
#         if len(df) >= 4:
#             q_low = df['y'].quantile(0.05)
#             q_high = df['y'].quantile(0.95)
#             df = df[(df['y'] >= q_low) & (df['y'] <= q_high)]

#         # Optional: smooth data
#         df['y'] = df['y'].rolling(window=2, min_periods=1).mean()

#         if len(df) >= 2:
#             model = Prophet(
#                 yearly_seasonality=True,
#                 changepoint_prior_scale=0.05,
#                 seasonality_prior_scale=1
#             )
#             model.fit(df[['ds', 'y']])
#             future = model.make_future_dataframe(periods=12, freq='M')
#             forecast_df = model.predict(future)

#             # Apply seasonal boost to in-season months
#             boost_factor = 1.2
#             forecast_df['month_num'] = forecast_df['ds'].dt.month
#             forecast_df['yhat_boosted'] = forecast_df.apply(
#                 lambda row: row['yhat'] * boost_factor if row['month_num'] in in_season_months else row['yhat'],
#                 axis=1
#             )
#             forecast_df['yhat_boosted'] = forecast_df['yhat_boosted'].clip(lower=0)

#             labels = forecast_df['ds'].dt.strftime('%B %Y').tolist()
#             values = forecast_df['yhat_boosted'].round().tolist()
#             combined_forecast = list(zip(labels, values))

#             forecast_data = {
#                 'labels': labels,
#                 'forecasted_count': values,
#                 'combined': combined_forecast
#             }
#         else:
#             forecast_data = None

        
#         #  Table for grouped by commodity, separate forecast / Forecast summary
        
#         filter_month = request.GET.get('filter_month')
#         filter_year = request.GET.get('filter_year')
        
#         now = datetime.now()
#         current_year = now.year
#         current_month = now.month
#         months =  Month.objects.order_by('number')
#         if filter_year and int(filter_year) == current_year:
#             months = months.filter(number__gt=current_month)

#         # Prepare available years for the dropdown
#         current_year = datetime.now().year
#         available_years = [current_year, current_year + 1]
#         if not available_years:
#             available_years = [timezone.now().year]

#         # Prepare forecast summary per commodity for the selected month/year
#         forecast_summary = []
#         if filter_month and filter_year:
#             filter_month = int(filter_month)
#             filter_year = int(filter_year)
#             # For each commodity, get forecast for the selected month/year
#             for commodity in commodity_types:
#                 qs_for_sum = VerifiedHarvestRecord.objects.filter(commodity_id=commodity.commodity_id)
#                 if selected_municipality_id:
#                     qs_for_sum = qs_for_sum.filter(municipality_id=selected_municipality_id)
#                 qs_for_sum = qs_for_sum.values('harvest_date', 'total_weight_kg')
#                 if qs_for_sum.exists():
#                     df = pd.DataFrame.from_records(qs_for_sum)
#                     df['ds'] = pd.to_datetime(df['harvest_date'])
#                     df['y'] = df['total_weight_kg'].astype(float)
#                     df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
#                     df['ds'] = df['ds'].dt.to_timestamp()
#                     if len(df) >= 2:
#                         model = Prophet(yearly_seasonality=True, changepoint_prior_scale=0.05, seasonality_prior_scale=1)
#                         model.fit(df[['ds', 'y']])
#                         # Forecast for the selected month/year
#                         last_day = monthrange(filter_year, filter_month)[1]
#                         forecast_date = datetime(filter_year, filter_month, last_day)
#                         future = pd.DataFrame({'ds': [forecast_date]})
#                         forecast = model.predict(future)
#                         forecasted_kg = max(0, round(forecast['yhat'].iloc[0]))
#                     else:
#                         forecasted_kg = None
#                 else:
#                     forecasted_kg = None
#                 forecast_summary.append({
#                     'commodity': commodity.name,
#                     'forecasted_kg': forecasted_kg
#                 })
#         else:
#             forecast_summary = None
        
#         # --- 2D Mapping (unchanged, but you can filter map_data if you want) ---
#         with open('static/geojson/BATAAN_MUNICIPALITY.geojson', 'r') as f:
#             geojson_data = json.load(f)

#         prev_to_municipality = {}
#         for rec in qs:
#             prev_id = rec['prev_record']
#             if prev_id:
#                 try:
#                     prev = initHarvestRecord.objects.get(pk=prev_id)
#                     if prev.transaction and prev.transaction.location_type == 'farm_land' and prev.transaction.farm_land:
#                         municipality = prev.transaction.farm_land.municipality.municipality
#                         prev_to_municipality[prev_id] = municipality
#                 except Exception:
#                     continue

#         df_full = pd.DataFrame.from_records(qs)
#         df_full['municipality'] = df_full['prev_record'].map(prev_to_municipality)
#         muni_group = df_full.groupby('municipality')['total_weight_kg'].sum().to_dict()

#         for feature in geojson_data['features']:
#             properties = feature.get('properties', {})
#             municipality = properties.get('MUNICIPALI') or properties.get('NAME_2')
#             geom = shape(feature['geometry'])
#             centroid = geom.centroid
#             latitude = centroid.y
#             longitude = centroid.x
#             forecasted_amount = muni_group.get(municipality, 0)
#             map_data.append({
#                 'latitude': latitude,
#                 'longitude': longitude,
#                 'barangay': None,
#                 'municipality': municipality,
#                 'province': properties.get('PROVINCE', None),
#                 'forecasted_amount': float(forecasted_amount)
#             })

#     context = {
#         'user_firstname': userinfo.firstname,
#         'forecast_data': forecast_data,
#         'commodity_types': commodity_types,
#         'municipalities': municipalities,
#         'selected_commodity': selected_commodity_id,
#         'selected_municipality': selected_municipality_id,
#         'map_data': map_data,
#         'selected_commodity_obj': selected_commodity_obj,
#         'selected_commodity_id': selected_commodity_id,
#         'selected_municipality_obj': selected_municipality_obj,
#         'forecast_summary': forecast_summary,
#         'filter_month': filter_month,
#         'filter_year': filter_year,
#         'available_years': available_years,
#         'months': months
#     }
#     return render(request, 'forecasting/forecast.html', context)