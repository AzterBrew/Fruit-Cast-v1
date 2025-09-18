from celery import shared_task
from django.core.management import call_command
from django.db import transaction
from django.contrib import messages
import os
import pandas as pd
import joblib
from datetime import datetime
from dateutil.relativedelta import relativedelta
from base.models import CommodityType, MunicipalityName, Month
from dashboard.models import ForecastBatch, ForecastResult, VerifiedHarvestRecord # Adjust based on your actual app names
from prophet import Prophet

@shared_task
def retrain_and_generate_forecasts_task():
    """
    Asynchronously retrains Prophet models and generates forecasts.
    This task combines the logic from train_forecastmodel.py and generate_all_forecasts.
    """
    
    # 1. Run the model retraining logic
    try:
        call_command('train_forecastmodel')
        print("Model training completed successfully.")
    except Exception as e:
        print(f"Error during model training: {e}")
        return False # Indicate task failure
    
    # 2. Run the forecast generation logic
    try:
        # Create a single ForecastBatch object to track this generation run.
        # This will be created by a separate process (Celery worker).
        batch = ForecastBatch.objects.create(notes="Bulk generated forecast - All commodities and municipalities for the next 12 months.")

        model_dir = os.path.join(settings.BASE_DIR, 'prophet_models')
        os.makedirs(model_dir, exist_ok=True)
        commodities = CommodityType.objects.exclude(pk=1)
        municipalities = MunicipalityName.objects.exclude(pk=14)
        months = Month.objects.all().order_by('number')
        
        results_created = 0
        
        with transaction.atomic():
            for commodity in commodities:
                for municipality in municipalities:
                    # Determine model filename
                    model_filename = f"prophet_{commodity.commodity_id}_{municipality.municipality_id}.joblib"
                    model_path = os.path.join(model_dir, model_filename)
                    
                    if not os.path.exists(model_path):
                        print(f"Model file not found: {model_path}")
                    else:
                        print(f"Model file found: {model_path}")
                    
                    if not os.path.exists(model_path):
                        continue
                    
                    m = joblib.load(model_path)
                    
                    qs = VerifiedHarvestRecord.objects.filter(
                        commodity_id=commodity,
                        municipality=municipality
                    ).values('harvest_date', 'total_weight_kg').order_by('harvest_date')
                    
                    if not qs.exists():
                        continue
                        
                    df = pd.DataFrame(list(qs))
                    df['ds'] = pd.to_datetime(df['harvest_date'])
                    df['y'] = df['total_weight_kg'].astype(float)
                    df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
                    df['ds'] = df['ds'].dt.to_timestamp()
                    
                    last_historical_date = df['ds'].max()
                    backtest_start_date = last_historical_date - pd.offsets.MonthBegin(12) if len(df) > 12 else df['ds'].min()
                    future_end_date = datetime.today() + relativedelta(months=+12)
                    
                    future_months = pd.date_range(start=backtest_start_date, end=future_end_date, freq='MS')
                    future = pd.DataFrame({'ds': future_months})
                    
                    forecast = m.predict(future)
                    
                    today = datetime.today().replace(day=1)
                    
                    for _, row in forecast.iterrows():
                        forecast_date = row['ds']
                        if forecast_date >= today:
                            forecasted_amount = max(0, row['yhat'])
                            
                            month_num = forecast_date.month
                            year = forecast_date.year
                            
                            try:
                                month_obj = months.get(number=month_num)
                                
                                # Use update_or_create to avoid conflicts
                                ForecastResult.objects.update_or_create(
                                    batch=batch,
                                    commodity=commodity,
                                    forecast_month=month_obj,
                                    forecast_year=year,
                                    municipality=municipality,
                                    defaults={
                                        'forecasted_amount_kg': forecasted_amount,
                                        'notes': f"Generated from Prophet model"
                                    }
                                )
                                results_created += 1
                                
                            except Month.DoesNotExist:
                                continue

        print(f"Successfully generated {results_created} forecast records in batch {batch.batch_id}.")
        return True # Indicate task success

    except Exception as e:
        print(f"Error during forecast generation: {e}")
        return False # Indicate task failure
