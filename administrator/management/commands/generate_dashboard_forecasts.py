from django.core.management.base import BaseCommand
from dashboard.models import VerifiedHarvestRecord, ForecastBatch, ForecastResult
from base.models import MunicipalityName, CommodityType, Month
from prophet import Prophet
import pandas as pd
import joblib
from django.core.files.storage import default_storage
from dateutil.relativedelta import relativedelta
from datetime import datetime
from django.db import transaction
from io import BytesIO

class Command(BaseCommand):
    help = 'Generate forecasts using the same logic as dashboard real-time forecasting'
  
    def handle(self, *args, **options):
        self.stdout.write("Starting forecast generation using dashboard logic...")
        
        municipalities = MunicipalityName.objects.exclude(pk=14)
        commodities = CommodityType.objects.exclude(pk=1)
        months = Month.objects.all().order_by('number')
        
        batch = ForecastBatch.objects.create(
            notes="Generated using dashboard logic - no artificial data"
        )
        
        results_created = 0
        models_trained = 0
        
        with transaction.atomic():
            # Process individual municipality-commodity combinations
            for muni in municipalities:
                for comm in commodities:
                    self.stdout.write(f"Processing {comm.name} - {muni.municipality}...")
                    
                    # Historical data
                    qs = VerifiedHarvestRecord.objects.filter(
                        municipality=muni,
                        commodity_id=comm
                    ).values('harvest_date', 'total_weight_kg').order_by('harvest_date')
                    
                    if qs.count() < 2:
                        self.stdout.write(f"  Skipping: insufficient data ({qs.count()} records)")
                        continue
                    
                    df = pd.DataFrame(list(qs))
                    df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
                    df['ds'] = pd.to_datetime(df['ds'])
                    df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
                    df = df.groupby('ds', as_index=False)['y'].sum()
                    
                    if len(df) < 2:
                        self.stdout.write(f"  Skipping: insufficient data after grouping ({len(df)} records)")
                        continue
                    
                    try:
                        # Train model
                        m = Prophet(
                            yearly_seasonality=True,
                            changepoint_prior_scale=0.05,
                            seasonality_prior_scale=1,
                            daily_seasonality=False,
                            weekly_seasonality=False
                        )
                        m.fit(df[['ds', 'y']])
                        models_trained += 1
                        
                        # Save model
                        model_filename = f"prophet_{comm.commodity_id}_{muni.municipality_id}.joblib"
                        bucket_path = f"prophet_models/{model_filename}"
                        
                        buffer = BytesIO()
                        joblib.dump(m, buffer)
                        buffer.seek(0)
                        default_storage.save(bucket_path, buffer)
                        
                        # Generate forecasts
                        future = m.make_future_dataframe(periods=12, freq='MS')
                        forecast = m.predict(future)
                        
                        # only future forecasts
                        last_historical_date = df['ds'].max()
                        future_forecast = forecast[forecast['ds'] > last_historical_date]
                        
                        # Save forecasts
                        for _, row in future_forecast.iterrows():
                            forecast_date = row['ds']
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
                                    'notes': f"Dashboard-compatible forecast"
                                }
                            )
                            results_created += 1
                        
                        self.stdout.write(f"  ✓ Created {len(future_forecast)} forecasts")
                        
                    except Exception as e:
                        self.stdout.write(f"  ✗ Error: {e}")
                        continue
            
            # Process Overall models
            self.stdout.write("\nProcessing Overall models...")
            for comm in commodities:
                self.stdout.write(f"Processing Overall {comm.name}...")
                
                qs = VerifiedHarvestRecord.objects.filter(
                    commodity_id=comm
                ).exclude(municipality_id=14).values('harvest_date', 'total_weight_kg').order_by('harvest_date')
                
                if qs.count() < 2:
                    self.stdout.write(f"  Skipping: insufficient overall data ({qs.count()} records)")
                    continue
                
                # Prep data
                df = pd.DataFrame(list(qs))
                df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
                df['ds'] = pd.to_datetime(df['ds'])
                df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
                df = df.groupby('ds', as_index=False)['y'].sum()
                
                if len(df) < 2:
                    self.stdout.write(f"  Skipping: insufficient data after grouping ({len(df)} records)")
                    continue
                
                try:
                    # Train model
                    m = Prophet(
                        yearly_seasonality=True,
                        changepoint_prior_scale=0.05,
                        seasonality_prior_scale=1,
                        daily_seasonality=False,
                        weekly_seasonality=False
                    )
                    m.fit(df[['ds', 'y']])
                    models_trained += 1
                    
                    # Save Overall model
                    model_filename = f"prophet_{comm.commodity_id}_14.joblib"
                    bucket_path = f"prophet_models/{model_filename}"
                    
                    from io import BytesIO
                    buffer = BytesIO()
                    joblib.dump(m, buffer)
                    buffer.seek(0)
                    default_storage.save(bucket_path, buffer)
                    
                    # Generate forecasts
                    future = m.make_future_dataframe(periods=12, freq='MS')
                    forecast = m.predict(future)
                    
                    # only future forecasts
                    last_historical_date = df['ds'].max()
                    future_forecast = forecast[forecast['ds'] > last_historical_date]
                    
                    # Save forecasts for Overall municipality
                    overall_muni = MunicipalityName.objects.get(pk=14)
                    for _, row in future_forecast.iterrows():
                        forecast_date = row['ds']
                        forecasted_amount = max(0, row['yhat'])
                        month_obj = months.get(number=forecast_date.month)
                        year = forecast_date.year
                        
                        ForecastResult.objects.update_or_create(
                            batch=batch,
                            commodity=comm,
                            forecast_month=month_obj,
                            forecast_year=year,
                            municipality=overall_muni,
                            defaults={
                                'forecasted_amount_kg': forecasted_amount,
                                'notes': f"Overall dashboard-compatible forecast"
                            }
                        )
                        results_created += 1
                    
                    self.stdout.write(f"  ✓ Created {len(future_forecast)} overall forecasts")
                    
                except Exception as e:
                    self.stdout.write(f"  ✗ Error: {e}")
                    continue
        
        self.stdout.write(f"\nForecast generation complete!")
        self.stdout.write(f"Models trained: {models_trained}")
        self.stdout.write(f"Forecast records created: {results_created}")
        self.stdout.write(f"Batch ID: {batch.batch_id}")
        
        # Show sample forecasts for verification
        sample_forecasts = ForecastResult.objects.filter(batch=batch).select_related(
            'commodity', 'municipality', 'forecast_month'
        )[:10]
        
        self.stdout.write("\nSample forecasts created:")
        for forecast in sample_forecasts:
            self.stdout.write(
                f"  {forecast.commodity.name} - {forecast.municipality.municipality} - "
                f"{forecast.forecast_month.name} {forecast.forecast_year}: {forecast.forecasted_amount_kg:.2f} kg"
            )
            
        self.stdout.write("\ndatabase now contains forecasts that match the dashboard real-time predictions.")
                # run: python manage.py generate_dashboard_forecasts