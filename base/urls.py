
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
    path('get-barangays/<int:municipality_id>/', views.get_barangays, name='get_barangays'),
    path('register/email/', views.register_email, name='register_email'),
    path('register/email/verify/', views.register_verify_code, name='register_verify_code'),
    path('register/step1/', views.register_step1, name='register_step1'),
    path('register/step2/', views.register_step2, name='register_step2'),
    path('register/cancel/', views.cancel_registration, name='cancel_registration'),
    # Forgot Password URLs
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-password/verify/', views.forgot_password_verify, name='forgot_password_verify'),
    path('reset-password/', views.reset_password, name='reset_password'),
    # Change Password URLs
    path('change-password/', views.change_password, name='change_password'),
    path('change-password/verify/', views.change_password_verify, name='change_password_verify'),
    path('change-password/new/', views.change_password_new, name='change_password_new'),
    # path('signup/', register_step1, name='registerauth'),
    path('login/', custom_login, name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    # path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/login/success/', views.login_success, name='login_success'),
    # path('login/', include('loginpage.urls'))
    # path('accountinfo/', accinfo, name="accinfo"),
    # path('accountinfo/edit/', editacc, name="editacc"),
    path('forecast/', forecast, name="forecast"),
    path('monitor/', monitor, name="monitor"),
    path('aboutus/', about, name="about"),
    path('farmerrecords/', newrecord, name="newrecord"),

    path('farmerrecords/harvest/finalize', finalize_transaction, name="finalize_transaction"),
    path('transactions/farmland-record/', views.farmland_record_view, name='farmland_record'),
    path('transactions/farmland-record/<int:farminfo_id>/edit/', views.farmland_record_edit_view, name='farmland_edit'),
    path('transactions/plant-record/', views.plant_record_view, name='plant_record'),
    path('transactions/harvest-record/', views.solo_harvest_record_view, name='solo_harvest_record'),
    path('transactions/harvest-record/<int:transaction_id>/', views.harvest_record_for_plant_view, name='harvest_record_for_plant'),
    path('transaction-recordlist/<int:transaction_id>/', views.transaction_recordlist, name='transaction_recordlist'),
    path('get-barangays/', views.get_barangays, name='get_barangays'),
    path('accountpanel/', views.account_panel_view, name='account_info_panel'),
    path('accountpanel/edit/', views.account_edit_view, name='account_edit_panel'),
    path('accountpanel/farmland/', views.farmland_owned_view, name='farmland_owned'),

    path('record/remove/<int:index>/', views.remove_pending_record, name='remove_pending_record'), #index ng pending record since saved as array lang sha, not in the db
    path('record/edit/<int:index>/', views.edit_pending_record, name='edit_pending_record'),
    path('transaction/history/', views.transaction_history, name='transaction_history'),
    path('transaction/history/<int:transaction_id>', views.transaction_recordhistory, name='transaction_recordhistory'),
    path('api/get-recommendations/', views.get_recommendations_api, name='get_recommendations_api'),    
]
 