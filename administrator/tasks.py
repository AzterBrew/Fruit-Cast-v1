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
        
        # Define municipalities and commodities first
        municipalities = MunicipalityName.objects.exclude(pk=14)
        commodities = CommodityType.objects.exclude(pk=1)
        months = Month.objects.all().order_by('number')
        
        # Clear any existing forecast records that might conflict
        print(f"Clearing any existing forecast records to prevent duplicates...")
        
        # Delete existing forecast records for commodities and municipalities we're about to generate
        existing_results = ForecastResult.objects.filter(
            commodity__in=commodities,
            municipality__in=list(municipalities) + [MunicipalityName.objects.get(pk=14)]  # Include "Overall"
        )
        deleted_count = existing_results.count()
        existing_results.delete()
        print(f"Deleted {deleted_count} existing forecast records.")
        
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
                    
                    # Use EXACT Dashboard approach - match forecast view logic
                    df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
                    df['ds'] = pd.to_datetime(df['ds'])
                    df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
                    df = df.groupby('ds', as_index=False)['y'].sum()
                    
                    # Filter out future outlier dates (anything beyond current date + 1 year) - EXACT MATCH
                    current_date = pd.Timestamp.now()
                    max_allowed_date = current_date + pd.DateOffset(years=1)
                    df = df[df['ds'] <= max_allowed_date]
                    
                    if len(df) < 2:
                        print(f"Skipping {comm.name} - {muni.municipality}: insufficient data after grouping and filtering.")
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
                    
                    # Generate forecast using EXACT Dashboard approach
                    last_historical_date = df['ds'].max()
                    backtest_start_date = last_historical_date - pd.offsets.MonthBegin(12) if len(df) > 12 else df['ds'].min()
                    
                    # Define the end date for forecast (12 months into the future) - EXACT MATCH
                    future_end_date = datetime.today() + relativedelta(months=+12)

                    # Create future DataFrame that includes backtesting and future periods - EXACT MATCH
                    future_months = pd.date_range(start=backtest_start_date, end=future_end_date, freq='MS')
                    future = pd.DataFrame({'ds': future_months})
                    
                    if len(future) == 0:
                        print(f"Error: Future dataframe is empty for {comm.name} - {muni.municipality} - cannot generate forecast")
                        continue
                    
                    forecast = m.predict(future)
                    
                    # EXACT Dashboard logic: only future forecasts beyond last historical date
                    future_forecast = forecast[forecast['ds'] > last_historical_date]
                    
                    print(f"Debug for {comm.name} - {muni.municipality}: Generated {len(future_forecast)} future forecasts")
                    print(f"  Last historical date: {last_historical_date}")
                    print(f"  Future forecast range: {future_forecast['ds'].min()} to {future_forecast['ds'].max()}")
                    
                    # Use EXACT same processing as dashboard: round the entire series first, then process
                    rounded_forecasts = future_forecast['yhat'].round(2)  # Apply rounding to entire series like dashboard
                    
                    for idx, row in future_forecast.iterrows():
                        forecast_date = row['ds']
                        # Use the pre-rounded value from the series (exact dashboard approach)
                        forecasted_amount = max(0, rounded_forecasts.loc[idx])  # Ensure non-negative values
                        month_obj = months.get(number=forecast_date.month)
                        year = forecast_date.year
                        
                        print(f"  Saving forecast: {comm.name} - {muni.municipality} - {month_obj.name} {year}: {forecasted_amount} kg")
                        
                        # Use get_or_create to avoid duplicates, but since we cleared existing records, this should create new ones
                        forecast_obj, created = ForecastResult.objects.get_or_create(
                            commodity=comm,
                            forecast_month=month_obj,
                            forecast_year=year,
                            municipality=muni,
                            defaults={
                                'batch': batch,
                                'forecasted_amount_kg': forecasted_amount, 
                                'notes': f"Generated from Prophet model"
                            }
                        )
                        if created:
                            results_created += 1
                        else:
                            # Update existing record if somehow one exists
                            forecast_obj.batch = batch
                            forecast_obj.forecasted_amount_kg = forecasted_amount
                            forecast_obj.notes = f"Generated from Prophet model"
                            forecast_obj.save()

            # Process "Overall" models for each commodity
            for comm in commodities:
                # Filter the main DataFrame for the specific commodity across all municipalities
                df = all_records_df[all_records_df['commodity_id'] == comm.pk].copy()
                
                if len(df) < 2:
                    print(f"Skipping Overall {comm.name}: not enough data.")
                    continue
                
                # Use EXACT Dashboard approach - match forecast view logic
                df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
                df['ds'] = pd.to_datetime(df['ds'])
                df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
                df = df.groupby('ds', as_index=False)['y'].sum()

                # Filter out future outlier dates (anything beyond current date + 1 year) - EXACT MATCH
                current_date = pd.Timestamp.now()
                max_allowed_date = current_date + pd.DateOffset(years=1)
                df = df[df['ds'] <= max_allowed_date]

                if len(df) < 2:
                    print(f"Skipping Overall {comm.name}: insufficient data after grouping and filtering.")
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

                # Generate forecast using EXACT Dashboard approach
                last_historical_date = df['ds'].max()
                backtest_start_date = last_historical_date - pd.offsets.MonthBegin(12) if len(df) > 12 else df['ds'].min()
                
                # Define the end date for forecast (12 months into the future) - EXACT MATCH
                future_end_date = datetime.today() + relativedelta(months=+12)

                # Create future DataFrame that includes backtesting and future periods - EXACT MATCH
                future_months = pd.date_range(start=backtest_start_date, end=future_end_date, freq='MS')
                future = pd.DataFrame({'ds': future_months})
                
                if len(future) == 0:
                    print(f"Error: Future dataframe is empty for Overall {comm.name} - cannot generate forecast")
                    continue
                
                forecast = m.predict(future)
                
                # EXACT Dashboard logic: only future forecasts beyond last historical date
                future_forecast = forecast[forecast['ds'] > last_historical_date]
                
                print(f"Debug for Overall {comm.name}: Generated {len(future_forecast)} future forecasts")
                print(f"  Last historical date: {last_historical_date}")
                print(f"  Future forecast range: {future_forecast['ds'].min()} to {future_forecast['ds'].max()}")
                
                # Use EXACT same processing as dashboard: round the entire series first, then process
                rounded_forecasts = future_forecast['yhat'].round(2)  # Apply rounding to entire series like dashboard
                
                for idx, row in future_forecast.iterrows():
                    forecast_date = row['ds']
                    forecasted_amount = max(0, rounded_forecasts.loc[idx])  # Use series-level rounded value
                    month_obj = months.get(number=forecast_date.month)
                    year = forecast_date.year
                    
                    print(f"  Saving forecast: {comm.name} - Overall - {month_obj.name} {year}: {forecasted_amount} kg")
                    
                    overall_muni = MunicipalityName.objects.get(pk=14)
                    # Use get_or_create to avoid duplicates, but since we cleared existing records, this should create new ones
                    forecast_obj, created = ForecastResult.objects.get_or_create(
                        commodity=comm,
                        forecast_month=month_obj,
                        forecast_year=year,
                        municipality=overall_muni,
                        defaults={
                            'batch': batch,
                            'forecasted_amount_kg': forecasted_amount, 
                            'notes': f"Overall forecast generated by Prophet"
                        }
                    )
                    if created:
                        results_created += 1
                    else:
                        # Update existing record if somehow one exists
                        forecast_obj.batch = batch
                        forecast_obj.forecasted_amount_kg = forecasted_amount
                        forecast_obj.notes = f"Overall forecast generated by Prophet"
                        forecast_obj.save()

        print(f"Successfully generated {results_created} forecast records in batch {batch.batch_id}.")
        return True

    except Exception as e:
        # Log the error to the Celery worker logs
        print(f"An error occurred during the forecast task: {e}")
        # In a real-world scenario, you might want to log this to an external service or a Django model.
        return False