from django.urls import path
from . import views
from .views import *
from base.views import get_barangays

app_name = 'administrator'


urlpatterns = [
    path('login/', admin_login, name='admin_login'),
    path('dashboard/', admin_dashboard, name='dashboard'),
    path('verify_accounts/', verify_accounts, name='verify_accounts'),
    path('admin_dashboard/', admin_dashboard, name='admin_dashboard'),
    path('verify-account/<int:account_id>/', views.verify_account_action, name='verify_account_action'),
    path('show_allaccounts/', show_allaccounts, name='show_allaccounts'),
    path('change_account_type/<int:account_id>/', views.change_account_type, name='change_account_type'),    
    path('update_account_status/<int:account_id>/', update_account_status, name='update_account_status'),
    path('assign_account/', assign_account, name='assign_account'),
    # path('manage_users/', views.manage_users, name='manage_users'),
    path('verify_records/plant', views.admin_verifyplantrec, name='admin_verifyplantrec'),
    path('verify_records/harvest', views.admin_verifyharvestrec, name='admin_verifyharvestrec'),
    path('verify_records/harvest/add', views.admin_add_verifyharvestrec, name='admin_add_verifyharvestrec'),
    # path('generate_report/', views.generate_report, name='generate_report'),
    path('accountinfo/', accinfo, name="accinfo"),
    path('accountinfo/edit', editacc, name="editacc"),
    path('admin-forecast/', views.admin_forecast, name='admin_forecast'),
    path('save-admin-forecast/', views.save_admin_forecast, name='save_admin_forecast'),
    path('generate-all-forecasts/', views.generate_all_forecasts, name='generate_all_forecasts'),
    path('admin-forecast/batch/<int:batch_id>/download_csv/', views.forecast_csv, name='forecast_csv'),
    path('admin-forecast/batches/', views.admin_forecastviewall, name='admin_forecastviewall'),
    path('admin-forecast/batch/<int:batch_id>/', views.admin_forecastbatchdetails, name='admin_forecastbatchdetails'),
    path('commodities/', views.admin_commodity_list, name='admin_commodity_list'),
    path('commodity/add/', views.admin_commodity_add_edit, name='admin_commodity_add'),
    path('commodity/<int:pk>/edit/', views.admin_commodity_add_edit, name='admin_commodity_edit'),
    path('get_barangays/<int:municipality_id>/', get_barangays, name='get_barangays'),
]