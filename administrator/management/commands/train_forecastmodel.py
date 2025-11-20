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

                if qs.count() < 2:
                    self.stdout.write(f"Not enough data for {muni} - {comm}")
                    continue
 
                df = pd.DataFrame(list(qs))
                if df.empty:
                    self.stdout.write(f"No data for {muni} - {comm}")
                    continue
                    
                df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
                df['ds'] = pd.to_datetime(df['ds'])
                df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
                df = df.groupby('ds', as_index=False)['y'].sum()

                # checking  / debuggin
                print(f"Using ALL historical data for training {muni} - {comm}: {len(df)} records")

                if len(df) < 2:
                    self.stdout.write(f"Insufficient data after grouping and filtering for {muni} - {comm}")
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

                # Save model
                model_filename = f"prophet_{comm.commodity_id}_{muni.municipality_id}.joblib"
                
                bucket_path = f"prophet_models/{model_filename}"

                # in-memory bufferfor holding the model file
                buffer = BytesIO()
                joblib.dump(m, buffer)

                # Rewind the buffer to the beginning before saving
                buffer.seek(0)
                #  directly saving to DigitalOcean Spaces
                default_storage.save(bucket_path, buffer)
                
                self.stdout.write(f"Trained and saved model for {muni} - {comm}")
            
        self.stdout.write("Training Overall models...")
        for comm in commodities:
            # Get all harvest data for this commodity across all municipalities in db (excluding pk=14)
            qs = VerifiedHarvestRecord.objects.filter(
                commodity_id=comm
            ).exclude(municipality_id=14).values('harvest_date', 'total_weight_kg').order_by('harvest_date')

            if qs.count() < 2:
                self.stdout.write(f"Not enough overall data for {comm}")
                continue

            df = pd.DataFrame(list(qs))
            if df.empty:
                self.stdout.write(f"No overall data for {comm}")
                continue

            df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
            df['ds'] = pd.to_datetime(df['ds'])
            df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
            df = df.groupby('ds', as_index=False)['y'].sum()

            # checking  / debuggin
            print(f"Using ALL historical data for Overall {comm} training: {len(df)} records")

            if len(df) < 2:
                self.stdout.write(f"Insufficient overall data after grouping and filtering for {comm}")
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

            # in-memory bufferfor holding the model file
            buffer = BytesIO()
            joblib.dump(m, buffer)

            # Rewind the buffer to the beginning before saving
            buffer.seek(0)

            #  directly saving to DigitalOcean Spaces
            default_storage.save(bucket_path, buffer)
            
            self.stdout.write(f"Trained and saved Overall model for {comm}")

        self.stdout.write("Model training complete!")
                # run : python manage.py train_forecastmodel