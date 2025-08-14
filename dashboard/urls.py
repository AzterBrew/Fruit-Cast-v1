
from django.urls import path, include
from . import views #importing from files, in this case, my views python file
from django.contrib.auth import views as auth_views
from .views import *
#authview and home r functions i imported from views.py 

app_name = 'dashboard'

urlpatterns = [
    # path('', home, name='home'),
    path('forecast/', forecast, name="forecast"),
    path('forecast/download_csv/', views.forecast_csv, name='forecast_csv'),
    path('forecast/bycommodity/', views.forecast_bycommodity, name='forecast_bycommodity'),
    path('monitor/', monitor, name="monitor"),
    path('notifications/', notifications, name='notifications'),
    path('mark-notification-read/', views.mark_notification_read, name='mark_notification_read'),
]
 