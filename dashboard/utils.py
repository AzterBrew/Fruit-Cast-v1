from datetime import datetime
from base.models import CommodityType
from django.utils import timezone

fruit_seasons = {
    "Mango": ("March", "June"),
    "Banana": ("All Year", "All Year"),
    "Papaya": ("All Year", "All Year"),
    "Pineapple": ("March", "June"),
    "Lanzones": ("September", "November"),
    "Rambutan": ("August", "October"),
    "Guava": ("August", "October"),
    "Durian": ("August", "October"),
    "Mangosteen": ("July", "September"),
    "Calamansi": ("August", "October"),
    "Watermelon": ("March", "July"),
    "Avocado": ("July", "September"),
    "Pomelo": ("August", "October"),
}

def get_current_month():
    return datetime.now().strftime('%B')

def is_in_season(commodity, month):
    season = fruit_seasons.get(commodity)
    if not season:
        return False
    if season[0] == "All Year":
        return True
    start, end = [datetime.strptime(m, "%B").month for m in season]
    current_month = datetime.strptime(month, "%B").month

    if start <= end:
        return start <= current_month <= end
    else:
        return current_month >= start or current_month <= end

def generate_notifications(crops):
    """Generate a list of notifications for the user based on their crops and seasonality."""
    current_month = get_current_month()

    # Get commodity types and their seasonal months
    commodity_seasons = {}
    for commodity in CommodityType.objects.all():
        commodity_seasons[commodity.name] = commodity.seasonal_months.values_list('number', flat=True)

    notifications = []

    for crop in crops:
        in_season = current_month in commodity_seasons.get(crop, [])
        alternatives = [
            fruit for fruit, months in commodity_seasons.items()
            if fruit != crop and current_month in months
        ]

        notifications.append({
            'crop': crop,
            'in_season': in_season,
            'current_month': current_month,
            'alternatives': alternatives,
        })

    return notifications


# for making superuser a record in userinformation and accountsinformation tables

# from base.models import AuthUser
# from base.models import UserInformation, AccountsInformation, AccountType, AccountStatus, BarangayName, MunicipalityName 
# from django.utils import timezone
# from django.utils.timezone import now

# superuser = AuthUser.objects.get(email='emmsumbad@bpsu.edu.ph')

# admin_type = AccountType.objects.get(account_type='Administrator')  # adjust as needed
# active_status = AccountStatus.objects.get(pk=2)  #Verified value in the table
# barangay = BarangayName.objects.get(pk=1)
# municipality = MunicipalityName.objects.get(pk=1)
# municipality_assigned = MunicipalityName.objects.get(pk=13)  #overall - value

# userinfo = UserInformation.objects.create(
#     auth_user=superuser,
#     firstname='Admin',
#     lastname='User',
#     middlename='',
#     nameextension='',
#     sex='',  # 'Male' or 'Female'
#     contact_number='+639123456789',
#     user_email=superuser.email,
#     birthdate='1950-01-01',  # YYYY-MM-DD format
#     emergency_contact_person='Jane Doe',
#     emergency_contact_number='09123456788',
#     address_details='123 Admin St.',
#     barangay_id=barangay,
#     municipality_id=municipality,
#     religion='None',
#     civil_status='Single',
# )

# account_info = AccountsInformation.objects.create(
#     userinfo_id=userinfo,
#     account_type_id=admin_type,
#     acc_status_id=active_status,
#     account_isverified=True,
#     account_register_date=timezone.now(),  # sets to current timestamp in your timezone    
# )
# admin_info = AdminInformation.objects.create(
#     userinfo_id=userinfo,
#     municipality_incharge=municipality_assigned,
# )


# for truncating a table 
# from django.db import connection
# with connection.cursor() as cursor:
#     cursor.execute("TRUNCATE TABLE base_authuser RESTART IDENTITY CASCADE;")