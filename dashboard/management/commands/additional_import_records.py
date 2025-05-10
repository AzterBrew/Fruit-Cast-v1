from django.core.management.base import BaseCommand
from dashboard.models import VerifiedHarvestRecord, VerifiedPlantRecord
import random
from datetime import datetime, timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = "Generates and inserts additional random harvest and plant records into the database"

    def handle(self, *args, **kwargs):
        commodity_types = ["Mango", "Banana", "Papaya", "Pineapple", "Lanzones", "Rambutan", "Guava", "Durian", "Mangosteen", "Calamansi"]
        locations = ["Balanga", "Orani", "Dinalupihan", "Abucay", "Hermosa", "Samal", "Pilar", "Bagac", "Morong", "Mariveles"]
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2025, 12, 31)

        def random_date(start, end):
            return start + timedelta(days=random.randint(0, (end - start).days))

        # ✅ Generate 100 VerifiedHarvestRecord objects
        for _ in range(100):
            harvest_date = random_date(start_date, end_date).date()
            VerifiedHarvestRecord.objects.create(
                harvest_date=harvest_date,
                commodity_type=random.choice(commodity_types),
                commodity_spec=f"Spec {random.randint(1,3)}",
                total_weight_kg=round(random.uniform(100, 1000), 2),
                weight_per_unit_kg=round(random.uniform(0.1, 3.0), 2),
                harvest_location=random.choice(locations),
                remarks="",
                date_verified=timezone.now(),
                verified_by=None,
                prev_record=None
            )

        self.stdout.write(self.style.SUCCESS("✅ 100 additional harvest records added."))

        # ✅ Generate 100 VerifiedPlantRecord objects
        for _ in range(100):
            plant_date = random_date(start_date, end_date).date()
            min_harvest = random.randint(100, 500)
            max_harvest = min_harvest + random.randint(0, 200)
            avg_units = round((min_harvest + max_harvest) / 2, 2)
            avg_weight_per_unit = round(random.uniform(0.1, 3.0), 2)
            est_weight = round(avg_units * avg_weight_per_unit, 2)
            VerifiedPlantRecord.objects.create(
                plant_date=plant_date,
                commodity_type=random.choice(commodity_types),
                commodity_spec=f"Spec {random.randint(1,3)}",
                expected_harvest_date=plant_date + timedelta(days=random.randint(60, 150)),
                estimated_weight_kg=est_weight,
                plant_location=random.choice(locations),
                min_expected_harvest=min_harvest,
                max_expected_harvest=max_harvest,
                average_harvest_units=avg_units,
                land_area=round(random.uniform(100, 1000), 2),
                remarks="",
                date_verified=timezone.now(),
                verified_by=None,
                prev_record=None
            )

        self.stdout.write(self.style.SUCCESS("✅ 100 additional plant records added."))
