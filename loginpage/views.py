from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

# Create your views here.
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            #login here daw
            return redirect("login")
    else :
        form = AuthenticationForm()
    return render(request, 'login.html', {"form" : form})