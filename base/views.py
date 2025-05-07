from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.forms import inlineformset_factory
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from datetime import date
from decimal import Decimal
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.urls import reverse

#from .forms import CustomUserCreationForm  # make sure this is imported

from .models import *
from .forms import UserContactAndAccountForm, CustomUserInformationForm, EditUserInformation, HarvestRecordCreate


# @login_required > btw i made this not required so that it doesn't require the usr to login just to view the home page


def home(request):
    print("🔥 DEBUG: Home view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
        
            context = {
                'user_firstname' : userinfo.firstname,
            }            
            return render(request, 'loggedin/home.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')         
    else:        
        return render(request, 'home.html', {})
     

def forecast(request):
    print("🔥 DEBUG: forecast view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
        
            context = {
                'user_firstname' : userinfo.firstname,
            }            
            return render(request, 'loggedin/forecast.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')                
            
    else :
        return render(request, 'home.html', {})  


def newrecord(request):         #opreations ng saving ng records (pero di pa magrecord sa database mismo till masubmit as a whole transaction mismo)
    print("🔥 DEBUG: newrecord view called!")  
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            userinfo = UserInformation.objects.get(pk=userinfo_id)
            accountinfo = AccountsInformation.objects.get(pk=account_id)
            view_to_show = request.GET.get("view", "") #for showing another page within another page ()yung transaction and harves/plant

            form = None
            if view_to_show == "harvest":
                form = HarvestRecordCreate(request.POST or None)
                
                if request.method == "POST" and form.is_valid():
                    # Get the current list from session or empty list
                    pending_records = request.session.get('pending_harvest_records', [])
                    
                    # Serialize form data
                    record_data = form.cleaned_data.copy()
                    
                    for key, value in record_data.items():
                        if isinstance(value,date):
                            record_data[key] = value.isoformat() # Converts date to 'YYYY-MM-DD' string
                        if isinstance(value, Decimal):
                            record_data[key] = float(value)
                            
                    
                    pending_records.append(record_data)

                    # Save back to session
                    request.session['pending_harvest_records'] = pending_records
                    request.session.modified = True

                    return redirect(f"{reverse('base:newrecord')}?view=transaction_list")  # Create this URL/view

            from_transaction = request.GET.get("from") == "transaction"
            
            context = {
                'user_firstname': userinfo.firstname,
                'view_to_show': view_to_show,
                'form': form,
                'pending_records': request.session.get('pending_harvest_records',[]),
                'from_transaction' : from_transaction,
            }
            return render(request, 'loggedin/transaction/transaction.html', context)
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')
    else:
        return render(request, 'home.html', {})


def transaction_recordlist(request):
    if not request.user.is_authenticated:
        return redirect('base:home')

    pending_records = request.session.get('pending_harvest_records', [])
    userinfo_id = request.session.get('userinfo_id')
    userinfo = UserInformation.objects.get(pk=userinfo_id)

    context = {
        'pending_records': pending_records,
        'user_firstname': userinfo.firstname,
    }

    return render(request, 'loggedin/transaction/transaction_recordlist.html', context)


@require_POST
def finalize_transaction(request):
    if not request.user.is_authenticated:
        return redirect('base:home')

    account_id = request.session.get('account_id')
    userinfo_id = request.session.get('userinfo_id')
    accountinfo = AccountsInformation.objects.get(pk=account_id)
    userinfo = UserInformation.objects.get(pk=userinfo_id)
    
    records = request.session.get('pending_harvest_records', [])

    if not records:
        return redirect('base:transaction_recordlist')  # Nothing to save

    transaction = Transaction.objects.create(
        account_id=accountinfo,
        transaction_type="Harvest",
        notes="Submitted via transaction cart"
    )

    for data in records:
        HarvestRecord.objects.create(
            transaction_id=transaction,
            harvest_date=data['harvest_date'],
            commodity_type=data['commodity_type'],
            commodity_spec=data['commodity_spec'],
            total_weight=data['total_weight'],
            unit=data['unit'],
            harvest_location=data['harvest_location'],
            remarks=data.get('remarks', '')
        )

    # Clear session
    del request.session['pending_harvest_records']
    return redirect(f"{reverse('base:newrecord')}?view=choose")  # Or a success page


@require_POST
def remove_pending_record(request, index):
    if not request.user.is_authenticated:
        return redirect('base:home')

    pending_records = request.session.get('pending_harvest_records', [])
    if 0 <= index < len(pending_records):
        del pending_records[index]
        request.session['pending_harvest_records'] = pending_records
        request.session.modified = True

    return redirect(f"{reverse('base:newrecord')}?view=transaction_list")


def edit_pending_record(request, index):
    if not request.user.is_authenticated:
        return redirect('base:home')

    pending_records = request.session.get('pending_harvest_records', [])
    if index < 0 or index >= len(pending_records):
        return redirect(f"{reverse('base:newrecord')}?view=transaction_list")

    record_data = pending_records[index]

    # Convert stored ISO dates/strings back to usable values
    form = HarvestRecordCreate(initial=record_data)

    if request.method == "POST":
        form = HarvestRecordCreate(request.POST)
        if form.is_valid():
            updated_data = form.cleaned_data.copy()
            # Convert again
            for key, value in updated_data.items():
                if isinstance(value, date):
                    updated_data[key] = value.isoformat()
                if isinstance(value, Decimal):
                    updated_data[key] = float(value)
            pending_records[index] = updated_data
            request.session['pending_harvest_records'] = pending_records
            request.session.modified = True
            return redirect(f"{reverse('base:newrecord')}?view=transaction_list")
        
        
    from_transactionedit = request.GET.get("from") == "transactionedit"
    # Pass the same context you use in `newrecord`
    context = {
        'form': form,
        'view_to_show': 'harvest',
        'pending_records': pending_records,
        'from_transactionedit' : from_transactionedit,
    }
    return render(request, 'loggedin/transaction/transaction.html', context)



# def newrecord(request):           WORKING HARVESTRECORD SUBMISSION
#     print("🔥 DEBUG: newrecord view called!")  
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
#             accountinfo = AccountsInformation.objects.get(pk=account_id)
#             view_to_show = request.GET.get("view", "") #for showing another page within another page ()yung transaction and harves/plant

#             form = None
#             if view_to_show == "harvest":
#                 form = HarvestRecordCreate(request.POST or None)
                
#                 if request.method == "POST" and form.is_valid():
#                     transaction = Transaction.objects.create(
#                         account_id=accountinfo,
#                         transaction_type="Harvest",
#                         notes=form.cleaned_data.get("remarks","")
#                     ) 
                    
#                     harvest = form.save(commit=False)
#                     harvest.transaction_id = transaction
#                     harvest.user_info = userinfo
#                     harvest.save()
                    
#                     return redirect('base:home')  

#             context = {
#                 'user_firstname': userinfo.firstname,
#                 'view_to_show': view_to_show,
#                 'form': form,
#             }
#             return render(request, 'loggedin/transaction/transaction.html', context)
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('base:home')
#     else:
#         return render(request, 'home.html', {})


# def newrecord(request):     #e2 po for transaction / creating new records  ACTUALLY OLD VER
#     print("🔥 DEBUG: newrecord view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:            
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
            
#             view_to_show = request.GET.get("view", "") # for transaction na page, displaying other pages with include kineme
        
#             context = {
#                 'user_firstname' : userinfo.firstname,
#                 'view_to_show' : view_to_show,
#             }            
            
#             return render(request, 'loggedin/transaction/transaction.html', context)
        
#         else:
#             print("⚠️ account_id missing in session!")
#             return redirect('base:home')   
#     else :
#         return render(request, 'home.html', {}) 


# def harvestrecord(request):    OLD VERSION (nimove over to newrecord() kase i just included the harvestrecord.html within the transaciton.html, not redirected to the page, so this function isnt really happening)
#     print("🔥 DEBUG: newrecord harvest view called!")  # This should print when you visit "/"
#     print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
#     if request.user.is_authenticated: 
#         account_id = request.session.get('account_id')
#         userinfo_id = request.session.get('userinfo_id')
        
#         if userinfo_id and account_id:
#             userinfo = UserInformation.objects.get(pk=userinfo_id)
#             form = HarvestRecordCreate(request.POST or None)

#             if request.method == "POST" and form.is_valid():
#                 form.instance.user_info = userinfo  # Set FK if needed
#                 form.save()
#                 return redirect('some_success_url')  # TODO: change this
            
#             context = {
#                 'user_firstname': userinfo.firstname,
#                 'form': form
#             }

#             return render(request, 'loggedin/transaction/harvest_record.html', context)
#         else:
#             print("⚠️ account_id or userinfo_id missing in session!")
#             return redirect('base:home')   
#     else :
#         return render(request, 'home.html', {}) 


def plantrecord(request):
    print("🔥 DEBUG: newrecord view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
        
            context = {
                'user_firstname' : userinfo.firstname,
            }            
            return render(request, 'loggedin/transaction/plant_record.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home')   
    else :
        return render(request, 'home.html', {}) 


def about(request):
    print("🔥 DEBUG: about view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        return render(request, 'loggedin/about.html', {})
    else :
        return render(request, 'about.html', {})  


def editacc(request):
    print("🔥 DEBUG: editacc view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        userinfo_id = request.session.get('userinfo_id')
        userinfo = UserInformation.objects.get(pk=userinfo_id)
        
        context = {
                'user_firstname' : userinfo.firstname,
            } 
        
        if request.method == "POST":
            form = EditUserInformation(request.POST,instance=userinfo)
            if form.is_valid():
                updated_info = form.save(commit=False)
                updated_info.auth_user = request.user
                updated_info.save()
                
                request.user.email = updated_info.user_email
                request.user.save()
                
                return redirect('base:accinfo')                
        
        else:
            form = EditUserInformation(instance=userinfo)

        return render(request, 'loggedin/account_edit.html', {'form': form})
    else :
        return render(request, 'home.html', {})  


def accinfo(request):
    print("🔥 DEBUG: account view called!")  # This should print when you visit "/"
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
    if request.user.is_authenticated: 
        account_id = request.session.get('account_id')
        userinfo_id = request.session.get('userinfo_id')
        
        if userinfo_id and account_id:
            
            userinfo = UserInformation.objects.get(pk=userinfo_id)
        
            context = {
                'user_firstname' : userinfo.firstname,
                'user_middlename' : userinfo.middlename,
                'user_lastname' : userinfo.lastname,
                'user_nameext' : userinfo.nameextension,
                'user_sex' : userinfo.sex,
                'user_dob' : userinfo.birthdate,
                'user_emperson' : userinfo.emergency_contact_person,
                'user_emcontact' : userinfo.emergency_contact_number,
                'user_fulladdress' : userinfo.full_Address,
                'user_barangay' : userinfo.barangay,
                'user_municipality' : userinfo.municipality,
                'user_contactno' : userinfo.contact_number,
                'user_email' : userinfo.user_email
            }            
            return render(request, 'loggedin/account_info.html', context)
        
        else:
            print("⚠️ account_id missing in session!")
            return redirect('base:home') 
    else :
        return render(request, 'home.html', {})   
    

def login_success(request):
    print("🔥 Login successful! Redirecting...")  # Debugging log
    print(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        return render(request, 'loggedin/home.html', {})
    else:        
        return render(request, 'home.html', {})
    # return redirect("base:home")  
    # Redirect to home *manually*
    
def register_step1(request):
    if request.user.is_authenticated: 
        return render(request, 'loggedin/home.html', {})

    else:
        if request.method == "POST":
            form = CustomUserInformationForm(request.POST)
            if form.is_valid():
                step1_data = form.cleaned_data.copy()

                if isinstance(step1_data.get("birthdate"), date):
                    step1_data["birthdate"] = step1_data["birthdate"].isoformat()

                request.session['step1_data'] = step1_data
                
                return redirect('base:register_step2')
        else:
            form = CustomUserInformationForm(initial=request.session.get('step1_data'))

        return render(request, 'registration/register_step1.html', {'form': form})


def register_step2(request):
    
    if 'step1_data' not in request.session:
        return redirect('base:register_step1')  # magredirect sa unang page so users wouldnt skip p1

    if request.method == "POST":
        form = UserContactAndAccountForm(request.POST)
        if form.is_valid():
            auth_user = AuthUser.objects.create_user(
                email=form.cleaned_data['user_email'],
                password=form.cleaned_data['password1']
            )

            # Merge and save UserInformation na table
            step1_data = request.session['step1_data']
            userinfo = UserInformation.objects.create(
                auth_user=auth_user,
                contact_number=form.cleaned_data['contact_number'],
                user_email=form.cleaned_data['user_email'],
                full_Address=form.cleaned_data['full_Address'],
                emergency_contact_person=form.cleaned_data['emergency_contact_person'],
                emergency_contact_number=form.cleaned_data['emergency_contact_number'],
                **step1_data  # merges all step 1 fields
            )
            account_type_instance = AccountType.objects.get(account_type_id=1)
            account_status_instance = AccountStatus.objects.get(accstatus_id=1)

            AccountsInformation.objects.create(
                userinfo_id = userinfo,
                account_type_id = account_type_instance,
                account_status_id = account_status_instance,
                account_register_date = timezone.now()
            )

            del request.session['step1_data']  # delete sesh
            return redirect('base:login') 

    else:
        form = UserContactAndAccountForm()

    return render(request, 'registration/register_step2.html', {'form': form})

 
def custom_login(request):
    
    if request.method == 'POST':
        contact = request.POST['email_or_contact']
        password = request.POST['password']

        print("🔥 Login processing...")  
        print("🔥 DEBUG: POST Data ->", request.POST)

        # Check if the input is a numeric phone number or an email
        try:
            if contact.isdigit():  # If it's a number, use PhoneAuthBackend
                user = authenticate(request, username=contact, password=password)  
            else:  # Otherwise, use EmailAuthBackend
                user = authenticate(request, username=contact, password=password)  

            if user is not None:
                login(request, user)
                
                try:
                    user_info = UserInformation.objects.get(auth_user=request.user)
                    account_info = AccountsInformation.objects.get(userinfo_id__auth_user=user)
                    account_status = account_info.account_status_id
                    
                    UserLoginLog.objects.create(
                        account_id=account_info, 
                        account_status_id=account_status)
                    
                    request.session['account_id'] = account_info.account_id
                    request.session['userinfo_id'] = user_info.userinfo_id
                     
                    print("🔥 Logged IN...logged to userloginlog")  # Debugging log
                
                except AccountsInformation.DoesNotExist:
                    print("no acc info record for this user")
                    messages.error(request, 'Account not registered')  
                    
                return redirect('base:home')
            else:
                messages.error(request, 'Invalid email/phone or password.')  
                print("🔥 Login failed...")  # Debugging log
                
        except ValueError:
            messages.error(request, "Invalid input for phone number.")

        return render(request, 'registration/login.html')

    return render(request, 'registration/login.html')


# def registerauth(request):
#     form = CustomUserCreationForm()
    
#     if request.method == "POST":
#         form = CustomUserCreationForm(request.POST)
#         if form.is_valid():
#             form.save()
#             return redirect('base:login')
    
#     context = {'form': form}
#     return render(request, 'registration/signup.html', context)
    
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

# def register_step1(request):
#     if request.method == "POST":
#         form = CustomUserInformationForm(request.POST)
#         if form.is_valid():
#             # userinfo = form.save(commit=False)  # Don't save yet
#             # userinfo.save()  # Save the first step of user info
#             # request.session['userinfo_id'] = userinfo.id  # Store userinfo id in session
#             # return redirect('register_step2')
#             # request.session['step1_data'] = form.cleaned_data  # 🔐 Save input to session
            

#         # Cleaned version of form data, with date fields converted to string
#             step1_data = form.cleaned_data.copy()

#             # Convert date objects to strings manually (you can also loop over fields to detect types, but this is safer & explicit)
#             if isinstance(step1_data.get("birthdate"), date):
#                 step1_data["birthdate"] = step1_data["birthdate"].isoformat()

#             request.session['step1_data'] = step1_data
            
#             return redirect('base:register_step2')
#     else:
#         form = CustomUserInformationForm(initial=request.session.get('step1_data'))

#     return render(request, 'registration/register_step1.html', {'form': form})


# def register_step2(request):
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


