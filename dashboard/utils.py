from datetime import datetime
from django.utils import timezone
from django.db.models import OuterRef, Subquery, Max
from base.models import CommodityType, UnitMeasurement, Month


def get_latest_forecasts_by_combination(base_queryset):
    """
    Get the latest forecast for each commodity-municipality-month-year combination
    regardless of batch. This ensures that selective retraining doesn't hide
    forecasts from older batches.
    
    Args:
        base_queryset: Base ForecastResult queryset with initial filters
        
    Returns:
        Queryset with only the latest forecast for each combination
    """
    from dashboard.models import ForecastResult
    
    # Get the latest batch generation date for each unique combination
    latest_batch_for_combination = ForecastResult.objects.filter(
        commodity=OuterRef('commodity'),
        municipality=OuterRef('municipality'),
        forecast_month=OuterRef('forecast_month'),
        forecast_year=OuterRef('forecast_year')
    ).order_by('-batch__generated_at').values('batch__generated_at')[:1]
    
    # Filter base queryset to only include records with the latest batch date for each combination
    return base_queryset.filter(
        batch__generated_at=Subquery(latest_batch_for_combination)
    )


# GENERATING THESIS2 COMMODITY TYPE MODEL

# Define your fruits and their properties
# fruits = [
#     {
#         "name": "Mango",
#         "average_weight_per_unit_kg": 0.25,
#         "unit_abrv": "kg",
#         "seasonal_months": ["March", "April", "May", "June"]
#     },
#     {
#         "name": "Banana",
#         "average_weight_per_unit_kg": 0.15,
#         "unit_abrv": "kg",
#         "seasonal_months": [m for m in [
#             "January", "February", "March", "April", "May", "June",
#             "July", "August", "September", "October", "November", "December"
#         ]]
#     },
#     {
#         "name": "Papaya",
#         "average_weight_per_unit_kg": 1.2,
#         "unit_abrv": "kg",
#         "seasonal_months": [m for m in [
#             "January", "February", "March", "April", "May", "June",
#             "July", "August", "September", "October", "November", "December"
#         ]]
#     },
#     {
#         "name": "Pineapple",
#         "average_weight_per_unit_kg": 1.5,
#         "unit_abrv": "kg",
#         "seasonal_months": ["March", "April", "May", "June"]
#     },
#     {
#         "name": "Lanzones",
#         "average_weight_per_unit_kg": 0.02,
#         "unit_abrv": "kg",
#         "seasonal_months": ["September", "October", "November"]
#     },
#     {
#         "name": "Rambutan",
#         "average_weight_per_unit_kg": 0.03,
#         "unit_abrv": "kg",
#         "seasonal_months": ["August", "September", "October"]
#     },
#     {
#         "name": "Guava",
#         "average_weight_per_unit_kg": 0.2,
#         "unit_abrv": "kg",
#         "seasonal_months": ["August", "September", "October"]
#     },
#     {
#         "name": "Durian",
#         "average_weight_per_unit_kg": 1.5,
#         "unit_abrv": "kg",
#         "seasonal_months": ["August", "September", "October"]
#     },
#     {
#         "name": "Mangosteen",
#         "average_weight_per_unit_kg": 0.08,
#         "unit_abrv": "kg",
#         "seasonal_months": ["July", "August", "September"]
#     },
#     {
#         "name": "Calamansi",
#         "average_weight_per_unit_kg": 0.005,
#         "unit_abrv": "kg",
#         "seasonal_months": ["August", "September", "October"]
#     },
#     {
#         "name": "Watermelon",
#         "average_weight_per_unit_kg": 2.5,
#         "unit_abrv": "kg",
#         "seasonal_months": ["March", "April", "May", "June", "July"]
#     },
#     {
#         "name": "Avocado",
#         "average_weight_per_unit_kg": 0.3,
#         "unit_abrv": "kg",
#         "seasonal_months": ["July", "August", "September"]
#     },
#     {
#         "name": "Pomelo",
#         "average_weight_per_unit_kg": 1.0,
#         "unit_abrv": "kg",
#         "seasonal_months": ["August", "September", "October"]
#     },
# ]

# def populate_commodity_types():
#     for fruit in fruits:
#         unit = UnitMeasurement.objects.get(unit_abrv=fruit["unit_abrv"])
#         commodity, created = CommodityType.objects.get_or_create(
#             name=fruit["name"],
#             defaults={
#                 "average_weight_per_unit_kg": fruit["average_weight_per_unit_kg"],
#                 "unit": unit,
#             }
#         )
#         if not created:
#             commodity.average_weight_per_unit_kg = fruit["average_weight_per_unit_kg"]
#             commodity.unit = unit
#             commodity.save()
#         # Set seasonal months
#         months = Month.objects.filter(name__in=fruit["seasonal_months"])
#         commodity.seasonal_months.set(months)
#         commodity.save()
#         print(f"{'Created' if created else 'Updated'}: {commodity.name}")

# END OF COMMODITY TYPE SCRIPT


# GENERATING THE THESIS2 VERIFIED RECORDS WITH COMMODITY TYPE NOT CONNECTED TO INITPLATNRECORD AND INITHARVESTRECORD

from dashboard.models import VerifiedPlantRecord, VerifiedHarvestRecord
from base.models import MunicipalityName, BarangayName
import random
from datetime import timedelta

def generate_verified_records():
    commodities = list(CommodityType.objects.all())
    municipalities = list(MunicipalityName.objects.all())
    barangays = list(BarangayName.objects.all())

    if not commodities or not municipalities or not barangays:
        print("Populate CommodityType, MunicipalityName, and BarangayName first.")
        return

    # Generate 100 VerifiedPlantRecord
    for i in range(100):
        commodity = random.choice(commodities)
        municipality = random.choice(municipalities)
        # Pick a barangay that belongs to the selected municipality
        barangay_choices = [b for b in barangays if b.municipality_id == municipality]
        barangay = random.choice(barangay_choices) if barangay_choices else random.choice(barangays)

        min_expected = random.randint(100, 500)
        max_expected = min_expected + random.randint(50, 200)
        average_units = (min_expected + max_expected) / 2
        estimated_weight = average_units * float(commodity.average_weight_per_unit_kg)

        VerifiedPlantRecord.objects.create(
            plant_date=timezone.now().date() - timedelta(days=random.randint(0, 730)),
            commodity_id=commodity,
            min_expected_harvest=min_expected,
            max_expected_harvest=max_expected,
            average_harvest_units=average_units,
            estimated_weight_kg=estimated_weight,
            remarks="Auto-generated record.",
            date_verified=timezone.now(),
            municipality=municipality,
            barangay=barangay,
            # prev_record left as None
        )
        print(f"Created VerifiedPlantRecord {i+1}/100")

    # Generate 100 VerifiedHarvestRecord
    for i in range(100):
        commodity = random.choice(commodities)
        municipality = random.choice(municipalities)
        barangay_choices = [b for b in barangays if b.municipality_id == municipality]
        barangay = random.choice(barangay_choices) if barangay_choices else random.choice(barangays)

        total_weight = round(random.uniform(100, 1000), 2)
        weight_per_unit = float(commodity.average_weight_per_unit_kg) or 1.0

        VerifiedHarvestRecord.objects.create(
            harvest_date=timezone.now().date() - timedelta(days=random.randint(0, 730)),
            commodity_id=commodity,
            total_weight_kg=total_weight,
            weight_per_unit_kg=weight_per_unit,
            remarks="Auto-generated record.",
            date_verified=timezone.now(),
            municipality=municipality,
            barangay=barangay,
            # prev_record left as None
        )
        print(f"Created VerifiedHarvestRecord {i+1}/100")

# To run:
# from dashboard.utils import generate_verified_records
# generate_verified_records()



# GENERATING THE THESIS1 VERIFIED RECORDS AND COMMODITY TYPE
# fruit_seasons = {
#     "Mango": ("March", "June"),
#     "Banana": ("All Year", "All Year"),
#     "Papaya": ("All Year", "All Year"),
#     "Pineapple": ("March", "June"),
#     "Lanzones": ("September", "November"),
#     "Rambutan": ("August", "October"),
#     "Guava": ("August", "October"),
#     "Durian": ("August", "October"),
#     "Mangosteen": ("July", "September"),
#     "Calamansi": ("August", "October"),
#     "Watermelon": ("March", "July"),
#     "Avocado": ("July", "September"),
#     "Pomelo": ("August", "October"),
# }

# def get_current_month():
#     return datetime.now().strftime('%B')

# def is_in_season(commodity, month):
#     season = fruit_seasons.get(commodity)
#     if not season:
#         return False
#     if season[0] == "All Year":
#         return True
#     start, end = [datetime.strptime(m, "%B").month for m in season]
#     current_month = datetime.strptime(month, "%B").month

#     if start <= end:
#         return start <= current_month <= end
#     else:
#         return current_month >= start or current_month <= end

# def generate_notifications(crops):
#     """Generate a list of notifications for the user based on their crops and seasonality."""
#     current_month = get_current_month()

#     # Get commodity types and their seasonal months
#     commodity_seasons = {}
#     for commodity in CommodityType.objects.all():
#         commodity_seasons[commodity.name] = commodity.seasonal_months.values_list('number', flat=True)

#     notifications = []

#     for crop in crops:
#         in_season = current_month in commodity_seasons.get(crop, [])
#         alternatives = [
#             fruit for fruit, months in commodity_seasons.items()
#             if fruit != crop and current_month in months
#         ]

#         notifications.append({
#             'crop': crop,
#             'in_season': in_season,
#             'current_month': current_month,
#             'alternatives': alternatives,
#         })

#     return notifications

# END OF THESIS1 VERIFIED RECORD GENERATOR




# MAKING THE SUPERUSER A RECORD IN THE TABLES 

# for making superuser a record in userinformation and accountsinformation tables

# from base.models import AuthUser
# from base.models import UserInformation, AccountsInformation, AccountType, AccountStatus, BarangayName, MunicipalityName, AdminInformation
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


# TRUNCATING THE TABLE SELECTED
# for truncating a table 
# from django.db import connection
# with connection.cursor() as cursor:
#     cursor.execute("TRUNCATE TABLE base_authuser RESTART IDENTITY CASCADE;")

# SQL QUERY FOR THE COMMODITY TYPE
# SELECT *
# FROM base_commoditytype c
# JOIN base_commoditytype_seasonal_months m2m ON c.commodity_id = m2m.commoditytype_id
# JOIN base_month m ON m2m.month_id = m.month_id
# -- WHERE m.name = 'August';
# GROUP BY m.month_id, c.commodity_id, m2m.id
# ORDER BY m.month_id