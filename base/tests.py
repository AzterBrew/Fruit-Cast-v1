from django.test import TestCase
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import *
from dashboard.models import Notification
from .views import schedule_monthly_fruit_recommendations


class FruitRecommendationNotificationTest(TestCase):
    
    def setUp(self):
        """Set up test data"""
        # Create basic test data
        self.account_type = AccountType.objects.create(account_type="Farmer")
        self.account_status = AccountStatus.objects.create(acc_status="Active")
        self.municipality = MunicipalityName.objects.create(municipality="Test Municipality")
        self.barangay = BarangayName.objects.create(barangay="Test Barangay", municipality_id=self.municipality)
        
        # Create user and account
        self.user_info = UserInformation.objects.create(
            lastname="Test",
            firstname="User",
            sex="Male",
            contact_number="1234567890",
            user_email="test@example.com",
            birthdate="1990-01-01",
            emergency_contact_person="Emergency Contact",
            emergency_contact_number="0987654321",
            address_details="Test Address",
            barangay_id=self.barangay,
            municipality_id=self.municipality,
            religion="Catholic",
            civil_status="Single"
        )
        
        self.account = AccountsInformation.objects.create(
            account_register_date=timezone.now(),
            account_type_id=self.account_type,
            acc_status_id=self.account_status,
            userinfo_id=self.user_info
        )
        
        # Create farmland
        self.farmland = FarmLand.objects.create(
            farmland_name="Test Farm",
            userinfo_id=self.user_info,
            municipality=self.municipality,
            barangay=self.barangay,
            estimated_area=5.0
        )
    
    def test_schedule_monthly_fruit_recommendations(self):
        """Test that fruit recommendation notifications are scheduled correctly"""
        # Call the function
        schedule_monthly_fruit_recommendations(self.account, self.municipality.municipality_id)
        
        # Check if notification was created
        notifications = Notification.objects.filter(
            account=self.account,
            notification_type="fruit_recommendation"
        )
        
        # Should have at least one notification scheduled for next month
        self.assertTrue(notifications.exists(), "No fruit recommendation notification was created")
        
        notification = notifications.first()
        next_month = timezone.now() + relativedelta(months=1)
        expected_date = next_month.replace(day=1, hour=8, minute=0, second=0, microsecond=0)
        
        # Check if scheduled for next month
        self.assertEqual(notification.scheduled_for.month, expected_date.month)
        self.assertEqual(notification.scheduled_for.year, expected_date.year)
        self.assertEqual(notification.scheduled_for.day, 1)
        self.assertEqual(notification.scheduled_for.hour, 8)
        
        # Check if message contains municipality name
        self.assertIn(self.municipality.municipality, notification.message)
        self.assertEqual(notification.notification_type, "fruit_recommendation")
        
    def test_no_duplicate_notifications(self):
        """Test that duplicate notifications for the same month/municipality are not created"""
        # Schedule notifications twice
        schedule_monthly_fruit_recommendations(self.account, self.municipality.municipality_id)
        schedule_monthly_fruit_recommendations(self.account, self.municipality.municipality_id)
        
        # Should only have one notification for this month/municipality combination
        next_month = timezone.now() + relativedelta(months=1)
        notifications = Notification.objects.filter(
            account=self.account,
            notification_type="fruit_recommendation",
            scheduled_for__month=next_month.month,
            scheduled_for__year=next_month.year,
            message__icontains=self.municipality.municipality
        )
        
        self.assertEqual(notifications.count(), 1, "Duplicate notifications were created")


# Create your tests here.
