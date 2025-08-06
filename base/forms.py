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
    ('','Select Municipality'),
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
    sex = forms.ChoiceField(label="Sex *", choices=SEX_CHOICES, widget=forms.RadioSelect)

    nameextension = forms.CharField(label="Name Extension", required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank if N/A'}))

    class Meta:
        model = UserInformation
        fields = ["firstname", "lastname", "middlename", "nameextension", "sex", "birthdate", "barangay_id", "municipality_id", "address_details"]
        labels = {"lastname": "Last Name *","firstname": "First Name *", "middlename": "Middle Name *","nameextension": "Name Extension","sex": "Sex *","birthdate": "Date of Birth *","barangay_id": "Barangay *","municipality_id": "Municipality *","address_details": "Purok, Street Name, Building, House No. *"}
        widgets = {
            'firstname': forms.TextInput(attrs={'class': 'form-control','required': 'required'}),
            'lastname': forms.TextInput(attrs={'class': 'form-control','required': 'required'}),
            'middlename': forms.TextInput(attrs={'class': 'form-control'}),
            'sex': forms.RadioSelect(attrs={'class': 'form-check-input','required': 'required'}),
            'birthdate': forms.DateInput(attrs={'type': 'date', 'class': 'form-control','required': 'required'}),
            'barangay_id': forms.Select(attrs={'class': 'form-select','required': 'required'}),
            'municipality_id': forms.Select(attrs={'class': 'form-select','required': 'required'}),
            'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,'required': 'required'}),
        }


class UserContactAndAccountForm(forms.ModelForm):
    phone_regex = RegexValidator(  #regular expression
        regex=r'^\+?1?\d{9,15}$', 
        message="Phone number must be entered in the format: '+639XXXXXXXXX'.")
    
    contact_number = forms.CharField(label="Your Contact No. *", validators=[phone_regex], max_length=17, widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX', 'class' : 'form-control'}))
    emergency_contact_number = forms.CharField(label="Emergency Contact Person's Contact No. *",widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX', 'class' : 'form-control'}))
    civil_status = forms.ChoiceField(label="Civil Status *", choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class':'form-select'}))
    
    password1 = forms.CharField(
        label="Password *",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label="Confirm Password *",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UserInformation
        fields = ["religion", "civil_status", "rsbsa_ref_number", "emergency_contact_person", "emergency_contact_number", "contact_number", "user_email"]
        labels = {"religion":"Religion *",  "emergency_contact_person" : "Emergency Contact Person *", "emergency_contact_number" : "Emergency Contact Person's Contact No. *", "user_email" : "Email Address *", "contact_number" : "Contact Number *" }
        widgets = {
            'religion': forms.TextInput(attrs={'class': 'form-control'}),
            'civil_status': forms.TextInput(attrs={'class': 'form-control'}),
            'rsbsa_ref_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder' : 'Leave blank if N/A'}),
            'emergency_contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'user_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class EditUserInformation(forms.ModelForm):
    sex = forms.ChoiceField(choices=SEX_CHOICES, widget=forms.RadioSelect)
    civil_status = forms.ChoiceField(label="Civil Status", choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    nameextension = forms.CharField(label="Name Extension", required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank if N/A'}))

    class Meta:
        model = UserInformation
        fields = ["lastname", "firstname", "middlename", "nameextension", "sex", "birthdate","barangay_id", "municipality_id", "address_details", "religion", "civil_status","rsbsa_ref_number", "emergency_contact_person", "emergency_contact_number", "user_email", "contact_number"]
        labels = {"lastname": "Last Name", "firstname": "First Name", "middlename": "Middle Name","nameextension": "Name Extension", "sex": "Sex", "birthdate": "Date of Birth","barangay_id": "Barangay", "municipality_id": "Municipality","address_details": "Purok, Street Name, Building, House No.", "religion": "Religion","civil_status": "Civil Status", "rsbsa_ref_number": "RSBSA Reference No.","emergency_contact_person": "Emergency Contact Person", "emergency_contact_number": "Emergency Contact No.","user_email": "Email", "contact_number": "Contact No."}
        widgets = {
            'firstname': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'lastname': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'middlename': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'sex': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'birthdate': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'barangay_id': forms.Select(attrs={'class': 'form-control form-select'}),
            'municipality_id': forms.Select(attrs={'class': 'form-control form-select'}),
            'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'religion': forms.TextInput(attrs={'class': 'form-control'}),
            'civil_status': forms.Select(attrs={'class': 'form-control'}),
            'rsbsa_ref_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank if N/A'}),
            'emergency_contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'user_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'})
        }


class HarvestRecordCreate(forms.ModelForm):
    unit = forms.ModelChoiceField(label="Unit of Measurement",queryset=UnitMeasurement.objects.all(),widget=forms.Select(attrs={'class': 'form-select'}))
    total_weight = forms.DecimalField(localize=True,label="Total Weight of Commodity",widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.1'}))
    weight_per_unit = forms.DecimalField(localize=True,label="Weight per unit",widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.1'}))
    
    
    class Meta:
        model = initHarvestRecord
        fields = ["harvest_date", "commodity_id", "commodity_custom", "total_weight", "unit", "weight_per_unit", "remarks"]
        labels = {"harvest_date": "Harvest Date","commodity_id": "Commodity Type","commodity_custom": "Commodity Specification (if not listed)","remarks": "Remarks / Additional Notes"}
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commodity_id': forms.Select(attrs={'class': 'form-control', 'id': 'id_commodity_id'}),
            'commodity_custom': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_commodity_custom'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['farm_land'].queryset = FarmLand.objects.filter(userinfo_id__auth_user=user)

class RecordTransactionCreate(forms.ModelForm):
    location_type = forms.ChoiceField(label="Pick a Location Type",choices=LOCATION_TYPE_CHOICES,widget=forms.RadioSelect(attrs={ 'style': 'margin-right: 5px;'}))
    farm_land = forms.ModelChoiceField(queryset=FarmLand.objects.none(),required=False,label="Select FarmLand",widget=forms.Select(attrs={'class': 'form-select'}))

    manual_municipality = forms.ModelChoiceField(label="Manual: Municipality",queryset=MunicipalityName.objects.all(),required=False,widget=forms.Select(attrs={'class': 'form-select'}))
    manual_barangay = forms.ModelChoiceField(label="Manual: Barangay",queryset=BarangayName.objects.none(),required=False,widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = RecordTransaction
        fields = ["location_type", "farm_land", "manual_municipality", "manual_barangay"]
        # widgets = {
        #     'harvest_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        #     'commodity_id': forms.Select(attrs={'class': 'form-control', 'id': 'id_commodity_id'}),
        #     'commodity_custom': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_commodity_custom'}),
        #     'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        # }
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['farm_land'].queryset = FarmLand.objects.filter(userinfo_id__auth_user=user)

class PlantRecordCreate(forms.ModelForm):
    location_type = forms.ChoiceField(label="Location Type",choices=LOCATION_TYPE_CHOICES,widget=forms.RadioSelect(attrs={'class': 'form-check-input'}))
    farm_land = forms.ModelChoiceField(queryset=FarmLand.objects.none(),required=False,label="Select FarmLand",widget=forms.Select(attrs={'class': 'form-select'}))

    manual_municipality = forms.ChoiceField(label="Manual: Municipality",choices=MUNICIPALITY_CHOICES,required=False,widget=forms.Select(attrs={'class': 'form-select'}))
    manual_barangay = forms.ChoiceField(label="Manual: Barangay",choices=[('', 'Select a Municipality First')],required=False,widget=forms.Select(attrs={'class': 'form-select'}))

    unit = forms.ChoiceField(label="Unit of Measurement",choices=UNIT_CHOICES,widget=forms.Select(attrs={'class': 'form-select'}))
    total_weight = forms.DecimalField(localize=True,label="Total Weight of Commodity",widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.1'}))
    weight_per_unit = forms.DecimalField(localize=True,label="Weight per Unit",widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.1'}))

    class Meta:
        model = initPlantRecord
        fields = ["plant_date", "commodity_id", "commodity_custom", "min_expected_harvest","max_expected_harvest", "remarks"]
        labels = {"plant_date": "Date Planted","commodity_id": "Commodity Type","commodity_custom": "Commodity Specification (if not listed)","min_expected_harvest": "Min Expected Harvest (units)","max_expected_harvest": "Max Expected Harvest (units)","remarks": "Remarks / Additional Notes"}
        widgets = {
            'plant_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commodity_id': forms.Select(attrs={'class': 'form-control'}),
            'commodity_custom': forms.TextInput(attrs={'class': 'form-control'}),
            'min_expected_harvest': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_expected_harvest': forms.NumberInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['farm_land'].queryset = FarmLand.objects.filter(userinfo_id__auth_user=user)
        