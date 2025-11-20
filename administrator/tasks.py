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
                    
                    # NO FILTERING of historical data - use ALL available VerifiedHarvestRecord data for training
                    print(f"Using ALL historical data for training: {len(df)} records, date range: {df['ds'].min()} to {df['ds'].max()}")
                    
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
                    
                    # Generate forecast using dynamic approach from start of previous year to end of next year
                    current_year = datetime.today().year
                    forecast_start_date = datetime(current_year - 1, 1, 1)  # Start of previous year
                    forecast_end_date = datetime(current_year + 1, 12, 31)  # End of next year
                    
                    # Create future DataFrame with dynamic range
                    future_months = pd.date_range(start=forecast_start_date, end=forecast_end_date, freq='MS')
                    future = pd.DataFrame({'ds': future_months})
                    
                    if len(future) == 0:
                        print(f"Error: Future dataframe is empty for {comm.name} - {muni.municipality} - cannot generate forecast")
                        continue
                    
                    forecast = m.predict(future)
                    
                    # Use the entire forecast range (both historical fill-in and future predictions)
                    print(f"Debug for {comm.name} - {muni.municipality}: Generated {len(forecast)} total forecasts")
                    print(f"  Forecast range: {forecast['ds'].min()} to {forecast['ds'].max()}")
                    
                    # Round the forecasts and process all periods
                    rounded_forecasts = forecast['yhat'].round(2)
                    
                    for idx, row in forecast.iterrows():
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

                # NO FILTERING of historical data - use ALL available VerifiedHarvestRecord data for training
                print(f"Using ALL historical data for Overall {comm.name} training: {len(df)} records, date range: {df['ds'].min()} to {df['ds'].max()}")

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

                # Generate forecast using dynamic approach from start of previous year to end of next year
                current_year = datetime.today().year
                forecast_start_date = datetime(current_year - 1, 1, 1)  # Start of previous year
                forecast_end_date = datetime(current_year + 1, 12, 31)  # End of next year
                
                # Create future DataFrame with dynamic range
                future_months = pd.date_range(start=forecast_start_date, end=forecast_end_date, freq='MS')
                future = pd.DataFrame({'ds': future_months})
                
                if len(future) == 0:
                    print(f"Error: Future dataframe is empty for Overall {comm.name} - cannot generate forecast")
                    continue
                
                forecast = m.predict(future)
                
                # Use the entire forecast range (both historical fill-in and future predictions)
                print(f"Debug for Overall {comm.name}: Generated {len(forecast)} total forecasts")
                print(f"  Forecast range: {forecast['ds'].min()} to {forecast['ds'].max()}")
                
                # Round the forecasts and process all periods
                rounded_forecasts = forecast['yhat'].round(2)
                
                for idx, row in forecast.iterrows():
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


@shared_task
def retrain_selective_models_task(commodity_municipality_pairs):
    """
    Selectively retrains Prophet models for specific commodity-municipality combinations.
    
    Args:
        commodity_municipality_pairs: List of dicts with keys 'commodity_id' and 'municipality_id'
        Example: [{'commodity_id': 2, 'municipality_id': 3}, {'commodity_id': 4, 'municipality_id': 5}]
    """
    try:
        print(f"DEBUG: Starting selective retraining for {len(commodity_municipality_pairs)} combinations")
        
        # Create a ForecastBatch for tracking this selective update
        batch = ForecastBatch.objects.create(
            notes=f"Selective retraining for {len(commodity_municipality_pairs)} commodity-municipality combinations"
        )
        
        # Get unique commodities and municipalities from the pairs
        unique_commodity_ids = list(set([pair['commodity_id'] for pair in commodity_municipality_pairs]))
        unique_municipality_ids = list(set([pair['municipality_id'] for pair in commodity_municipality_pairs]))
        
        # Always include Overall (pk=14) for affected commodities
        if 14 not in unique_municipality_ids:
            unique_municipality_ids.append(14)
            
        commodities = CommodityType.objects.filter(commodity_id__in=unique_commodity_ids)
        municipalities = MunicipalityName.objects.filter(municipality_id__in=unique_municipality_ids)
        months = Month.objects.all().order_by('number')
        
        print(f"Processing commodities: {[c.name for c in commodities]}")
        print(f"Processing municipalities: {[m.municipality for m in municipalities]}")
        
        # Only delete forecast records for the specific combinations we're retraining
        for commodity in commodities:
            for municipality in municipalities:
                existing_results = ForecastResult.objects.filter(
                    commodity=commodity,
                    municipality=municipality
                )
                deleted_count = existing_results.count()
                existing_results.delete()
                if deleted_count > 0:
                    print(f"Deleted {deleted_count} existing forecast records for {commodity.name} - {municipality.municipality}")
        
        # Get all historical data for affected commodities and municipalities
        all_records_qs = VerifiedHarvestRecord.objects.filter(
            commodity_id__in=commodities,
            municipality__in=municipalities.exclude(pk=14)  # Exclude Overall from data fetch
        ).values('harvest_date', 'total_weight_kg', 'commodity_id', 'municipality_id').order_by('harvest_date')
        
        all_records_list = list(all_records_qs)
        print(f"Found {len(all_records_list)} historical records for selective retraining")
        
        if not all_records_list:
            print("No historical records found for selective retraining")
            return True
            
        all_records_df = pd.DataFrame(all_records_list)
        
        results_created = 0
        
        with transaction.atomic():
            # Process each individual municipality and commodity combination
            for commodity in commodities:
                for municipality in municipalities.exclude(pk=14):  # Skip Overall sa loop
                    # Check if this specific combination was in the original request
                    combination_requested = any(
                        pair['commodity_id'] == commodity.commodity_id and 
                        pair['municipality_id'] == municipality.municipality_id 
                        for pair in commodity_municipality_pairs
                    )
                    
                    if not combination_requested:
                        print(f"Skipping {commodity.name} - {municipality.municipality} (not in request)")
                        continue
                    
                    # Filter data for specific combination
                    if 'municipality_id' not in all_records_df.columns or 'commodity_id' not in all_records_df.columns:
                        print(f"Missing required columns in dataframe: {all_records_df.columns.tolist()}")
                        continue
                        
                    df = all_records_df[
                        (all_records_df['municipality_id'] == municipality.municipality_id) & 
                        (all_records_df['commodity_id'] == commodity.commodity_id)
                    ].copy()
                    
                    if len(df) < 2:
                        print(f"Not enough data for {municipality.municipality} - {commodity.name}")
                        continue
                    
                    # Data processing (same as original task)
                    df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
                    df['ds'] = pd.to_datetime(df['ds'])
                    df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
                    df = df.groupby('ds', as_index=False)['y'].sum()
                    
                    print(f"Training model for {municipality.municipality} - {commodity.name}: {len(df)} records")
                    
                    if len(df) < 2:
                        print(f"Insufficient data after grouping for {municipality.municipality} - {commodity.name}")
                        continue
                    
                    # Train Prophet model
                    m = Prophet(
                        yearly_seasonality=True,
                        changepoint_prior_scale=0.05,
                        seasonality_prior_scale=1,
                        daily_seasonality=False,
                        weekly_seasonality=False
                    )
                    m.fit(df[['ds', 'y']])
                    
                    # Save model
                    model_filename = f"prophet_{commodity.commodity_id}_{municipality.municipality_id}.joblib"
                    bucket_path = f"prophet_models/{model_filename}"
                    
                    buffer = BytesIO()
                    joblib.dump(m, buffer)
                    buffer.seek(0)
                    default_storage.save(bucket_path, buffer)
                    
                    # Generate forecasts
                    current_year = datetime.today().year
                    forecast_start_date = datetime(current_year - 1, 1, 1)
                    forecast_end_date = datetime(current_year + 1, 12, 31)
                    
                    future_months = pd.date_range(start=forecast_start_date, end=forecast_end_date, freq='MS')
                    future = pd.DataFrame({'ds': future_months})
                    
                    if len(future) == 0:
                        print(f"No future dates to forecast for {municipality.municipality} - {commodity.name}")
                        continue
                    
                    forecast = m.predict(future)
                    rounded_forecasts = forecast['yhat'].round(2)
                    
                    # Save forecast results
                    for idx, row in forecast.iterrows():
                        forecast_date = row['ds']
                        forecasted_amount = max(0, rounded_forecasts.loc[idx])
                        month_obj = months.get(number=forecast_date.month)
                        year = forecast_date.year
                        
                        forecast_obj, created = ForecastResult.objects.get_or_create(
                            commodity=commodity,
                            forecast_month=month_obj,
                            forecast_year=year,
                            municipality=municipality,
                            defaults={
                                'batch': batch,
                                'forecasted_amount_kg': forecasted_amount,
                                'notes': f"Selective forecast for {municipality.municipality} - {commodity.name}"
                            }
                        )
                        if created:
                            results_created += 1
                
                # Process Overall model for this commodity (if commodity was affected)
                if any(pair['commodity_id'] == commodity.commodity_id for pair in commodity_municipality_pairs):
                    print(f"Training Overall model for {commodity.name}")
                    
                    # Get all data for this commodity across all municipalities (excluding pk=14)
                    if 'commodity_id' not in all_records_df.columns:
                        print(f"Missing commodity_id column in dataframe: {all_records_df.columns.tolist()}")
                        continue
                        
                    df = all_records_df[all_records_df['commodity_id'] == commodity.commodity_id].copy()
                    
                    if len(df) < 2:
                        print(f"Not enough overall data for {commodity.name}")
                        continue
                    
                    # Data processing
                    df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
                    df['ds'] = pd.to_datetime(df['ds'])
                    df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
                    df = df.groupby('ds', as_index=False)['y'].sum()
                    
                    print(f"Training Overall {commodity.name}: {len(df)} records")
                    
                    if len(df) < 2:
                        print(f"Insufficient overall data after grouping for {commodity.name}")
                        continue
                    
                    # Train model
                    m = Prophet(
                        yearly_seasonality=True,
                        changepoint_prior_scale=0.05,
                        seasonality_prior_scale=1,
                        daily_seasonality=False,
                        weekly_seasonality=False
                    )
                    m.fit(df[['ds', 'y']])
                    
                    # Save Overall model
                    model_filename = f"prophet_{commodity.commodity_id}_14.joblib"
                    bucket_path = f"prophet_models/{model_filename}"
                    
                    buffer = BytesIO()
                    joblib.dump(m, buffer)
                    buffer.seek(0)
                    default_storage.save(bucket_path, buffer)
                    
                    # Generate forecasts for Overall
                    current_year = datetime.today().year
                    forecast_start_date = datetime(current_year - 1, 1, 1)
                    forecast_end_date = datetime(current_year + 1, 12, 31)
                    
                    future_months = pd.date_range(start=forecast_start_date, end=forecast_end_date, freq='MS')
                    future = pd.DataFrame({'ds': future_months})
                    
                    if len(future) > 0:
                        forecast = m.predict(future)
                        rounded_forecasts = forecast['yhat'].round(2)
                        
                        overall_muni = MunicipalityName.objects.get(pk=14)
                        
                        # Save forecast results for Overall
                        for idx, row in forecast.iterrows():
                            forecast_date = row['ds']
                            forecasted_amount = max(0, rounded_forecasts.loc[idx])
                            month_obj = months.get(number=forecast_date.month)
                            year = forecast_date.year
                            
                            forecast_obj, created = ForecastResult.objects.get_or_create(
                                commodity=commodity,
                                forecast_month=month_obj,
                                forecast_year=year,
                                municipality=overall_muni,
                                defaults={
                                    'batch': batch,
                                    'forecasted_amount_kg': forecasted_amount,
                                    'notes': f"Overall selective forecast for {commodity.name}"
                                }
                            )
                            if created:
                                results_created += 1
        
        print(f"Selective retraining completed! Generated {results_created} forecast records in batch {batch.batch_id}.")
        return True
        
    except Exception as e:
        print(f"An error occurred during selective retraining: {e}")
        return False