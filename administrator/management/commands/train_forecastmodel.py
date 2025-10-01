from django.core.management.base import BaseCommand
from dashboard.models import VerifiedHarvestRecord
from base.models import MunicipalityName, CommodityType
from prophet import Prophet
import pandas as pd
import os
import joblib
from django.conf import settings
from django.core.files.storage import default_storage
from io import BytesIO

class Command(BaseCommand):
    help = 'Train Prophet models for each municipality and commodity combination'
 
    def handle(self, *args, **options):

        municipalities = MunicipalityName.objects.exclude(pk=14)
        commodities = CommodityType.objects.exclude(pk=1)

        for muni in municipalities:
            for comm in commodities:
                qs = VerifiedHarvestRecord.objects.filter(
                    municipality=muni,
                    commodity_id=comm
                ).values('harvest_date', 'total_weight_kg').order_by('harvest_date')

                # Create minimal data if not enough records exist (to match dashboard behavior)
                if qs.count() < 2:
                    self.stdout.write(f"Creating synthetic data for {muni} - {comm}: insufficient historical data")
                    # Create minimal synthetic data to enable forecasting
                    from datetime import datetime
                    from dateutil.relativedelta import relativedelta
                    today = datetime.today()
                    synthetic_data = [
                        {'harvest_date': today - relativedelta(months=2), 'total_weight_kg': 1.0},
                        {'harvest_date': today - relativedelta(months=1), 'total_weight_kg': 1.0}
                    ]
                    df = pd.DataFrame(list(qs) + synthetic_data)
                else:
                    df = pd.DataFrame(list(qs))

                if df.empty:
                    self.stdout.write(f"No data for {muni} - {comm}")
                    continue
                df['ds'] = pd.to_datetime(df['harvest_date'])
                df['y'] = df['total_weight_kg'].astype(float)
                df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
                df['ds'] = df['ds'].dt.to_timestamp()

                # Remove outliers (5th and 95th percentiles)
                if len(df) >= 4:
                    q_low = df['y'].quantile(0.05)
                    q_high = df['y'].quantile(0.95)
                    df = df[(df['y'] >= q_low) & (df['y'] <= q_high)]

                # Smooth data (rolling mean)
                df['y'] = df['y'].rolling(window=2, min_periods=1).mean()

                # More permissive check - even 1 data point can work with Prophet
                if df['y'].notna().sum() < 1:
                    self.stdout.write(f"Skipping: {comm.name}, {muni.municipality} (no valid data after cleaning)")
                    continue

                # Prophet model with tuned parameters
                m = Prophet(
                    yearly_seasonality=True,
                    changepoint_prior_scale=0.05,
                    seasonality_prior_scale=1,
                    daily_seasonality=False,
                    weekly_seasonality=False
                )
                m.fit(df[['ds', 'y']])

                # Save model (optionally, could also save last cleaned df for debugging)
                model_filename = f"prophet_{comm.commodity_id}_{muni.municipality_id}.joblib"
                
                bucket_path = f"prophet_models/{model_filename}"

                # Create an in-memory buffer to hold the model file
                buffer = BytesIO()
                joblib.dump(m, buffer)

                # Rewind the buffer to the beginning before saving
                buffer.seek(0)

                # Save the model directly to DigitalOcean Spaces
                default_storage.save(bucket_path, buffer)
                
                self.stdout.write(f"Trained and saved model for {muni} - {comm}")
            
            
        self.stdout.write("Training Overall models...")
        for comm in commodities:
            # Get all harvest data for this commodity across ALL municipalities (excluding pk=14)
            qs = VerifiedHarvestRecord.objects.filter(
                commodity_id=comm
            ).exclude(municipality_id=14).values('harvest_date', 'total_weight_kg').order_by('harvest_date')

            # Create minimal data if not enough records exist (to match dashboard behavior)
            if qs.count() < 2:
                self.stdout.write(f"Creating synthetic data for Overall {comm}: insufficient historical data")
                # Create minimal synthetic data to enable forecasting
                from datetime import datetime
                from dateutil.relativedelta import relativedelta
                today = datetime.today()
                synthetic_data = [
                    {'harvest_date': today - relativedelta(months=2), 'total_weight_kg': 1.0},
                    {'harvest_date': today - relativedelta(months=1), 'total_weight_kg': 1.0}
                ]
                df = pd.DataFrame(list(qs) + synthetic_data)
            else:
                df = pd.DataFrame(list(qs))

            if df.empty:
                self.stdout.write(f"No overall data for {comm}")
                continue

            df['ds'] = pd.to_datetime(df['harvest_date'])
            df['y'] = df['total_weight_kg'].astype(float)
            
            # Group by month and sum across all municipalities
            df = df.groupby(df['ds'].dt.to_period('M'))['y'].sum().reset_index()
            df['ds'] = df['ds'].dt.to_timestamp()

            # Remove outliers (5th and 95th percentiles)
            if len(df) >= 4:
                q_low = df['y'].quantile(0.05)
                q_high = df['y'].quantile(0.95)
                df = df[(df['y'] >= q_low) & (df['y'] <= q_high)]

            # Smooth data (rolling mean)
            df['y'] = df['y'].rolling(window=2, min_periods=1).mean()

            # More permissive check - even 1 data point can work with Prophet
            if df['y'].notna().sum() < 1:
                self.stdout.write(f"Skipping: {comm.name} Overall (no valid data after cleaning)")
                continue

            # Prophet model with tuned parameters
            m = Prophet(
                yearly_seasonality=True,
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=1,
                daily_seasonality=False,
                weekly_seasonality=False
            )
            m.fit(df[['ds', 'y']])

            # Save "Overall" model with special naming convention
            model_filename = f"prophet_{comm.commodity_id}_14.joblib"  # Use 14 for "Overall"
            
            bucket_path = f"prophet_models/{model_filename}"

            # Create an in-memory buffer to hold the model file
            buffer = BytesIO()
            joblib.dump(m, buffer)

            # Rewind the buffer to the beginning before saving
            buffer.seek(0)

            # Save the model directly to DigitalOcean Spaces
            default_storage.save(bucket_path, buffer)
            
            self.stdout.write(f"Trained and saved Overall model for {comm}")

        self.stdout.write("Model training complete!")
                # run : python manage.py train_forecastmodel