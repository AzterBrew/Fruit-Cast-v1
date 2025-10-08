from django.core.management.base import BaseCommand
from django.utils import timezone
from base.models import AccountsInformation, FarmLand
from base.views import schedule_monthly_fruit_recommendations


class Command(BaseCommand):
    help = 'Schedule fruit recommendation notifications for all users with farmland records'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting fruit recommendation scheduling...'))
        
        # Get all accounts that have farmland records or user information
        all_accounts = AccountsInformation.objects.select_related('userinfo_id').all()
        
        total_notifications = 0
        processed_municipalities = {}  # Track municipalities per account to avoid duplicates
        
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
            
            # 3. Schedule notifications for each unique municipality
            for municipality_id, farmland_name, is_residential in account_municipalities:
                try:
                    success = schedule_monthly_fruit_recommendations(
                        account, 
                        municipality_id, 
                        farmland_name=farmland_name,
                        is_residential=is_residential
                    )
                    if success:
                        total_notifications += 1
                        location_type = "residential" if is_residential else f"farmland ({farmland_name})"
                        self.stdout.write(
                            f'Scheduled notification for {account.userinfo_id.firstname} '
                            f'{account.userinfo_id.lastname} - {location_type} (Municipality ID: {municipality_id})'
                        )
                except Exception as e:
                    location_type = "residential" if is_residential else f"farmland ({farmland_name})"
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error scheduling for {account.userinfo_id.firstname} '
                            f'{account.userinfo_id.lastname} - {location_type}: {e}'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully scheduled {total_notifications} fruit recommendation notifications'
            )
        )