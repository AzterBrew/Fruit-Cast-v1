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
    # ('Other','Other'),
]


class RegistrationForm(forms.ModelForm):
    phone_regex = RegexValidator(  #regular expression
        regex=r'^\+?1?\d{9,15}$', 
        message="Phone number must be entered in the format: '+639XXXXXXXXX'.")
    
    contact_number = forms.CharField(label="Your Contact No. *", validators=[phone_regex], max_length=17, widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX', 'class' : 'form-control'}))
    emergency_contact_number = forms.CharField(label="Emergency Contact Person's Contact No. *", validators=[phone_regex], max_length=17, widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX', 'class' : 'form-control'}))
    civil_status = forms.ChoiceField(label="Civil Status *", choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class':'form-select'}))
    
    # password1 = forms.CharField(
    #     label="Password *",
    #     widget=forms.PasswordInput(attrs={'class': 'form-control'})
    # )
    # password2 = forms.CharField(
    #     label="Confirm Password *",
    #     widget=forms.PasswordInput(attrs={'class': 'form-control'})
    # )
    sex = forms.ChoiceField(label="Sex *", choices=SEX_CHOICES, widget=forms.RadioSelect)

    nameextension = forms.CharField(label="Name Extension", required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank if N/A'}))

    class Meta:
        model = UserInformation
        fields = ["firstname", "lastname", "middlename", "nameextension", "sex", "birthdate", "barangay_id", "municipality_id", "address_details", "religion", "civil_status", "rsbsa_ref_number", "emergency_contact_person", "emergency_contact_number", "contact_number"]
        labels = {"lastname": "Last Name *","firstname": "First Name *", "middlename": "Middle Name","nameextension": "Name Extension","sex": "Sex *","birthdate": "Date of Birth *","barangay_id": "Barangay *","municipality_id": "Municipality *","address_details": "Address Details *", "religion":"Religion *",  "emergency_contact_person" : "Emergency Contact Person *", "emergency_contact_number" : "Emergency Contact Person's Contact No. *", "contact_number" : "Contact Number *"}
        widgets = {
            'firstname': forms.TextInput(attrs={'class': 'form-control','required': 'required', 'placeholder': 'First Name'}),
            'lastname': forms.TextInput(attrs={'class': 'form-control','required': 'required', 'placeholder': 'Last Name'}),
            'middlename': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle Name'}),
            'sex': forms.RadioSelect(attrs={'class': 'form-check-input','required': 'required'}),
            'birthdate': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control',
                'required': 'required',
                'min': '1900-01-01',
                'max': '2024-12-31'
            }),
            'barangay_id': forms.Select(attrs={'class': 'form-select','required': 'required'}),
            'municipality_id': forms.Select(attrs={'class': 'form-select','required': 'required'}),
            'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,'required': 'required', 'placeholder': 'Purok, Street Name, Building, House No.'}),
            'religion': forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Religion'}),
            'civil_status': forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Civil Status'}),
            'rsbsa_ref_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder' : 'Leave blank if Not Applicable'}),
            'emergency_contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Last Name, First Name Middle Name'}),
        }
    # def clean(self):
    #     cleaned_data = super().clean()
    #     # Add password match validation, etc.
    #     password1 = cleaned_data.get("password1")
    #     password2 = cleaned_data.get("password2")
    #     if password1 and password2 and password1 != password2:
    #         self.add_error('password2', "Passwords do not match.")
    #     return cleaned_data
    
# class CustomUserInformationForm(forms.ModelForm):
#     sex = forms.ChoiceField(label="Sex *", choices=SEX_CHOICES, widget=forms.RadioSelect)

#     nameextension = forms.CharField(label="Name Extension", required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank if N/A'}))

#     class Meta:
#         model = UserInformation
#         fields = ["firstname", "lastname", "middlename", "nameextension", "sex", "birthdate", "barangay_id", "municipality_id", "address_details"]
#         labels = {"lastname": "Last Name *","firstname": "First Name *", "middlename": "Middle Name *","nameextension": "Name Extension","sex": "Sex *","birthdate": "Date of Birth *","barangay_id": "Barangay *","municipality_id": "Municipality *","address_details": "Purok, Street Name, Building, House No. *"}
#         widgets = {
#             'firstname': forms.TextInput(attrs={'class': 'form-control','required': 'required'}),
#             'lastname': forms.TextInput(attrs={'class': 'form-control','required': 'required'}),
#             'middlename': forms.TextInput(attrs={'class': 'form-control'}),
#             'sex': forms.RadioSelect(attrs={'class': 'form-check-input','required': 'required'}),
#             'birthdate': forms.DateInput(attrs={'type': 'date', 'class': 'form-control','required': 'required'}),
#             'barangay_id': forms.Select(attrs={'class': 'form-select','required': 'required'}),
#             'municipality_id': forms.Select(attrs={'class': 'form-select','required': 'required'}),
#             'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,'required': 'required', 'placeholder': 'Purok, Street Name, Building, House No.'}),
#         }


# class UserContactAndAccountForm(forms.ModelForm):
#     phone_regex = RegexValidator(  #regular expression
#         regex=r'^\+?1?\d{9,15}$', 
#         message="Phone number must be entered in the format: '+639XXXXXXXXX'.")
    
#     contact_number = forms.CharField(label="Your Contact No. *", validators=[phone_regex], max_length=17, widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX', 'class' : 'form-control'}))
#     emergency_contact_number = forms.CharField(label="Emergency Contact Person's Contact No. *",widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX', 'class' : 'form-control'}))
#     civil_status = forms.ChoiceField(label="Civil Status *", choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class':'form-select'}))
    
#     password1 = forms.CharField(
#         label="Password *",
#         widget=forms.PasswordInput(attrs={'class': 'form-control'})
#     )
#     password2 = forms.CharField(
#         label="Confirm Password *",
#         widget=forms.PasswordInput(attrs={'class': 'form-control'})
#     )

#     class Meta:
#         model = UserInformation
#         fields = ["religion", "civil_status", "rsbsa_ref_number", "emergency_contact_person", "emergency_contact_number", "contact_number", "user_email"]
#         labels = {"religion":"Religion *",  "emergency_contact_person" : "Emergency Contact Person *", "emergency_contact_number" : "Emergency Contact Person's Contact No. *", "user_email" : "Email Address *", "contact_number" : "Contact Number *" }
#         widgets = {
#             'religion': forms.TextInput(attrs={'class': 'form-control'}),
#             'civil_status': forms.TextInput(attrs={'class': 'form-control'}),
#             'rsbsa_ref_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder' : 'Leave blank if N/A'}),
#             'emergency_contact_person': forms.TextInput(attrs={'class': 'form-control'}),
#             'user_email': forms.EmailInput(attrs={'class': 'form-control'}),
#         }

class EditUserInformation(forms.ModelForm):
    sex = forms.ChoiceField(choices=SEX_CHOICES, widget=forms.RadioSelect)
    civil_status = forms.ChoiceField(label="Civil Status", choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    nameextension = forms.CharField(label="Name Extension", required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank if N/A'}))

    class Meta:
        model = UserInformation
        fields = ["lastname", "firstname", "middlename", "nameextension", "sex", "birthdate","barangay_id", "municipality_id", "address_details", "religion", "civil_status","rsbsa_ref_number", "emergency_contact_person", "emergency_contact_number", "user_email", "contact_number"]
        labels = {"lastname": "Last Name", "firstname": "First Name", "middlename": "Middle Name","nameextension": "Name Extension", "sex": "Sex", "birthdate": "Date of Birth","barangay_id": "Barangay", "municipality_id": "Municipality","address_details": "Purok, Street Name, Building, House No.", "religion": "Religion","civil_status": "Civil Status", "rsbsa_ref_number": "RSBSA Reference No.","emergency_contact_person": "Emergency Contact Person", "emergency_contact_number": "Emergency Contact No.","user_email": "Email", "contact_number": "Contact No."}
        widgets = {
            'firstname': forms.TextInput(attrs={'class': 'form-control form-control'}),
            'lastname': forms.TextInput(attrs={'class': 'form-control form-control'}),
            'middlename': forms.TextInput(attrs={'class': 'form-control form-control'}),
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
    unit = forms.ModelChoiceField(label="Unit of Measurement *",queryset=UnitMeasurement.objects.all(),widget=forms.Select(attrs={'class': 'form-select'}))
    total_weight = forms.DecimalField(localize=True,label="Total Weight of Commodity *",widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.1', 'placeholder': '0.0'}))
    weight_per_unit = forms.DecimalField(localize=True,label="Weight per unit *",widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.1', 'placeholder': '0.0'}))


    class Meta:
        model = initHarvestRecord
        fields = ["harvest_date", "commodity_id", "commodity_custom",  "unit", "total_weight", "weight_per_unit", "remarks"]
        labels = {"harvest_date": "Harvest Date *","commodity_id": "Commodity Type *","commodity_custom": "Commodity Specification (if not listed)","remarks": "Remarks / Additional Notes"}
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commodity_id': forms.Select(attrs={'class': 'form-control', 'id': 'id_commodity_id'}),
            'commodity_custom': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_commodity_custom', 'placeholder': 'If not listed, enter commodity here'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Enter remarks here...(optional)'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Custom ordering for commodity dropdown: blank, "Not Listed" (pk=1), then alphabetical
        if 'commodity_id' in self.fields:
            commodities = CommodityType.objects.all()
            not_listed = commodities.filter(pk=1).first()
            other_commodities = commodities.exclude(pk=1).order_by('name')
            
            # Create custom queryset with desired order
            if not_listed:
                ordered_commodities = [not_listed] + list(other_commodities)
                self.fields['commodity_id'].queryset = CommodityType.objects.filter(
                    pk__in=[c.pk for c in ordered_commodities]
                )
                # Set the widget choices manually to maintain order
                choices = [('', '---------')]  # Default blank option
                choices.append((not_listed.pk, not_listed.name))  # "Not Listed" as second option
                choices.extend([(c.pk, c.name) for c in other_commodities])
                self.fields['commodity_id'].widget.choices = choices
        
class RecordTransactionCreate(forms.ModelForm):
    location_type = forms.ChoiceField(label="Pick a Location Type *",choices=LOCATION_TYPE_CHOICES,widget=forms.RadioSelect(attrs={ 'style': 'margin-right: 5px;', 'placeholder' : 'Enter estimated land area...(optional)'}))
    farm_land = forms.ModelChoiceField(queryset=FarmLand.objects.none(),required=False,label="Select FarmLand",widget=forms.Select(attrs={'class': 'form-select',  'placeholder' : 'Enter Farmland name...'}))

    manual_municipality = forms.ModelChoiceField(label="Manual: Municipality",queryset=MunicipalityName.objects.all(),required=False,widget=forms.Select(attrs={'class': 'form-select'}))
    manual_barangay = forms.ModelChoiceField(label="Manual: Barangay",queryset=BarangayName.objects.none(),required=False,widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = RecordTransaction
        fields = ["location_type", "farm_land", "manual_municipality", "manual_barangay"]
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Only set queryset if the field exists
        if user and 'farm_land' in self.fields:
            self.fields['farm_land'].queryset = FarmLand.objects.filter(userinfo_id__auth_user=user)

class PlantRecordCreate(forms.ModelForm):
    min_expected_harvest = forms.DecimalField(label="Min Expected Harvest (kg) *", widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01', 'placeholder':'0'}))
    max_expected_harvest = forms.DecimalField(label="Max Expected Harvest (kg) *", widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01', 'placeholder':'0'}))

    class Meta:
        model = initPlantRecord
        fields = ["plant_date", "commodity_id", "commodity_custom", "min_expected_harvest", "max_expected_harvest", "remarks"]
        labels = {"plant_date": "Plant Date *","commodity_id": "Commodity Type *","commodity_custom": "Commodity Specification (if not listed)","remarks": "Remarks / Additional Notes"}
        widgets = {
            'plant_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commodity_id': forms.Select(attrs={'class': 'form-control', 'id': 'id_commodity_id'}),
            'commodity_custom': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_commodity_custom','placeholder': 'If not listed, enter commodity here'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Enter remarks here...(optional)'}),
        }


    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Custom ordering for commodity dropdown: blank, "Not Listed" (pk=1), then alphabetical
        if 'commodity_id' in self.fields:
            commodities = CommodityType.objects.all()
            not_listed = commodities.filter(pk=1).first()
            other_commodities = commodities.exclude(pk=1).order_by('name')
            
            # Create custom queryset with desired order
            if not_listed:
                ordered_commodities = [not_listed] + list(other_commodities)
                self.fields['commodity_id'].queryset = CommodityType.objects.filter(
                    pk__in=[c.pk for c in ordered_commodities]
                )
                # Set the widget choices manually to maintain order
                choices = [('', '---------')]  # Default blank option
                choices.append((not_listed.pk, not_listed.name))  # "Not Listed" as second option
                choices.extend([(c.pk, c.name) for c in other_commodities])
                self.fields['commodity_id'].widget.choices = choices

class FarmlandRecordCreate(forms.ModelForm):
    farmland_name = forms.CharField(label="Farm Name *", max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder' : 'Enter Farmland name...'}))
    estimated_area = forms.DecimalField(label="Estimated Farm Area (in hectares)", localize=True, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01', 'placeholder' : 'Enter land area...(optional)'}))
    municipality = forms.ModelChoiceField(label="Municipality of Farm *", queryset=MunicipalityName.objects.exclude(pk=14), widget=forms.Select(attrs={'class': 'form-select'}))
    barangay = forms.ModelChoiceField(label="Barangay of Farm *", queryset=BarangayName.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = FarmLand
        fields = ["farmland_name", "estimated_area", "municipality", "barangay"]
        labels = {"farmland_name": "Farm Name *", "estimated_area": "Farm Area (in hectares) *", "municipality": "Municipality of Farm *", "barangay": "Barangay of Farm *"}
        widgets = {
            'farmland_name': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_area': forms.NumberInput(attrs={'class': 'form-control'}),
            'municipality': forms.Select(attrs={'class': 'form-select'}),
            'barangay': forms.Select(attrs={'class': 'form-select'}),
        }