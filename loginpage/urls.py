from django.urls import path, include
from . import views #importing from files, in this case, my views python file

app_name = 'loginpage'

urlpatterns = [
    path('', views.login_view, name="login")
]
