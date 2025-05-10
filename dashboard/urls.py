
from django.urls import path, include
from . import views #importing from files, in this case, my views python file
from django.contrib.auth import views as auth_views
from .views import *
#authview and home r functions i imported from views.py 

app_name = 'dashboard'

urlpatterns = [
    path('', home, name='home'),
    path('forecast/', forecast, name="forecast"),
    path('monitor/', monitor, name="monitor"),

]
 