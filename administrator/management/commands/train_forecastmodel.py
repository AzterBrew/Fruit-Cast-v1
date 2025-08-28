from django.core.management.base import BaseCommand
from dashboard.models import VerifiedHarvestRecord
from base.models import MunicipalityName, CommodityType
from prophet import Prophet
import pandas as pd
import os
import joblib

class Command(BaseCommand):
    help = 'Train Prophet models for each municipality and commodity combination'

    def handle(self, *args, **options):
        model_dir = os.path.join('prophet_models')
        os.makedirs(model_dir, exist_ok=True)

        municipalities = MunicipalityName.objects.exclude(pk=14)
        commodities = CommodityType.objects.exclude(pk=1)

        for muni in municipalities:
            for comm in commodities:
                qs = VerifiedHarvestRecord.objects.filter(
                    municipality=muni,
                    commodity_id=comm
                ).values('harvest_date', 'total_weight_kg').order_by('harvest_date')

                if qs.count() < 2:
                    self.stdout.write(f"Not enough data for {muni} - {comm}")
                    continue

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

                # Skip if less than 2 non-NaN rows
                if df['y'].notna().sum() < 2:
                    self.stdout.write(f"Skipping: {comm.name}, {muni.municipality} (not enough data after cleaning)")
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
                model_path = os.path.join(model_dir, model_filename)
                joblib.dump(m, model_path)
                self.stdout.write(f"Trained and saved model for {muni} - {comm}")
                
                # run : python manage.py train_forecastmodel