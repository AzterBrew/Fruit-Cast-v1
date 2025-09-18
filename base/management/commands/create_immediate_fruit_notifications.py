from django.core.management.base import BaseCommand
from django.utils import timezone
from base.models import AccountsInformation, FarmLand
from base.views import schedule_immediate_fruit_recommendations


class Command(BaseCommand):
    help = 'Create immediate fruit recommendation notifications for testing purposes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Specific account ID to create notifications for (optional)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating immediate fruit recommendation notifications...'))
        
        if options['account_id']:
            # Handle specific account
            try:
                account = AccountsInformation.objects.get(account_id=options['account_id'])
                accounts_with_farmland = [account]
            except AccountsInformation.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Account with ID {options["account_id"]} not found'))
                return
        else:
            # Get all accounts that have farmland records
            accounts_with_farmland = AccountsInformation.objects.filter(
                userinfo_id__farmland__isnull=False
            ).distinct()
        
        total_notifications = 0
        
        for account in accounts_with_farmland:
            # Get distinct municipality IDs from user's farmlands
            distinct_municipality_ids = FarmLand.objects.filter(
                userinfo_id=account.userinfo_id
            ).values_list('municipality_id', flat=True).distinct()
            
            for municipality_id in distinct_municipality_ids:
                success = schedule_immediate_fruit_recommendations(account, municipality_id)
                if success:
                    total_notifications += 1
                    self.stdout.write(
                        f'Created notification for {account.userinfo_id.firstname} '
                        f'{account.userinfo_id.lastname} (Municipality ID: {municipality_id})'
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {total_notifications} immediate fruit recommendation notifications'
            )
        )