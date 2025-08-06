from django.contrib import admin
from .models import *

# Register your models here.

# super user : moa-emms
# pass : opaemmsumbad
admin.site.register(AuthUser)
admin.site.register(AccountType)
admin.site.register(AccountStatus)
admin.site.register(MunicipalityName)
admin.site.register(BarangayName)
admin.site.register(UserInformation)
admin.site.register(AdminInformation)
admin.site.register(AccountsInformation)
admin.site.register(UserLoginLog)
admin.site.register(AdminUserManagement)
admin.site.register(FarmLand)
admin.site.register(Month)
admin.site.register(UnitMeasurement)
admin.site.register(CommodityType)
admin.site.register(RecordTransaction)
admin.site.register(initPlantRecord)
admin.site.register(initHarvestRecord)