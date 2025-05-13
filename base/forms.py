from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from base.models import *


# class CustomUserCreationForm(UserCreationForm):
#     email = forms.EmailField(required=True)    
#     phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
#     phone = forms.CharField(validators=[phone_regex], max_length=17)
    

#     class Meta:
#         model = User
#         fields = ["username", "email", "phone", "password1", "password2"]


# ark ; ark@gmail.com ; arkarkark



SEX_CHOICES = [
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other')
]

MUNICIPALITY_CHOICES = [
    ('Abucay', 'Abucay'),
    ('Bagac', 'Bagac'),
    ('Balanga', 'Balanga'),
    ('Dinalupihan', 'Dinalupihan'),
    ('Hermosa', 'Hermosa'),
    ('Limay', 'Limay'),
    ('Mariveles' ,'Mariveles'),
    ('Morong' ,'Morong'),
    ('Orani', 'Orani'),
    ('Orion', 'Orion'),
    ('Pilar', 'Pilar'),
    ('Samal', 'Samal'),
    ('Others', 'Outside Bataan')
]

UNIT_CHOICES = [
    ('kg','kilogram (kg)'),
    ('g','gram (g)'),
    ('ton','Metric Ton (t)'),
    ('lbs', 'Pounds (lbs)'),
]

CIVSTAT_CHOICES = [
    ('Single','Single'),
    ('Married','Married'),
    ('Separated','Separated'),
    ('Widowed','Widowed'),
    ('Divorced','Divorced'),
    ('Other','Other'),
]

class CustomUserInformationForm(forms.ModelForm):
    
    sex = forms.ChoiceField(choices=SEX_CHOICES, widget=forms.RadioSelect)
    nameextension = forms.CharField(label="Name Extension", required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder' : 'Leave blank if N/A'}))

    # nameextension = forms.CharField(label="Name Extension",widget=forms.TextInput(attrs={'placeholder' : 'Leave blank if not applicable'}))
    municipality = forms.ChoiceField(choices=MUNICIPALITY_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    
    class Meta:
        model = UserInformation
        fields = ["firstname", "lastname", "middlename", "nameextension", "sex", "birthdate", "barangay", "municipality", "address_details"]
        labels = {"lastname": "Last Name", "firstname": "First Name", "middlename" : "Middle Name", "nameextension" : "Name Extension", "sex" : "Sex", "birthdate" : "Date of Birth", "barangay": "Barangay", "municipality" : "Municipality", "address_details" : "Purok, Street Name, Building, House No."}
        widgets = {
            'firstname': forms.TextInput(attrs={'class': 'form-control'}),
            'lastname': forms.TextInput(attrs={'class': 'form-control'}),
            'middlename': forms.TextInput(attrs={'class': 'form-control'}),
            'sex': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'birthdate': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control'}),
            'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows' : 2}),
        }


class UserContactAndAccountForm(forms.ModelForm):
    phone_regex = RegexValidator(  #regular expression
        regex=r'^\+?1?\d{9,15}$', 
        message="Phone number must be entered in the format: '+639XXXXXXXXX'.")
    
    contact_number = forms.CharField(validators=[phone_regex], max_length=17, widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX', 'class' : 'form-control'}))
    emergency_contact_number = forms.CharField(label="Emergency Contact Person's Contact No.",widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX', 'class' : 'form-control'}))
    civil_status = forms.ChoiceField(label="Civil Status", choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class':'form-select'}))
    
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UserInformation
        fields = ["religion", "civil_status", "rsbsa_ref_number", "emergency_contact_person", "emergency_contact_number", "contact_number", "user_email"]
        labels = {"religion":"Religion",  "emergency_contact_person" : "Emergency Contact Person", "emergency_contact_number" : "Emergency Contact Person's Contact No.", "user_email" : "Email Address", "contact_number" : "Contact Number" }
        widgets = {
            'religion': forms.TextInput(attrs={'class': 'form-control'}),
            'civil_status': forms.TextInput(attrs={'class': 'form-control'}),
            'rsbsa_ref_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder' : 'Leave blank if N/A'}),
            'emergency_contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'user_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class EditUserInformation(forms.ModelForm):

    sex = forms.ChoiceField(choices=SEX_CHOICES, widget=forms.RadioSelect)
    municipality = forms.ChoiceField(choices=MUNICIPALITY_CHOICES, widget=forms.Select(attrs={'class': 'form-control form-select'}))
    nameextension = forms.CharField(label="Name Extension", required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder' : 'Leave blank if N/A'}))
    civil_status = forms.ChoiceField(label="Civil Status",choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class':'form-select'}))
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$', 
        message="Phone number must be entered in the format: '+639XXXXXXXXX'.")
        
    class Meta:
        model = UserInformation
        fields = ["lastname", "firstname", "middlename", "nameextension", "sex", "birthdate", "barangay", "municipality","address_details", "religion", "civil_status", "rsbsa_ref_number", "emergency_contact_person", "emergency_contact_number", "user_email","contact_number"]
        labels = {"lastname": "Last Name", "firstname": "First Name", "middlename" : "Middle Name", "nameextension" : "Name Extension", "sex" : "Sex", "birthdate" : "Date of Birth", "barangay": "Barangay", "municipality" : "Municipality", "address_details" : "Purok, Street Name, Building, House No.", "religion":"Religion",  "emergency_contact_person" : "Emergency Contact Person", "emergency_contact_number" : "Emergency Contact Person's Contact No.", "user_email" : "Email Address", "contact_number" : "Contact Number"}    
        widgets = {
            'firstname': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'lastname': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'middlename': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'sex': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'birthdate': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control'}),
            'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows' : 2}),
            'religion': forms.TextInput(attrs={'class': 'form-control'}),
            'civil_status': forms.TextInput(attrs={'class': 'form-control'}),
            'rsbsa_ref_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder' : 'Leave blank if N/A'}),
            'emergency_contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'user_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'})
        }


class HarvestRecordCreate (forms.ModelForm):
    
    # HELLOOO I ACTUALLY FORGOT TO ADD THE WEIGHT PER UNIT SO NEED KO MAG REMIGRATE
    
    harvest_municipality = forms.ChoiceField(label="Location of Harvest",choices=MUNICIPALITY_CHOICES, widget=forms.Select(attrs={'class':'form-control form-select'}))    
    unit = forms.ChoiceField(label="Unit of Measurement",choices=UNIT_CHOICES, widget=forms.Select(attrs={'class':'form-select'}))
    total_weight = forms.DecimalField(localize=True, label="Total Weight of Commodity",widget=forms.NumberInput(attrs={'class':'form-control', 'min':'0','step':'0.1'}))
    weight_per_unit = forms.DecimalField(localize=True, label="Weight per Unit",widget=forms.NumberInput(attrs={'class':'form-control', 'min':'0','step':'0.1'}))
    
    class Meta:
        model = HarvestRecord
        fields = ["harvest_date", "harvest_municipality", "commodity_type", "commodity_spec", "total_weight", "unit", "weight_per_unit","remarks"]
        labels = {"harvest_date" : "Harvest Date", "commodity_type" : "Commodity Type", "commodity_spec" : "Commodity Specification", "remarks" : "Remarks / Additional Notes"}
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commodity_type' : forms.TextInput(attrs={'class':'form-control'}),
            'commodity_spec' : forms.TextInput(attrs={'class':'form-control'}),
            'remarks' : forms.Textarea(attrs={'class':'form-control', 'rows' : 2})
            
        }

class PlantRecordCreate(forms.ModelForm):
    plant_municipality = forms.ChoiceField(label="Planting Location", choices=MUNICIPALITY_CHOICES, widget=forms.Select(attrs={'class':'form-select'}))

    class Meta:
        model = PlantRecord
        fields = ["plant_date", "expected_harvest_date","commodity_type", "commodity_spec","min_expected_harvest", "max_expected_harvest", "plant_municipality","land_area", "remarks"]
        labels = {"plant_date": "Date Planted","commodity_type": "Commodity Type","commodity_spec": "Commodity Specification","expected_harvest_date": "Expected Harvest Date","min_expected_harvest": "Min Expected Harvest (kg)","max_expected_harvest": "Max Expected Harvest (kg)","land_area": "Land Area (hectares)","remarks": "Remarks / Additional Notes"}
        widgets = {
            'plant_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expected_harvest_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commodity_type': forms.TextInput(attrs={'class': 'form-control'}),
            'commodity_spec': forms.TextInput(attrs={'class': 'form-control'}),
            'min_expected_harvest': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_expected_harvest': forms.NumberInput(attrs={'class': 'form-control'}),
            'land_area': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

        