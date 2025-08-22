from django.core.management.base import BaseCommand
from base.models import UnitMeasurement

class Command(BaseCommand):
    help = 'Insert unit measurement records'

    def handle(self, *args, **kwargs):
        units = [
            ('kg', 'Kilogram'),
            ('g', 'Gram'),
            ('ton', 'Metric Ton'),
            ('lbs', 'Pounds'),
        ]
        for abrv, full in units:
            UnitMeasurement.objects.get_or_create(unit_abrv=abrv, unit_full=full)
        self.stdout.write(self.style.SUCCESS('Unit measurements inserted!'))