from django.core.management.base import BaseCommand
from base.models import Month

class Command(BaseCommand):
    help = 'Insert month records'

    def handle(self, *args, **kwargs):
        months = [
            ('January', 1), ('February', 2), ('March', 3), ('April', 4), ('May', 5), ('June', 6),
            ('July', 7), ('August', 8), ('September', 9), ('October', 10), ('November', 11), ('December', 12)
        ]
        for name, number in months:
            Month.objects.get_or_create(name=name, number=number)
        self.stdout.write(self.style.SUCCESS('Months inserted!'))