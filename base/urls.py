
from django.urls import path, include
from . import views #importing from files, in this case, my views python file
from django.contrib.auth import views as auth_views
from .views import *
#authview and home r functions i imported from views.py 

app_name = 'base'

urlpatterns = [
    # path('', homeuser, name='homeuser'),
    # path('', homeguest, name='homeguest'),
    path('', home, name='home'),
    path('signup/', registerauth, name='registerauth'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    # path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/login/success/', views.login_success, name='login_success'),
    # path('login/', include('loginpage.urls'))
    path('accountinfo/', accinfo, name="accinfo"),
    path('aboutus/', about, name="about")
]
 