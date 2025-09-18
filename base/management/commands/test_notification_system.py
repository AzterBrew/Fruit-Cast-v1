from django.core.management.base import BaseCommand
from django.utils import timezone
from base.models import AccountsInformation, FarmLand
from dashboard.models import Notification
from base.views import schedule_monthly_fruit_recommendations


class Command(BaseCommand):
    help = 'Test the notification scheduling system with detailed output'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Test with a specific account ID'
        )
        parser.add_argument(
            '--show-existing',
            action='store_true',
            help='Show existing notifications before creating new ones'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== NOTIFICATION SYSTEM TEST ==='))
        
        current_time = timezone.now()
        self.stdout.write(f"Current time: {current_time}")
        self.stdout.write(f"Current day of month: {current_time.day}")
        
        # Get test account
        if options['account_id']:
            try:
                account = AccountsInformation.objects.get(account_id=options['account_id'])
            except AccountsInformation.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Account with ID {options["account_id"]} not found'))
                return
        else:
            # Get first account with farmland
            account = AccountsInformation.objects.filter(
                userinfo_id__farmland__isnull=False
            ).first()
            if not account:
                self.stdout.write(self.style.ERROR('No accounts with farmland found'))
                return
        
        self.stdout.write(f"\nTesting with account: {account.userinfo_id.firstname} {account.userinfo_id.lastname} (ID: {account.account_id})")
        
        # Show existing notifications if requested
        if options['show_existing']:
            existing_notifications = Notification.objects.filter(
                account=account,
                notification_type="fruit_recommendation"
            ).order_by('-created_at')
            
            self.stdout.write(f"\n=== EXISTING NOTIFICATIONS ({existing_notifications.count()}) ===")
            for notif in existing_notifications:
                self.stdout.write(
                    f"- Scheduled for: {notif.scheduled_for} | Created: {notif.created_at} | "
                    f"Read: {notif.is_read} | Message: {notif.message[:60]}..."
                )
        
        # Get farmlands and test scheduling
        farmlands = FarmLand.objects.filter(userinfo_id=account.userinfo_id)
        municipality_ids = farmlands.values_list('municipality_id', flat=True).distinct()
        
        self.stdout.write(f"\n=== FARMLANDS ({farmlands.count()}) ===")
        for farmland in farmlands:
            self.stdout.write(f"- {farmland.farmland_name} in {farmland.municipality.municipality}")
        
        self.stdout.write(f"\n=== SCHEDULING TESTS ===")
        for municipality_id in municipality_ids:
            municipality_name = farmlands.filter(municipality_id=municipality_id).first().municipality.municipality
            self.stdout.write(f"\nTesting municipality: {municipality_name} (ID: {municipality_id})")
            
            # Count existing notifications for this municipality and month
            existing_count = Notification.objects.filter(
                account=account,
                notification_type="fruit_recommendation",
                message__icontains=municipality_name,
                scheduled_for__month=current_time.month,
                scheduled_for__year=current_time.year
            ).count()
            
            self.stdout.write(f"Existing notifications for this month: {existing_count}")
            
            # Try to schedule
            success = schedule_monthly_fruit_recommendations(account, municipality_id)
            self.stdout.write(f"Scheduling result: {'SUCCESS' if success else 'SKIPPED/FAILED'}")
        
        # Show final notification count
        final_count = Notification.objects.filter(
            account=account,
            notification_type="fruit_recommendation"
        ).count()
        
        self.stdout.write(f"\n=== FINAL RESULTS ===")
        self.stdout.write(f"Total fruit recommendation notifications for this account: {final_count}")
        
        # Show due notifications
        due_notifications = Notification.objects.filter(
            account=account,
            scheduled_for__lte=current_time,
            is_read=False,
            notification_type="fruit_recommendation"
        )
        
        self.stdout.write(f"Notifications due for delivery: {due_notifications.count()}")
        
        self.stdout.write(self.style.SUCCESS('\n=== TEST COMPLETE ==='))
        self.stdout.write('Next steps:')
        self.stdout.write('1. Run: python manage.py process_scheduled_notifications --dry-run')
        self.stdout.write('2. Run: python manage.py process_scheduled_notifications')
        self.stdout.write('3. Check the notification panel in the web interface')