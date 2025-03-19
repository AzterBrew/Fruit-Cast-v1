
from django.urls import path, include
from . import views #importing from files, in this case, my views python file
from django.contrib.auth import views as auth_views
from .views import authView, home
#authview and home r functions i imported from views.py 

app_name = 'base'

urlpatterns = [
    path('', home, name='home'),
    path('signup/', authView, name='authView'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    # path('login/', include('loginpage.urls'))
]
 