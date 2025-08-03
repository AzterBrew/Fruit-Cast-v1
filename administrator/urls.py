from django.urls import path
from . import views

app_name = 'administrator'


urlpatterns = [
    path('login/', views.admin_login, name='admin_login'),
    path('dashboard/', views.admin_dashboard, name='dashboard'),
    path('verify_accounts/', views.verify_accounts, name='verify_accounts'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    # path('verify-account/<int:account_id>/', views.verify_account_action, name='verify_account_action'),
    path('show_allaccounts/', views.show_allaccounts, name='show_allaccounts'),
    path('update_account_status/<int:account_id>/', views.update_account_status, name='update_account_status'),
    # path('manage_users/', views.manage_users, name='manage_users'),
    # path('verify_records/', views.verify_records, name='verify_records'),
    # path('generate_report/', views.generate_report, name='generate_report'),
]