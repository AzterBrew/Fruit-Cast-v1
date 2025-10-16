from django.core.management.base import BaseCommand
from dashboard.models import ForecastResult, ForecastBatch
from django.db.models import Q

class Command(BaseCommand):
    help = 'Clean up artificial forecast data (1.0 kg values) from database'
 
    def handle(self, *args, **options):
        self.stdout.write("Cleaning up artificial forecast data...")
        
        # Count artificial forecasts (1.0 kg values)
        artificial_count = ForecastResult.objects.filter(
            Q(forecasted_amount_kg=1.0) | Q(notes__icontains="minimal forecast")
        ).count()
        
        self.stdout.write(f"Found {artificial_count} artificial forecast records to delete")
         
        if artificial_count > 0:
            # Delete artificial forecasts
            deleted_count = ForecastResult.objects.filter(
                Q(forecasted_amount_kg=1.0) | Q(notes__icontains="minimal forecast")
            ).delete()[0]
            
            self.stdout.write(f"Deleted {deleted_count} artificial forecast records")
            
            # Delete empty batches
            empty_batches = ForecastBatch.objects.filter(results__isnull=True)
            empty_batch_count = empty_batches.count()
            empty_batches.delete()
            
            self.stdout.write(f"Deleted {empty_batch_count} empty forecast batches")
        else:
            self.stdout.write("No artificial forecast data found")
        
        # Show remaining forecast statistics
        remaining_forecasts = ForecastResult.objects.count()
        self.stdout.write(f"Remaining forecast records: {remaining_forecasts}")
        
        if remaining_forecasts > 0:
            # Show sample of remaining data
            sample_forecasts = ForecastResult.objects.select_related(
                'commodity', 'municipality', 'forecast_month'
            )[:5]
            
            self.stdout.write("\nSample remaining forecasts:")
            for forecast in sample_forecasts:
                self.stdout.write(
                    f"  {forecast.commodity.name} - {forecast.municipality.municipality} - "
                    f"{forecast.forecast_month.name} {forecast.forecast_year}: {forecast.forecasted_amount_kg} kg"
                )
        
        self.stdout.write("\nCleanup complete!")
                # run: python manage.py cleanup_forecasts