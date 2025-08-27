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
                df = df.rename(columns={'harvest_date': 'ds', 'total_weight_kg': 'y'})
                df['ds'] = pd.to_datetime(df['ds'])
                # Group by month
                df['ds'] = df['ds'].dt.to_period('M').dt.to_timestamp()
                df = df.groupby('ds', as_index=False)['y'].sum()

                if len(df) < 2:
                    self.stdout.write(f"Not enough monthly data for {muni} - {comm}")
                    continue

                m = Prophet(yearly_seasonality=True, daily_seasonality=False, weekly_seasonality=False)
                m.fit(df)

                # Save model
                model_filename = f"prophet_{comm.commodity_id}_{muni.municipality_id}.joblib"
                model_path = os.path.join(model_dir, model_filename)
                joblib.dump(m, model_path)
                self.stdout.write(f"Trained and saved model for {muni} - {comm}")