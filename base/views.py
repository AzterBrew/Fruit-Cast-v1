from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.forms import inlineformset_factory
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from datetime import date

#from .forms import CustomUserCreationForm  # make sure this is imported

from .models import *
from .forms import UserContactAndAccountForm, CustomUserInformationForm


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

# old register function

# def registerauth(request):
#     form = CustomUserCreationForm()
    
#     if request.method == "POST":
#         form = CustomUserCreationForm(request.POST)
#         if form.is_valid():
#             form.save()
#             return redirect('base:login')
    
#     context = {'form': form}
#     return render(request, 'registration/signup.html', context)

def register_step1(request):
    if request.method == "POST":
        form = CustomUserInformationForm(request.POST)
        if form.is_valid():
            # userinfo = form.save(commit=False)  # Don't save yet
            # userinfo.save()  # Save the first step of user info
            # request.session['userinfo_id'] = userinfo.id  # Store userinfo id in session
            # return redirect('register_step2')
            # request.session['step1_data'] = form.cleaned_data  # 🔐 Save input to session
            

        # Cleaned version of form data, with date fields converted to string
            step1_data = form.cleaned_data.copy()

            # Convert date objects to strings manually (you can also loop over fields to detect types, but this is safer & explicit)
            if isinstance(step1_data.get("birthdate"), date):
                step1_data["birthdate"] = step1_data["birthdate"].isoformat()

            request.session['step1_data'] = step1_data
            
            return redirect('base:register_step2')
    else:
        form = CustomUserInformationForm(initial=request.session.get('step1_data'))

    return render(request, 'registration/register_step1.html', {'form': form})

def register_step2(request):
    # if request.method == "POST":
    #     userinfo_id = request.session.get('userinfo_id')
    #     userinfo = UserInformation.objects.get(id=userinfo_id)

    #     form = UserContactAndAccountForm(request.POST)
    #     if form.is_valid():
    #         user = form.save(commit=False)
    #         userinfo.user_email = form.cleaned_data['user_email']
    #         userinfo.contact_number = form.cleaned_data['contact_number']
    #         userinfo.save()  # Save the additional user info

    #         # Create Account Information
    #         account_info = AccountsInformation.objects.create(
    #             userinfo_id=userinfo,
    #             account_register_date=form.cleaned_data['password1'],  # For example, password1 used here just for demonstration
    #             account_isverified=False,  # Set to False until verified by admin
    #         )

    #         # Create user in auth_user table
    #         auth_user = models.User.objects.create_user(username=userinfo.user_email, password=form.cleaned_data['password1'])
    #         login(request, auth_user)  # Log the user in
            
    #         return redirect('success')  # Redirect to success or homepage after registration
    # else:
    #     form = UserContactAndAccountForm()

    # return render(request, 'registration/register_step2.html', {'form': form})
    
    if 'step1_data' not in request.session:
        return redirect('base:register_step1')  # magredirect sa unang page so users wouldnt skip p1

    if request.method == "POST":
        form = UserContactAndAccountForm(request.POST)
        if form.is_valid():
            auth_user = AuthUser.objects.create_user(
                email=form.cleaned_data['user_email'],
                password=form.cleaned_data['password1']
            )

            # Merge and save UserInformation
            step1_data = request.session['step1_data']
            userinfo = UserInformation.objects.create(
                auth_user=auth_user,
                contact_number=form.cleaned_data['contact_number'],
                user_email=form.cleaned_data['user_email'],
                **step1_data  # merges all step 1 fields
            )

            del request.session['step1_data']  # 💣 clean up session
            return redirect('base:login')  # or wherever

    else:
        form = UserContactAndAccountForm()

    return render(request, 'registration/register_step2.html', {'form': form})



    
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

