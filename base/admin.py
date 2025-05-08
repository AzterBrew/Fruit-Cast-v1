from django.contrib import admin
from .models import *

# Register your models here.

# super user : moa-emms
# pass : opaemmsumbad
admin.site.register(AuthUser)
admin.site.register(Transaction)
admin.site.register(AccountsInformation)
admin.site.register(AdminInformation)
admin.site.register(UserInformation)
admin.site.register(ItemStatus)
admin.site.register(AccountType)
admin.site.register(PlantRecord)
admin.site.register(HarvestRecord)
admin.site.register(UserLoginLog)