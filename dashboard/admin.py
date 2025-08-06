from django.contrib import admin
from .models import *
# Register your models here.

# admin.site.register(Month)
# admin.site.register(CommodityType)
admin.site.register(VerifiedHarvestRecord)
admin.site.register(VerifiedPlantRecord)
admin.site.register(Notification)
admin.site.register(ForecastResult)
