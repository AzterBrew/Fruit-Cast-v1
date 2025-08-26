import csv
from django.core.management.base import BaseCommand
from dashboard.models import VerifiedHarvestRecord

class Command(BaseCommand):
    help = 'Export VerifiedHarvestRecord data to CSV'

    def handle(self, *args, **kwargs):
        with open('verifiedharvest_export.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'harvest_date', 'commodity_id', 'municipality', 'barangay',
                'total_weight_kg', 'weight_per_unit_kg', 'remarks'
            ])
            for rec in VerifiedHarvestRecord.objects.all():
                writer.writerow([
                    rec.harvest_date,
                    rec.commodity_id_id,
                    rec.municipality_id,
                    rec.barangay_id,
                    rec.total_weight_kg,
                    rec.weight_per_unit_kg,
                    rec.remarks
                ])
        self.stdout.write(self.style.SUCCESS('Exported to verifiedharvest_export.csv'))