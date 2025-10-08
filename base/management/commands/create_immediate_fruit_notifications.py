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
                all_accounts = [account]
            except AccountsInformation.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Account with ID {options["account_id"]} not found'))
                return
        else:
            # Get all accounts
            all_accounts = AccountsInformation.objects.select_related('userinfo_id').all()
        
        total_notifications = 0
        
        for account in all_accounts:
            account_municipalities = set()
            
            # 1. Add residential municipality from user information
            if hasattr(account, 'userinfo_id') and account.userinfo_id.municipality_id:
                residential_municipality_id = account.userinfo_id.municipality_id.municipality_id
                account_municipalities.add((residential_municipality_id, None, True))  # (municipality_id, farmland_name, is_residential)
            
            # 2. Add farmland municipalities
            farmlands = FarmLand.objects.filter(userinfo_id=account.userinfo_id)
            for farmland in farmlands:
                if farmland.municipality_id:
                    farmland_municipality_id = farmland.municipality_id.municipality_id
                    farmland_name = farmland.farmland_name
                    account_municipalities.add((farmland_municipality_id, farmland_name, False))
            
            # 3. Create notifications for each unique municipality
            for municipality_id, farmland_name, is_residential in account_municipalities:
                success = schedule_immediate_fruit_recommendations(
                    account, 
                    municipality_id,
                    farmland_name=farmland_name,
                    is_residential=is_residential
                )
                if success:
                    total_notifications += 1
                    location_type = "residential" if is_residential else f"farmland ({farmland_name})"
                    self.stdout.write(
                        f'Created notification for {account.userinfo_id.firstname} '
                        f'{account.userinfo_id.lastname} - {location_type} (Municipality ID: {municipality_id})'
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {total_notifications} immediate fruit recommendation notifications'
            )
        )