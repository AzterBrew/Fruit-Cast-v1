from django.core.management.base import BaseCommand
import csv
from dashboard.models import VerifiedHarvestRecord, VerifiedPlantRecord
from base.models import AdminInformation, HarvestRecord
from django.utils import timezone
from datetime import datetime
import os

class Command(BaseCommand):
    help = 'Imports verified harvest and plant data from a CSV file'

    def handle(self, *args, **kwargs):
        
        base_dir = os.path.dirname(__file__)
        
        # importing harvest records csv 
        harvest_csv_path = os.path.join(base_dir, 'verified_harvest_records.csv')
        try:
            with open(harvest_csv_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    VerifiedHarvestRecord.objects.create(
                        id=row['id'],
                        harvest_date=row['harvest_date'],
                        commodity_type=row['commodity_type'],
                        commodity_spec=row['commodity_spec'] or None,
                        total_weight_kg=row['total_weight_kg'],
                        weight_per_unit_kg=row['weight_per_unit_kg'],
                        harvest_municipality=row['harvest_municipality'],
                        remarks=row['remarks'] or None,
                        date_verified=datetime.strptime(row['date_verified'], "%Y-%m-%d %H:%M:%S") if row['date_verified'] else timezone.now(),
                        verified_by=row['verified_by'] or None,
                        prev_record=row['prev_record'] or None,
                    )
            self.stdout.write(self.style.SUCCESS("✔ Imported verified harvest records!"))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("❌ 'verified_harvest_records.csv' not found."))

        # Import Verified Plant Records
        
        # importing harvest records csv 
        plant_csv_path = os.path.join(base_dir, 'verified_plant_records.csv')
        try:
            
            with open(plant_csv_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    VerifiedPlantRecord.objects.create(
                        plant_date=row['plant_date'],
                        commodity_type=row['commodity_type'],
                        commodity_spec=row['commodity_spec'] or None,
                        expected_harvest_date=row['expected_harvest_date'],
                        estimated_weight_kg=row['estimated_weight_kg'] or None,
                        plant_municipality=row['plant_municipality'],
                        min_expected_harvest=row['min_expected_harvest'],
                        max_expected_harvest=row['max_expected_harvest'],
                        average_harvest_units=row['average_harvest_units'],
                        land_area=row['land_area'],
                        remarks=row['remarks'] or None,
                        date_verified=datetime.strptime(row['date_verified'], "%Y-%m-%d %H:%M:%S") if row['date_verified'] else timezone.now(),
                        verified_by=row['verified_by'] or None,
                        prev_record=row['prev_record'] or None
                    )
            self.stdout.write(self.style.SUCCESS("✔ Imported verified plant records!"))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("❌ 'verified_plants_records.csv' not found."))
