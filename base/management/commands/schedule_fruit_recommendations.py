from django.core.management.base import BaseCommand
from django.utils import timezone
from base.models import AccountsInformation, FarmLand
from base.views import schedule_monthly_fruit_recommendations


class Command(BaseCommand):
    help = 'Schedule fruit recommendation notifications for all users with farmland records'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting fruit recommendation scheduling...'))
        
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
                try:
                    schedule_monthly_fruit_recommendations(account, municipality_id)
                    total_notifications += 1
                    self.stdout.write(
                        f'Scheduled notification for {account.userinfo_id.firstname} '
                        f'{account.userinfo_id.lastname} (Municipality ID: {municipality_id})'
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error scheduling for {account.userinfo_id.firstname} '
                            f'{account.userinfo_id.lastname}: {e}'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully scheduled {total_notifications} fruit recommendation notifications'
            )
        )