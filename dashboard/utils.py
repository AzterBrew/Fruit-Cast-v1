from datetime import datetime
from dashboard.models import CommodityType, Month

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