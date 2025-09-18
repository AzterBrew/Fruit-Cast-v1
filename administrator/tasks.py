from celery import shared_task
from django.conf import settings
from django.db import transaction
import os, joblib
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from base.models import CommodityType, MunicipalityName, Month
from dashboard.models import ForecastBatch, ForecastResult, VerifiedHarvestRecord
from prophet import Prophet
from django.core.files.storage import default_storage
from io import BytesIO

@shared_task
def retrain_and_generate_forecasts_task():
    """
    Asynchronously trains Prophet models in memory and generates forecasts,
    saving the results to the database.
    """
    try:
        print(f"DEBUG: AWS_STORAGE_BUCKET_NAME is {os.environ.get('AWS_STORAGE_BUCKET_NAME')}")
        print(f"DEBUG: AWS_S3_ENDPOINT_URL is {os.environ.get('AWS_S3_ENDPOINT_URL')}")
        
        # Create a single ForecastBatch object to track this generation run.
        batch = ForecastBatch.objects.create(notes="Bulk generated forecast - All commodities and municipalities.")
        
        municipalities = MunicipalityName.objects.exclude(pk=14)
        commodities = CommodityType.objects.exclude(pk=1)
        months = Month.objects.all().order_by('number')
        
        print("Starting model training and forecast generation...")
        
        results_created = 0
        
        # We need to get all historical data once, for both individual and overall models
        all_records_qs = VerifiedHarvestRecord.objects.filter(
            commodity_id__in=commodities,
            municipality__in=municipalities
        ).values('harvest_date', 'total_weight_kg', 'commodity_id', 'municipality_id').order_by('harvest_date')
        
        all_records_df = pd.DataFrame(list(all_records_qs))
        
        # Directory to save models (optional but good practice to keep them)
        # model_dir = os.path.join(settings.BASE_DIR, 'prophet_models')
        # os.makedirs(model_dir, exist_ok=True)
        
        with transaction.atomic():
            # Process each individual municipality and commodity
            for muni in municipalities:
                for comm in commodities:
                    # Filter the main DataFrame for the specific combination
                    df = all_records_df[
                        (all_records_df['municipality_id'] == muni.pk) & 
                        (all_records_df['commodity_id'] == comm.pk)
                    ].copy()
                    
                    if len(df) < 2:
                        print(f"Skipping {comm.name} - {muni.municipality}: not enough data.")
                        continue
                    
                    # Group and clean the data for Prophet
                    df['ds'] = pd.to_datetime(df['harvest_date'])
                    df['y'] = df['total_weight_kg'].astype(float)
                    df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
                    df['ds'] = df['ds'].dt.to_timestamp()
                    
                    if len(df) >= 4:
                        q_low = df['y'].quantile(0.05)
                        q_high = df['y'].quantile(0.95)
                        df = df[(df['y'] >= q_low) & (df['y'] <= q_high)]
                    df['y'] = df['y'].rolling(window=2, min_periods=1).mean()
                    
                    if df['y'].notna().sum() < 2:
                        print(f"Skipping {comm.name} - {muni.municipality}: not enough data after cleaning.")
                        continue
                        
                    # Train model
                    m = Prophet(yearly_seasonality=True, changepoint_prior_scale=0.05, seasonality_prior_scale=1, daily_seasonality=False, weekly_seasonality=False)
                    m.fit(df[['ds', 'y']])
                    
                    # Save the trained model to disk
                    model_filename = f"prophet_{comm.commodity_id}_{muni.municipality_id}.joblib"
                    
                    bucket_path = f"prophet_models/{model_filename}"

                    # Create an in-memory buffer to hold the model file
                    buffer = BytesIO()
                    joblib.dump(m, buffer)

                    # Rewind the buffer to the beginning before saving
                    buffer.seek(0)

                    # Save the model directly to DigitalOcean Spaces
                    default_storage.save(bucket_path, buffer)
                    
                    # Generate forecast
                    future = m.make_future_dataframe(periods=12, freq='MS') # Changed to 'MS' for month start
                    forecast = m.predict(future)
                    
                    today = datetime.today().replace(day=1)
                    
                    for _, row in forecast.iterrows():
                        forecast_date = row['ds']
                        if forecast_date >= today:
                            forecasted_amount = max(0, row['yhat'])
                            month_obj = months.get(number=forecast_date.month)
                            year = forecast_date.year
                            
                            ForecastResult.objects.update_or_create(
                                batch=batch,
                                commodity=comm,
                                forecast_month=month_obj,
                                forecast_year=year,
                                municipality=muni,
                                defaults={'forecasted_amount_kg': forecasted_amount, 'notes': f"Generated from Prophet model"}
                            )
                            results_created += 1

            # Process "Overall" models for each commodity
            for comm in commodities:
                # Filter the main DataFrame for the specific commodity across all municipalities
                df = all_records_df[all_records_df['commodity_id'] == comm.pk].copy()
                
                if len(df) < 2:
                    print(f"Skipping Overall {comm.name}: not enough data.")
                    continue
                
                # Group by month and sum across all municipalities
                df['ds'] = pd.to_datetime(df['harvest_date'])
                df['y'] = df['total_weight_kg'].astype(float)
                df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
                df['ds'] = df['ds'].dt.to_timestamp()

                if len(df) >= 4:
                    q_low = df['y'].quantile(0.05)
                    q_high = df['y'].quantile(0.95)
                    df = df[(df['y'] >= q_low) & (df['y'] <= q_high)]
                df['y'] = df['y'].rolling(window=2, min_periods=1).mean()

                if df['y'].notna().sum() < 2:
                    print(f"Skipping Overall {comm.name}: not enough data after cleaning.")
                    continue
                
                # Train model
                m = Prophet(yearly_seasonality=True, changepoint_prior_scale=0.05, seasonality_prior_scale=1, daily_seasonality=False, weekly_seasonality=False)
                m.fit(df[['ds', 'y']])
                
                # Save "Overall" model with special naming convention
                model_filename = f"prophet_{comm.commodity_id}_14.joblib" 
                bucket_path = f"prophet_models/{model_filename}"

                # Create an in-memory buffer to hold the model file
                buffer = BytesIO()
                joblib.dump(m, buffer)

                # Rewind the buffer to the beginning before saving
                buffer.seek(0)

                # Save the model directly to DigitalOcean Spaces
                default_storage.save(bucket_path, buffer)

                # Generate forecast
                future = m.make_future_dataframe(periods=12, freq='MS') # Changed to 'MS' for month start
                forecast = m.predict(future)
                
                today = datetime.today().replace(day=1)
                
                for _, row in forecast.iterrows():
                    forecast_date = row['ds']
                    if forecast_date >= today:
                        forecasted_amount = max(0, row['yhat'])
                        month_obj = months.get(number=forecast_date.month)
                        year = forecast_date.year
                        
                        overall_muni = MunicipalityName.objects.get(pk=14)
                        ForecastResult.objects.update_or_create(
                            batch=batch,
                            commodity=comm,
                            forecast_month=month_obj,
                            forecast_year=year,
                            municipality=overall_muni,
                            defaults={'forecasted_amount_kg': forecasted_amount, 'notes': f"Overall forecast generated by Prophet"}
                        )
                        results_created += 1
                        
        print(f"Successfully generated {results_created} forecast records in batch {batch.batch_id}.")
        return True

    except Exception as e:
        # Log the error to the Celery worker logs
        print(f"An error occurred during the forecast task: {e}")
        # In a real-world scenario, you might want to log this to an external service or a Django model.
        return False