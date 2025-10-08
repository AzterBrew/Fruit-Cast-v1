from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.models import Notification


class Command(BaseCommand):
    help = 'Process scheduled notifications that are due for delivery'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what notifications would be processed without actually processing them'
        )

    def handle(self, *args, **options):
        current_time = timezone.now()
         
        # Find notifications that are scheduled for now or in the past and haven't been "delivered" yet
        # We'll use the is_read field to track if a notification has been "delivered"
        due_notifications = Notification.objects.filter(
            scheduled_for__lte=current_time,
            is_read=False,  # Using is_read=False to indicate "not yet delivered"
            notification_type="fruit_recommendation"
        )
        
        if options['dry_run']:
            self.stdout.write(f"DRY RUN: Found {due_notifications.count()} notifications due for processing")
            for notification in due_notifications:
                self.stdout.write(
                    f"Would process: {notification.account.userinfo_id.firstname} "
                    f"{notification.account.userinfo_id.lastname} - {notification.message[:50]}..."
                )
            return
        
        processed_count = 0
        for notification in due_notifications:
            try:
                # Mark the notification as "delivered" by updating created_at to current time
                # This makes it appear in the user's notification list
                notification.created_at = current_time
                notification.save()
                
                processed_count += 1
                self.stdout.write(
                    f"Processed notification for {notification.account.userinfo_id.firstname} "
                    f"{notification.account.userinfo_id.lastname}"
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing notification {notification.id}: {e}"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed {processed_count} scheduled notifications"
            )
        )