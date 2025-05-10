
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
    path('register/step1/', views.register_step1, name='register_step1'),
    path('register/step2/', views.register_step2, name='register_step2'),
    # path('signup/', register_step1, name='registerauth'),
    path('login/', custom_login, name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    # path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/login/success/', views.login_success, name='login_success'),

    # path('login/', include('loginpage.urls'))
    path('accountinfo/', accinfo, name="accinfo"),
    path('accountinfo/edit', editacc, name="editacc"),
    path('forecast/', forecast, name="forecast"),
    path('monitor/', monitor, name="monitor"),
    path('aboutus/', about, name="about"),
    path('newrecord/', newrecord, name="newrecord"),
    # path('newrecord/harvest', harvestrecord, name="harvestrecord"),
    # path('newrecord/plant', plantrecord, name="plantrecord"),
    path('newrecord/harvest/finalize', finalize_transaction, name="finalize_transaction"),
    # path('newrecord/harvest/review', transaction_recordlist, name="transaction_recordlist"),
    
    
    path('record/remove/<int:index>/', views.remove_pending_record, name='remove_pending_record'), #index ng pending record since saved as array lang sha, not in the db
    path('record/edit/<int:index>/', views.edit_pending_record, name='edit_pending_record'),
    path('transaction/history/', views.transaction_history, name='transaction_history'),
    path('transaction/history/<int:transaction_id>', views.transaction_recordhistory, name='transaction_recordhistory'),

]
 