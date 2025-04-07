from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.forms import inlineformset_factory
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

# Create your views here.
from .models import *
# from .forms import OrderForm
# from .filters import OrderFilter

@login_required
# def homeguest(request):
#     return render(request, 'home.html', {})

# def homeuser(request):
#     return render(request,'loggedin/home.html', {})

def home(request):
    print("🔥 DEBUG: Home view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        return render(request, 'loggedin/home.html', {})
    else:        
        return render(request, 'home.html', {})

def accinfo(request):
    if request.user.is_authenticated: 
        return render(request, 'loggedin/account_info.html', {})
    else :
        return render(request, 'home.html', {})        

def about(request):
    if request.user.is_authenticated: 
        return render(request, 'loggedin/about.html', {})
    else :
        return render(request, 'about.html', {})  

def login_success(request):
    print("🔥 Login successful! Redirecting...")  # Debugging log
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        return render(request, 'loggedin/home.html', {})
    else:        
        return render(request, 'home.html', {})
    # return redirect("base:home")  
    # Redirect to home *manually*

def registerauth(request):
    form = UserCreationForm()
    
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('base:login')
    
    context = {'form': form}
    return render(request, 'registration/signup.html', context)
    
def loginauth(request):
    if request.method=="POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('base:home')
        else :
            messages.info(request, 'user or pass incrrect')
    
    context = {}
    return render(request, 'login.html',context)
    
    


# def authView(request):
#     if request.method == "POST":
#         form = UserCreationForm(request.POST or None)
#         if form.is_valid():
#             form.save()
#             return redirect("base:login")
#     else : 
#         form = UserCreationForm()
#     return render(request, 'registration/signup.html', {'form' : form})

