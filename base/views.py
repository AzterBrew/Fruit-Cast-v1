from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.forms import inlineformset_factory
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import CustomUserCreationForm  # make sure this is imported

from .models import *


# @login_required > btw i made this not required so that it doesn't require the usr to login just to view the home page


def home(request):
    print("🔥 DEBUG: Home view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        return render(request, 'loggedin/home.html', {})
    else:        
        return render(request, 'home.html', {})

def accinfo(request):
    print("🔥 DEBUG: account view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        return render(request, 'loggedin/account_info.html', {})
    else :
        return render(request, 'home.html', {})        

def forecast(request):
    print("🔥 DEBUG: forecast view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        return render(request, 'loggedin/forecast.html', {})
    else :
        return render(request, 'home.html', {})  

def about(request):
    print("🔥 DEBUG: about view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
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
    form = CustomUserCreationForm()
    
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('base:login')
    
    context = {'form': form}
    return render(request, 'registration/signup.html', context)
    
# def loginauth(request):
#     if request.method=="POST":
#         username = request.POST.get('username')
#         password = request.POST.get('password')
        
#         user = authenticate(request, username=username, password=password)
        
#         if user is not None:
#             login(request, user)
#             return redirect('base:home')
#         else :
#             messages.error(request, 'user or pass incorrect')
    
#     context = {}
#     return render(request, 'login.html',context)
 
def custom_login(request):
    if request.method == 'POST':
        contact = request.POST['email_or_contact']
        password = request.POST['password']

        print("🔥 Login processing...")  # Debugging log
        print("🔥 DEBUG: POST Data ->", request.POST)

        # Check if the input is a numeric phone number or an email
        try:
            if contact.isdigit():  # If it's a number, use PhoneAuthBackend
                user = authenticate(request, username=contact, password=password)  
            else:  # Otherwise, use EmailAuthBackend
                user = authenticate(request, username=contact, password=password)  

            if user is not None:
                login(request, user)
                # messages.success(request, 'You are now logged in!') 
                print("🔥 Logged IN...")  # Debugging log
                
                return redirect('base:home')
            else:
                messages.error(request, 'Invalid email/phone or password.')  
                print("🔥 Login failed...")  # Debugging log
                
        except ValueError:
            messages.error(request, "Invalid input for phone number.")

        return render(request, 'registration/login.html')

    return render(request, 'registration/login.html')
    
# def custom_login(request):
#     if request.method == 'POST':
#         contact = request.POST['email_or_contact']
#         password = request.POST['password']
#         if contact.isdigit():
#             user = authenticate(request, username=contact, password=password)  # Phone login
#         else:
#             user = authenticate(request, username=contact, password=password)  # Email login

#         print("🔥 Login processing...")  # Debugging log
#         print("🔥 DEBUG: POST Data ->", request.POST)
#         if user is not None:
#             login(request, user)
#             messages.success(request, 'You are now logged in!') 
#             print("🔥 Logged IN...")  # Debugging log
                       
#             return redirect('base:home')
#         else:
#             messages.error(request, 'Invalid email/phone or password.')  
#             print("🔥 Login failed...")  # Debugging log
                      
#             return render(request, 'registration/login.html')
#     return render(request, 'registration/login.html')    


# def authView(request):
#     if request.method == "POST":
#         form = UserCreationForm(request.POST or None)
#         if form.is_valid():
#             form.save()
#             return redirect("base:login")
#     else : 
#         form = UserCreationForm()
#     return render(request, 'registration/signup.html', {'form' : form})

