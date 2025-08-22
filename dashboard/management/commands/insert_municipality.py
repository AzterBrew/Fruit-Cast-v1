from django.core.management.base import BaseCommand
from base.models import MunicipalityName

class Command(BaseCommand):
    help = 'Insert municipality records'

    def handle(self, *args, **kwargs):
        municipalities = [
            'Abucay', 'Bagac', 'Balanga', 'Dinalupihan', 'Hermosa', 'Limay', 'Mariveles', 'Morong', 'Orani', 'Orion','Orion', 'Pilar', 'Samal', 'Overall in Bataan'
        ]
        for name in municipalities:
            MunicipalityName.objects.get_or_create(municipality=name)
        self.stdout.write(self.style.SUCCESS('Municipalities inserted!'))