from django.urls import path
from . import views
from .views import *

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
    # path('verify_records/', views.verify_records, name='verify_records'),
    # path('generate_report/', views.generate_report, name='generate_report'),
    path('accountinfo/', accinfo, name="accinfo"),
    path('accountinfo/edit', editacc, name="editacc"),
]