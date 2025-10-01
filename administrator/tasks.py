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
                    
                    # Create minimal data if not enough records exist (to match dashboard behavior)
                    if len(df) < 2:
                        print(f"Creating synthetic data for {comm.name} - {muni.municipality}: insufficient historical data.")
                        # Create minimal synthetic data to enable forecasting (like dashboard does)
                        today = datetime.today()
                        synthetic_data = pd.DataFrame({
                            'harvest_date': [today - relativedelta(months=2), today - relativedelta(months=1)],
                            'total_weight_kg': [1.0, 1.0]  # Minimal values
                        })
                        df = pd.concat([df, synthetic_data], ignore_index=True)
                    
                    # Group and clean the data for Prophet (same as dashboard)
                    df['ds'] = pd.to_datetime(df['harvest_date'])
                    df['y'] = df['total_weight_kg'].astype(float)
                    df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
                    df['ds'] = df['ds'].dt.to_timestamp()
                    
                    # Apply lighter data cleaning (more permissive than before)
                    if len(df) >= 4:
                        q_low = df['y'].quantile(0.05)
                        q_high = df['y'].quantile(0.95)
                        df = df[(df['y'] >= q_low) & (df['y'] <= q_high)]
                    df['y'] = df['y'].rolling(window=2, min_periods=1).mean()
                    
                    # More permissive check (even 1 data point can work with Prophet)
                    if df['y'].notna().sum() < 1:
                        print(f"Skipping {comm.name} - {muni.municipality}: no valid data after cleaning.")
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
                
                # Create minimal data if not enough records exist (to match dashboard behavior)
                if len(df) < 2:
                    print(f"Creating synthetic data for Overall {comm.name}: insufficient historical data.")
                    # Create minimal synthetic data to enable forecasting
                    today = datetime.today()
                    synthetic_data = pd.DataFrame({
                        'harvest_date': [today - relativedelta(months=2), today - relativedelta(months=1)],
                        'total_weight_kg': [1.0, 1.0]  # Minimal values
                    })
                    df = pd.concat([df, synthetic_data], ignore_index=True)
                
                # Group by month and sum across all municipalities
                df['ds'] = pd.to_datetime(df['harvest_date'])
                df['y'] = df['total_weight_kg'].astype(float)
                df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
                df['ds'] = df['ds'].dt.to_timestamp()

                # Apply lighter data cleaning (more permissive than before)
                if len(df) >= 4:
                    q_low = df['y'].quantile(0.05)
                    q_high = df['y'].quantile(0.95)
                    df = df[(df['y'] >= q_low) & (df['y'] <= q_high)]
                df['y'] = df['y'].rolling(window=2, min_periods=1).mean()

                # More permissive check
                if df['y'].notna().sum() < 1:
                    print(f"Skipping Overall {comm.name}: no valid data after cleaning.")
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
        
        # ADDITIONAL: Generate forecasts for ALL missing combinations using fallback logic
        print("Generating forecasts for missing municipality-commodity combinations...")
        
        # Get all possible combinations
        all_munis = list(municipalities) + [MunicipalityName.objects.get(pk=14)]  # Include "Overall"
        all_combinations = []
        for muni in all_munis:
            for comm in commodities:
                all_combinations.append((muni, comm))
        
        # Check which combinations are missing from the current batch
        existing_combinations = set(
            ForecastResult.objects.filter(batch=batch)
            .values_list('municipality_id', 'commodity_id')
        )
        
        missing_combinations = [
            (muni, comm) for muni, comm in all_combinations 
            if (muni.pk, comm.pk) not in existing_combinations
        ]
        
        print(f"Found {len(missing_combinations)} missing combinations. Generating fallback forecasts...")
        
        # Generate fallback forecasts for missing combinations
        for muni, comm in missing_combinations:
            try:
                # Use overall model if individual model doesn't exist
                individual_model_path = f"prophet_models/prophet_{comm.commodity_id}_{muni.municipality_id}.joblib"
                overall_model_path = f"prophet_models/prophet_{comm.commodity_id}_14.joblib"
                
                model_path = None
                if default_storage.exists(individual_model_path):
                    model_path = individual_model_path
                elif default_storage.exists(overall_model_path):
                    model_path = overall_model_path
                
                if model_path:
                    # Load the model and generate forecasts
                    with default_storage.open(model_path, 'rb') as f:
                        m = joblib.load(f)
                    
                    # Generate forecast
                    future = m.make_future_dataframe(periods=12, freq='MS')
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
                                defaults={
                                    'forecasted_amount_kg': forecasted_amount, 
                                    'notes': f"Fallback forecast using {'individual' if 'individual' in model_path else 'overall'} model"
                                }
                            )
                            results_created += 1
                else:
                    # Create minimal forecasts with default values
                    print(f"No model available for {muni.municipality} - {comm.name}. Creating minimal forecasts.")
                    today = datetime.today().replace(day=1)
                    
                    for i in range(12):  # 12 months ahead
                        forecast_date = today + relativedelta(months=i)
                        month_obj = months.get(number=forecast_date.month)
                        year = forecast_date.year
                        
                        # Use a minimal forecast value (could be based on average, seasonal data, etc.)
                        minimal_forecast = 1.0  # Adjust this based on your business logic
                        
                        ForecastResult.objects.update_or_create(
                            batch=batch,
                            commodity=comm,
                            forecast_month=month_obj,
                            forecast_year=year,
                            municipality=muni,
                            defaults={
                                'forecasted_amount_kg': minimal_forecast, 
                                'notes': f"Minimal forecast (no model/data available)"
                            }
                        )
                        results_created += 1
                        
            except Exception as e:
                print(f"Error generating fallback forecast for {muni.municipality} - {comm.name}: {e}")
                continue
        
        print(f"Final total: {results_created} forecast records generated in batch {batch.batch_id}.")
        return True

    except Exception as e:
        # Log the error to the Celery worker logs
        print(f"An error occurred during the forecast task: {e}")
        # In a real-world scenario, you might want to log this to an external service or a Django model.
        return False