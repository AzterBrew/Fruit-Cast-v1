from urllib import request
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.forms import inlineformset_factory
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.db.models import Sum, Avg, Max, Count, Q
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
from django.template.loader import get_template
from weasyprint import HTML, CSS
from django.conf import settings
#from .forms import CustomUserCreationForm  # make sure this is imported
from django.core.files.storage import default_storage
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

    min_notify_time = timezone.now() + timedelta(seconds=3)
    
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
    # Initialize variables for authenticated users
    account_id = None
    userinfo_id = None
    userinfo = None
    
    if request.user.is_authenticated:
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        if userinfo_id:
            userinfo = UserInformation.objects.get(pk=userinfo_id)
    commodity_types = CommodityType.objects.exclude(pk=1)
    all_municipalities = MunicipalityName.objects.exclude(pk=14)
     
    selected_commodity_id = None
    selected_municipality_id = None
    selected_mapcommodity_id = None
 
    if request.GET.get('mapcommodity_id'):
        selected_mapcommodity_id = request.GET.get('mapcommodity_id')
        selected_mapcommodity_obj = CommodityType.objects.get(pk=selected_mapcommodity_id)
        
    else : 
        selected_mapcommodity_id = commodity_types.first().commodity_id if commodity_types.exists() else None
        selected_mapcommodity_obj = CommodityType.objects.get(pk=selected_mapcommodity_id)
        
    
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
    print("Selected map commodity:", selected_mapcommodity_id)

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
        
        # Filter out future outlier dates (anything beyond current date + 1 year)
        current_date = pd.Timestamp.now()
        max_allowed_date = current_date + pd.DateOffset(years=1)
        df = df[df['ds'] <= max_allowed_date]
        print(f"Filtered historical data: {len(df)} records, date range: {df['ds'].min()} to {df['ds'].max()}")

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
            # future_end_date = last_historical_date + pd.offsets.MonthBegin(12)
            future_end_date = datetime.today() + relativedelta(months=+12)

            # Create a 'future' DataFrame that includes the backtesting period
            # and the future forecast period.
            future_months = pd.date_range(start=backtest_start_date, end=future_end_date, freq='MS')
            future = pd.DataFrame({'ds': future_months})
            
            print(f"Future dataframe: {len(future)} rows, date range: {future['ds'].min()} to {future['ds'].max()}")
            
            # Check if future dataframe is empty
            if len(future) == 0:
                forecast_data = None
                print("Error: Future dataframe is empty - cannot generate forecast")
            else:
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
            
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    months =  Month.objects.order_by('number')
    if filter_year and int(filter_year) == current_year:
        months = months.filter(number__gt=now_dt.month)
        
    print(filter_month, filter_year)
    
    # Prepare available years for the dropdown based on ForecastResult
    available_years = list(
        ForecastResult.objects.order_by('forecast_year')
        .values_list('forecast_year', flat=True).distinct()
    )
    if not available_years:
        available_years = [timezone.now().year]
            
    forecast_value_for_selected_month = None
    if forecast_data and filter_month and filter_year:
        for label, value, month_number, year in forecast_data['combined']:
            # label is like "July 2025"
            month_name, year_str = label.split()
            if int(filter_year) == int(year_str) and int(filter_month) == datetime.strptime(month_name, "%b").month:
                forecast_value_for_selected_month = value
                break
    
    
    # CHOROPLETH 2D MAP DATA
    # Use the selected parameters from the form instead of hardcoded values
    map_commodity_id = selected_mapcommodity_id or selected_commodity_id
    map_month = filter_month
    map_year = filter_year
    
    print(f"Map parameters - Commodity: {map_commodity_id}, Month: {map_month}, Year: {map_year}")

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

    # Initialize choropleth data
    choropleth_data = {}

    # Try to get forecast data for the map
    if map_commodity_id and map_month and map_year:
        try:
            # First, try to get data for the selected parameters (no aggregation needed if unique records)
            forecast_results = ForecastResult.objects.filter(
                commodity_id=map_commodity_id,
                forecast_month__number=map_month,
                forecast_year=map_year
            ).exclude(municipality_id=14).select_related('municipality')  # Exclude "Overall" for individual maps
            
            print(f"Map commodity: {selected_mapcommodity_obj}")
            print(f"Forecast results for {map_month}/{map_year}: {forecast_results}")
            
            if forecast_results.exists():
                # Populate the choropleth data - use individual records (should be unique per municipality)
                for result in forecast_results:
                    muni_id = result.municipality_id
                    total_kg = result.forecasted_amount_kg
                    choropleth_data[str(muni_id)] = round(float(total_kg or 0), 2)
            else:
                # If no specific data, try to get "Overall" forecast and distribute it
                overall_forecast = ForecastResult.objects.filter(
                    commodity_id=map_commodity_id,
                    forecast_month__number=map_month,
                    forecast_year=map_year,
                    municipality_id=14  # "Overall" municipality
                ).first()
                
                if overall_forecast:
                    print(f"Using overall forecast: {overall_forecast.forecasted_amount_kg} kg")
                    # Distribute overall forecast among all municipalities equally
                    num_munis = len(muni_id_to_objectids)
                    if num_munis > 0:
                        avg_per_muni = overall_forecast.forecasted_amount_kg / num_munis
                        for muni_id in muni_id_to_objectids.keys():
                            choropleth_data[str(muni_id)] = round(float(avg_per_muni), 2)
                else:
                    print(f"No forecast data available for commodity {map_commodity_id}, {map_month}/{map_year}")
                
        except Exception as e:
            print(f"Error fetching choropleth data: {e}")
            choropleth_data = {}

    print("Choropleth Data:", choropleth_data)  # Debug print
    context = { 
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
        'selected_mapcommodity_obj': selected_mapcommodity_obj,
        'selected_mapcommodity_id': selected_mapcommodity_id,
        'filter_month': filter_month,
        'filter_year': filter_year,
        'available_years': available_years,
        'months': months,
        'choropleth_data' : json.dumps(choropleth_data),
    }
    if request.user.is_authenticated and userinfo:
        context['account_id'] = account_id
        context['user_firstname'] = userinfo.firstname
        
    return render(request, 'forecasting/forecast.html', context)


def forecast_bycommodity(request):
    # Initialize variables for authenticated users
    account_id = None
    userinfo_id = None
    userinfo = None
    
    if request.user.is_authenticated:
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        if userinfo_id:
            userinfo = UserInformation.objects.get(pk=userinfo_id)
    
    # Get filter params
    filter_month = request.GET.get('filter_month') or str(timezone.now().month)
    filter_year = request.GET.get('filter_year') or str(timezone.now().year)
    selected_municipality_id = request.GET.get('municipality_id')
    
    print("Bar graph filters:", filter_month, filter_year, selected_municipality_id)
    
    commodity_types = CommodityType.objects.exclude(pk=1)
    all_municipalities = MunicipalityName.objects.exclude(pk=14)
    months = Month.objects.order_by('number')
    now_dt = datetime.now()
    current_year = now_dt.year
    current_month = now_dt.month
    
    available_years = list(
        ForecastResult.objects.order_by('forecast_year')
        .values_list('forecast_year', flat=True).distinct()
    )
    if not available_years:
        available_years = [timezone.now().year]

    # if filter_year and int(filter_year) == current_year:
    #     months = months.filter(number__gt=current_month)

    months = Month.objects.order_by('number')
    
    forecast_summary = None
    forecast_summary_chart = None

    forecast_qs = ForecastResult.objects.filter(
        forecast_month__number=filter_month,
        forecast_year=filter_year
    )
    if selected_municipality_id != "14":
        forecast_qs = forecast_qs.filter(municipality__municipality_id=selected_municipality_id)
    # Get the latest batch among these results
    latest_batch = forecast_qs.order_by('-batch__generated_at').values_list('batch', flat=True).first()
    if latest_batch:
        forecast_qs = forecast_qs.filter(batch=latest_batch)
    else:
        forecast_qs = ForecastResult.objects.none()

    summary_dict = OrderedDict()
    for commodity in commodity_types:
        total = forecast_qs.filter(commodity=commodity).aggregate(
            total_kg=Sum('forecasted_amount_kg')
        )['total_kg']
        summary_dict[commodity.name] = round(total, 2) if total else 0

    forecast_summary = [
        {'commodity': k, 'forecasted_kg': v} for k, v in summary_dict.items()
    ]
    forecast_summary_chart = {
        'labels': list(summary_dict.keys()),
        'values': list(summary_dict.values())
    } if forecast_summary else None
    print("Forecast results count:", forecast_qs.count())

    context = {
        'user_firstname': userinfo.firstname if userinfo else None,
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
    municipality_name = None
    commodity_id = request.GET.get('commodity_id')
    commodity_name = None
    batch_id = request.GET.get('batch_id')

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
        commodity_name = None
        municipality_name = None
        if commodity_id:
            try:
                commodity = CommodityType.objects.get(pk=commodity_id)
                commodity_name = commodity.name
            except CommodityType.DoesNotExist:
                commodity_name = commodity_id
                
        if municipality_id and municipality_id != "14":
            try:
                municipality = MunicipalityName.objects.get(pk=municipality_id)
                municipality_name = municipality.municipality
            except MunicipalityName.DoesNotExist:
                municipality_name = municipality_id
        else:
            municipality_name = "All of Bataan"
        
        filename = f"forecast-by-month_{commodity_name.lower() or 'all'}_{municipality_name.lower() or 'all'}.csv"
        filename = filename.replace(" ", "-")
        
        writer.writerow(['Commodity:', commodity_name])
        writer.writerow(['Municipality:', municipality_name])
        writer.writerow([])  # blank row
        writer.writerow(['Month & Year', 'Forecasted Amount (kg)'])

        # Write forecast data
        for row in forecast_combined:
            # row: [month_year, forecast_kg, month_num, year]
            month_year, forecast_kg, month_num, year = row
            writer.writerow([month_year, f"{float(forecast_kg):.2f}"])

        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
                
    elif csv_type == 'by_commodity':
        # Download for forecast_bycommodity.html (summary by commodity)
        filter_month = request.GET.get('filter_month')
        filter_year = request.GET.get('filter_year')
        municipality_id = request.GET.get('municipality_id')
        
        response['Content-Disposition'] = 'attachment; filename="forecast_by_commodity.csv"'
        
        if municipality_id and municipality_id != "14":
            try:
                municipality = MunicipalityName.objects.get(pk=municipality_id)
                municipality_name = municipality.municipality
            except MunicipalityName.DoesNotExist:
                municipality_name = municipality_id
        else:
            municipality_name = "All of Bataan"
        
        filename = f"forecast-by-commodity_{municipality_name.lower() or 'all'}_{filter_year}-{filter_month.lower()}.csv"
        filename = filename.replace(" ", "-")
            
        writer.writerow(['Month:', filter_month])
        writer.writerow(['Year:', filter_year])
        writer.writerow(['Municipality:', municipality_name])
        writer.writerow([])  # blank row
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


def forecast_pdf(request):
    commodity_id = request.GET.get('commodity_id')
    municipality_id = request.GET.get('municipality_id')
    forecast_combined_raw = request.GET.get('forecast_combined')
    pdf_type = request.GET.get('pdf_type')
    
    # Initialize filter_month and filter_year for all PDF types
    filter_month = request.GET.get('filter_month')
    filter_year = request.GET.get('filter_year')
    
    if pdf_type == 'by_commodity':
        municipality_name = "All of Bataan"
        if municipality_id and municipality_id != "14":
            try:
                municipality_name = MunicipalityName.objects.get(pk=municipality_id).municipality
            except MunicipalityName.DoesNotExist:
                pass
                
        forecast_summary = []
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
            forecast_summary.append({'commodity': commodity.name, 'forecasted_kg': round(total_kg, 2)})
            
        # Update context and filename for this type of PDF
        context = {
            'forecast_summary': forecast_summary,
            'municipality_name': municipality_name,
            "filter_month": filter_month,
            "filter_year": filter_year,
            'report_title': f"Forecast by Commodity for {municipality_name}"
        }
        filename = f"forecast-by-commodity_{municipality_name.lower()}_{filter_year}-{filter_month}.pdf"
        template_name = 'forecasting/forecast_by_commodity_pdf_template.html'
    else: 
        forecast_combined = []
        if forecast_combined_raw:
            try:
                forecast_combined = json.loads(forecast_combined_raw)
            except Exception as e:
                print("Error decoding forecast_combined for PDF:", e)
                forecast_combined = []

        commodity_name = "Overall"
        if commodity_id:
            try:
                commodity_name = CommodityType.objects.get(pk=commodity_id).name
            except CommodityType.DoesNotExist:
                pass
                
        municipality_name = "All of Bataan"
        if municipality_id and municipality_id != "14":
            try:
                municipality_name = MunicipalityName.objects.get(pk=municipality_id).municipality
            except MunicipalityName.DoesNotExist:
                pass

        # Data to pass to the PDF template
        context = {
            'forecast_data': forecast_combined,
            'report_title': f"Forecast by Month for {commodity_name}",
            'commodity_name': commodity_name,
            "filter_month": filter_month,
            "filter_year": filter_year,
            'municipality_name': municipality_name,
        }
        filename = f"forecast-by-month_{commodity_name.lower() or 'all'}_{municipality_name.lower() or 'all'}.pdf"
        template_name = 'forecasting/forecast_pdf_template.html'

    filename = filename.replace(" ", "-")

    # Render the HTML template for the PDF
    template = get_template(template_name)
    html_content = template.render(context)
    
    # Generate the PDF from the rendered HTML
    pdf = HTML(string=html_content, base_url=request.build_absolute_uri('/')).write_pdf()

    # Create an HttpResponse with the PDF
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response



COLORS = [
    'rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)',
    'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)',
    'rgba(153, 102, 255, 0.7)', 'rgba(255, 159, 64, 0.7)'
]
    
# Helper function to get location names
def get_location_name(model_instance):
    if model_instance.municipality:
        return model_instance.municipality.name
    return "Unknown"

# Helper function for dynamic colors
COLORS = ['#4BC0C0', '#FF6384', '#36A2EB', '#FFCE56', '#9966FF', '#FF9F40', '#007BFF', '#28A745', '#17A2B8', '#DC3545', '#FD7E14']

def monitor(request):
    # Initialize variables for authenticated users
    userinfo_id = None
    userinfo = None
    
    if request.user.is_authenticated:
        userinfo_id = request.session.get('userinfo_id')
        if userinfo_id:
            userinfo = UserInformation.objects.get(pk=userinfo_id)

    # Get available years for the filter
    available_years = VerifiedHarvestRecord.objects.annotate(year=ExtractYear('harvest_date')).values_list('year', flat=True).distinct().order_by('year')
    if not available_years: # Fallback if no harvest data
        available_years = VerifiedPlantRecord.objects.annotate(year=ExtractYear('plant_date')).values_list('year', flat=True).distinct().order_by('year')

    # Get available municipalities for the filter
    municipalities = MunicipalityName.objects.exclude(pk=14).order_by('municipality')

    # Get available commodities for the filter
    commodities = CommodityType.objects.exclude(pk=1).order_by('name')

    # Get filter values from the request
    selected_year = request.GET.get('year')
    selected_municipality = request.GET.get('municipality', 'all')
    selected_commodity = request.GET.get('commodity', 'all')
    selected_municipality_name = 'All Municipalities'

    # Base QuerySets
    harvest_records = VerifiedHarvestRecord.objects.all()
    plant_records = VerifiedPlantRecord.objects.all()

    # Apply year filter to all datasets
    if selected_year and selected_year.isdigit():
        harvest_records = harvest_records.filter(harvest_date__year=selected_year)
        plant_records = plant_records.filter(plant_date__year=selected_year)
    else:
        # Default to the most recent year if no year is selected
        if available_years:
            selected_year = str(available_years.last())
            harvest_records = harvest_records.filter(harvest_date__year=selected_year)
            plant_records = plant_records.filter(plant_date__year=selected_year)

    # Create different filtered datasets for different cards
    
    # For c4-a, c4-b, c4-c, L-a: Apply both municipality AND commodity filters
    harvest_records_muni_commodity_filtered = harvest_records
    plant_records_muni_commodity_filtered = plant_records
    
    if selected_municipality != 'all' and selected_municipality.isdigit():
        harvest_records_muni_commodity_filtered = harvest_records_muni_commodity_filtered.filter(municipality=selected_municipality)
        plant_records_muni_commodity_filtered = plant_records_muni_commodity_filtered.filter(municipality=selected_municipality)
        selected_municipality_name = MunicipalityName.objects.get(pk=selected_municipality).municipality
    
    if selected_commodity != 'all' and selected_commodity.isdigit():
        harvest_records_muni_commodity_filtered = harvest_records_muni_commodity_filtered.filter(commodity_id=selected_commodity)
        plant_records_muni_commodity_filtered = plant_records_muni_commodity_filtered.filter(commodity_id=selected_commodity)
    
    # For b-a: Apply municipality filter only
    harvest_records_muni_only = harvest_records
    if selected_municipality != 'all' and selected_municipality.isdigit():
        harvest_records_muni_only = harvest_records.filter(municipality=selected_municipality)
    
    # For b-b, Li-a: Apply commodity filter only
    harvest_records_commodity_only = harvest_records
    if selected_commodity != 'all' and selected_commodity.isdigit():
        harvest_records_commodity_only = harvest_records.filter(commodity_id=selected_commodity)
    
    # --- KPI Cards (c4-a, c4-b, c4-c) - affected by municipality AND commodity filters ---
    total_plantings = plant_records_muni_commodity_filtered.aggregate(total=Count('id'))['total'] or 0
    total_harvests = harvest_records_muni_commodity_filtered.aggregate(total=Count('id'))['total'] or 0
    most_abundant_fruit = harvest_records_muni_commodity_filtered.values('commodity_id__name').annotate(total_weight=Sum('total_weight_kg')).order_by('-total_weight').first()
    most_abundant_fruit = most_abundant_fruit['commodity_id__name'] if most_abundant_fruit else None
    total_users = AccountsInformation.objects.count()

    # --- L-a: Total Harvested Weight for every month - affected by municipality AND commodity filters ---
    monthly_harvest_data = harvest_records_muni_commodity_filtered.annotate(month=TruncMonth('harvest_date')).values('month').annotate(total_weight=Sum('total_weight_kg')).order_by('month')
    monthly_labels = [data['month'].strftime('%b %Y') for data in monthly_harvest_data]
    monthly_values = [float(data['total_weight']) for data in monthly_harvest_data]
    
    # --- b-a: Total Harvested Weight by Commodity - affected by municipality filter only ---
    harvest_by_commodity = harvest_records_muni_only.values('commodity_id__name').annotate(total_weight=Sum('total_weight_kg')).order_by('commodity_id__name')
    commodity_labels = [data['commodity_id__name'] for data in harvest_by_commodity]
    commodity_values = [float(data['total_weight']) for data in harvest_by_commodity]

    # --- b-b & Li-a: Harvested Weight by Municipality & Top Municipalities - affected by commodity filter only ---
    harvest_by_municipality = harvest_records_commodity_only.values('municipality__municipality').annotate(total_weight=Sum('total_weight_kg')).order_by('-total_weight')
    
    # Fix the top municipalities to show names properly
    top_municipalities = []
    for data in harvest_by_municipality[:5]:
        top_municipalities.append({
            'municipality': data['municipality__municipality'],
            'total_weight': float(data['total_weight'])
        })

    municipality_labels = [data['municipality__municipality'] for data in harvest_by_municipality]
    municipality_values = [float(data['total_weight']) for data in harvest_by_municipality]
    
    # --- Li-b: Commodities List ---
    all_commodities = CommodityType.objects.exclude(pk=1)
    commodities_list = []
    for c in all_commodities:
        # Handle years_to_mature
        mature_info = ""
        if c.years_to_mature:
            years = int(c.years_to_mature)
            months = int((c.years_to_mature - years) * 12)
            
            if years > 0 and months > 0:
                mature_info = f"{years} year{'s' if years > 1 else ''}, {months} month{'s' if months > 1 else ''}"
            elif years > 0:
                mature_info = f"{years} year{'s' if years > 1 else ''}"
            elif months > 0:
                mature_info = f"{months} month{'s' if months > 1 else ''}"
            else:
                mature_info = "Not specified"
        else:
            mature_info = "Not specified"
        
        # Handle years_to_bearfruit
        bearfruit_info = ""
        if c.years_to_bearfruit:
            years = int(c.years_to_bearfruit)
            months = int((c.years_to_bearfruit - years) * 12)
            
            if years > 0 and months > 0:
                bearfruit_info = f"{years} year{'s' if years > 1 else ''}, {months} month{'s' if months > 1 else ''}"
            elif years > 0:
                bearfruit_info = f"{years} year{'s' if years > 1 else ''}"
            elif months > 0:
                bearfruit_info = f"{months} month{'s' if months > 1 else ''}"
            else:
                bearfruit_info = "Not specified"
        else:
            bearfruit_info = "Not specified"
        
        commodities_list.append({
            'name': c.name,
            'mature_info': mature_info,
            'bearfruit_info': bearfruit_info
        })
    
    # Consolidate all data into a single dictionary
    chart_data = {
        'monthly_harvest': {'labels': monthly_labels, 'values': monthly_values},
        'harvest_commodity': {'labels': commodity_labels, 'values': commodity_values},
        'harvest_municipality': {'labels': municipality_labels, 'values': municipality_values},
    }

    context = {
        'chart_data': chart_data,
        'selected_year': selected_year,
        'selected_municipality': selected_municipality,
        'selected_commodity': selected_commodity,
        'selected_municipality_name': selected_municipality_name,
        'available_years': available_years,
        'municipalities': municipalities,
        'commodities': commodities,
        'total_plantings': total_plantings,
        'total_harvests': total_harvests,
        'most_abundant_fruit': most_abundant_fruit,
        'total_users': total_users,
        'top_municipalities': top_municipalities,
        'commodities_list': commodities_list,
    }
    
    if request.user.is_authenticated and userinfo:
        context['user_firstname'] = userinfo.firstname
    
    return render(request, 'monitoring/overall_dashboard.html', context)

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

