from django.core.management.base import BaseCommand
from base.models import MunicipalityName

class Command(BaseCommand):
    help = 'Print all MunicipalityName records (ID and name)'

    def handle(self, *args, **options):
        self.stdout.write('All MunicipalityName records:')
        for muni in MunicipalityName.objects.all():
            self.stdout.write(f"ID: {muni.municipality_id} | Name: {muni.municipality}")
