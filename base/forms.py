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
    # Enhanced phone number validation for Philippine mobile numbers
    phone_regex = RegexValidator(
        regex=r'^\+63 9\d{2} \d{3} \d{4}$', 
        message="Phone number must be in the format: +63 9XX XXX XXXX"
    )
    
    # Name validation regex - alphabets, hyphens, apostrophes, and accent marks
    name_regex = RegexValidator(
        regex=r"^[a-zA-ZÀ-ÿ\u0100-\u017F\u1E00-\u1EFF'\-\s]+$",
        message="Only letters, hyphens, apostrophes, and accent marks are allowed."
    )
    
    contact_number = forms.CharField(
        label="Your Contact No. *", 
        validators=[phone_regex], 
        max_length=17, 
        widget=forms.TextInput(attrs={
            'type': 'tel', 
            'placeholder': '+63 9XX XXX XXXX', 
            'class': 'form-control phone-input',
            'value': '+63',
            'data-format': '+63 9XX XXX XXXX'
        })
    ) 
    
    emergency_contact_number = forms.CharField(
        label="Emergency Contact Person's Contact No. *", 
        validators=[phone_regex], 
        max_length=17, 
        widget=forms.TextInput(attrs={
            'type': 'tel', 
            'placeholder': '+63 9XX XXX XXXX', 
            'class': 'form-control phone-input',
            'value': '+63',
            'data-format': '+63 9XX XXX XXXX'
        })
    )
    
    civil_status = forms.ChoiceField(label="Civil Status *", choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class':'form-select'}))
    sex = forms.ChoiceField(label="Sex *", choices=SEX_CHOICES, widget=forms.RadioSelect)

    # Enhanced name fields with length and character restrictions
    firstname = forms.CharField(
        label="First Name *",
        max_length=16,
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '16',
            'placeholder': 'Enter your first name'
        })
    )
    
    lastname = forms.CharField(
        label="Last Name *",
        max_length=21,
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '21',
            'placeholder': 'Enter your last name'
        })
    )
    
    middlename = forms.CharField(
        label="Middle Name",
        max_length=16,
        required=False,
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '16',
            'placeholder': 'Enter your middle name'
        })
    )
    
    nameextension = forms.CharField(
        label="Name Extension", 
        max_length=7,
        required=False, 
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'maxlength': '7',
            'placeholder': 'Jr., Sr., III, etc.'
        })
    )
    
    emergency_contact_person = forms.CharField(
        label="Emergency Contact Person *",
        max_length=50,
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '50',
            'placeholder': 'Enter emergency contact name'
        })
    )

    class Meta:
        model = UserInformation
        fields = ["firstname", "lastname", "middlename", "nameextension", "sex", "birthdate", "barangay_id", "municipality_id", "address_details", "civil_status", "emergency_contact_person", "emergency_contact_number", "contact_number"]
        labels = {
            "lastname": "Last Name *",
            "firstname": "First Name *", 
            "middlename": "Middle Name",
            "nameextension": "Name Extension",
            "sex": "Sex *",
            "birthdate": "Date of Birth *",
            "barangay_id": "Barangay *",
            "municipality_id": "Municipality *",
            "address_details": "Address Details *", 
            "emergency_contact_person" : "Emergency Contact Person *", 
            "emergency_contact_number" : "Emergency Contact Person's Contact No. *", 
            "contact_number" : "Contact Number *"
        }
        widgets = {
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
            'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,'required': 'required', 'placeholder': 'House No., Purok, Street Name, Building'}),
            'civil_status': forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Civil Status'}),
        }
    
    def clean_birthdate(self):
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        birthdate = self.cleaned_data.get('birthdate')
        if birthdate:
            today = date.today()
            age = relativedelta(today, birthdate).years
            
            if age < 10:
                raise forms.ValidationError("You must be at least 10 years old to register.")
            elif age > 90:
                raise forms.ValidationError("Age cannot exceed 90 years. Please contact support if you need assistance.")
                
        return birthdate
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize barangay queryset as empty
        self.fields['barangay_id'].queryset = BarangayName.objects.none()
        # Exclude pk=14 (Overall) from municipality options
        self.fields['municipality_id'].queryset = MunicipalityName.objects.exclude(pk=14).order_by('municipality')
        
        # If we have initial data with municipality, populate barangays
        if 'municipality_id' in self.data:
            try:
                municipality_id = int(self.data.get('municipality_id'))
                self.fields['barangay_id'].queryset = BarangayName.objects.filter(municipality_id=municipality_id).order_by('barangay')
            except (ValueError, TypeError):
                pass  # Invalid municipality_id, keep empty queryset
        elif self.instance.pk and self.instance.municipality_id:
            # If editing an existing instance, populate barangays for the selected municipality
            self.fields['barangay_id'].queryset = BarangayName.objects.filter(municipality_id=self.instance.municipality_id).order_by('barangay')
    
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
    # Enhanced phone number validation for Philippine mobile numbers
    phone_regex = RegexValidator(
        regex=r'^\+63 9\d{2} \d{3} \d{4}$', 
        message="Phone number must be in the format: +63 9XX XXX XXXX"
    )
    
    # Name validation regex - alphabets, hyphens, apostrophes, and accent marks
    name_regex = RegexValidator(
        regex=r"^[a-zA-ZÀ-ÿ\u0100-\u017F\u1E00-\u1EFF'\-\s]+$",
        message="Only letters, hyphens, apostrophes, and accent marks are allowed."
    )
    
    sex = forms.ChoiceField(choices=SEX_CHOICES, widget=forms.RadioSelect)
    civil_status = forms.ChoiceField(label="Civil Status", choices=CIVSTAT_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    
    # Enhanced name fields with length and character restrictions
    firstname = forms.CharField(
        label="First Name *",
        max_length=16,
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '16',
            'placeholder': 'Enter your first name'
        })
    )
    
    lastname = forms.CharField(
        label="Last Name *",
        max_length=21,
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '21',
            'placeholder': 'Enter your last name'
        })
    )
    
    middlename = forms.CharField(
        label="Middle Name",
        max_length=16,
        required=False,
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '16',
            'placeholder': 'Enter your middle name'
        })
    )
    
    nameextension = forms.CharField(
        label="Name Extension", 
        max_length=7,
        required=False, 
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'maxlength': '7',
            'placeholder': 'Jr., Sr., III, etc.'
        })
    )
    
    emergency_contact_person = forms.CharField(
        label="Emergency Contact Person *",
        max_length=50,
        validators=[name_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '50',
            'placeholder': 'Enter emergency contact name'
        })
    )
    
    contact_number = forms.CharField(
        label="Contact No. *", 
        validators=[phone_regex], 
        max_length=20, 
        widget=forms.TextInput(attrs={
            'type': 'tel', 
            'placeholder': '+63 9XX XXX XXXX', 
            'class': 'form-control phone-input',
            'data-format': '+63 9XX XXX XXXX'
        })
    )
    
    emergency_contact_number = forms.CharField(
        label="Emergency Contact No. *", 
        validators=[phone_regex], 
        max_length=20, 
        widget=forms.TextInput(attrs={
            'type': 'tel', 
            'placeholder': '+63 9XX XXX XXXX', 
            'class': 'form-control phone-input',
            'data-format': '+63 9XX XXX XXXX'
        })
    )

    class Meta:
        model = UserInformation
        fields = ["lastname", "firstname", "middlename", "nameextension", "sex", "birthdate","municipality_id","barangay_id",  "address_details", "civil_status", "emergency_contact_person", "emergency_contact_number", "user_email", "contact_number"]
        labels = {
            "lastname": "Last Name *", 
            "firstname": "First Name", 
            "middlename": "Middle Name",
            "nameextension": "Name Extension", 
            "sex": "Sex *", 
            "birthdate": "Date of Birth *",
            "municipality_id": "Municipality *",
            "barangay_id": "Barangay *", 
            "address_details": "House No., Purok, Street Name, Building *", 
            "civil_status": "Civil Status *", 
            "emergency_contact_person": "Emergency Contact Person *", 
            "emergency_contact_number": "Emergency Contact No. *",
            "user_email": "Email *", 
            "contact_number": "Contact No. *"
        }
        widgets = {
            'sex': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'birthdate': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'barangay_id': forms.Select(attrs={'class': 'form-control form-select'}),
            'municipality_id': forms.Select(attrs={'class': 'form-control form-select'}),
            'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'civil_status': forms.Select(attrs={'class': 'form-control'}),
            'user_email': forms.EmailInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }
    
    def clean_birthdate(self):
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        birthdate = self.cleaned_data.get('birthdate')
        if birthdate:
            today = date.today()
            age = relativedelta(today, birthdate).years
            
            if age < 10:
                raise forms.ValidationError("You must be at least 10 years old.")
            elif age > 90:
                raise forms.ValidationError("Age cannot exceed 90 years. Please contact support if you need assistance.")
                
        return birthdate
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude pk=14 (Overall) from municipality options
        self.fields['municipality_id'].queryset = MunicipalityName.objects.exclude(pk=14).order_by('municipality')
        # Initialize barangay queryset properly
        self.fields['barangay_id'].queryset = BarangayName.objects.none()
        
        # If we have initial data with municipality, populate barangays
        if 'municipality_id' in self.data:
            try:
                municipality_id = int(self.data.get('municipality_id'))
                self.fields['barangay_id'].queryset = BarangayName.objects.filter(municipality_id=municipality_id).order_by('barangay')
            except (ValueError, TypeError):
                pass  # Invalid municipality_id, keep empty queryset
        elif self.instance.pk and self.instance.municipality_id:
            # If editing an existing instance, populate barangays for the selected municipality
            self.fields['barangay_id'].queryset = BarangayName.objects.filter(municipality_id=self.instance.municipality_id).order_by('barangay')


class HarvestRecordCreate(forms.ModelForm):
    unit = forms.ModelChoiceField(label="Unit of Measurement *",queryset=UnitMeasurement.objects.all(),widget=forms.Select(attrs={'class': 'form-select'}))
    total_weight = forms.DecimalField(
        label="Total Weight of Commodity *",
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '0.00',
            'maxlength': '12'
        })
    ) 

    class Meta:
        model = initHarvestRecord
        fields = ["harvest_date", "commodity_id", "unit", "total_weight", "remarks"]
        labels = {"harvest_date": "Harvest Date *","commodity_id": "Commodity Type *","remarks": "Remarks / Additional Notes"}
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commodity_id': forms.Select(attrs={'class': 'form-control', 'id': 'id_commodity_id'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Enter remarks here...(optional)'}),
        }

    def clean_total_weight(self):
        value = self.cleaned_data.get('total_weight')
        if value is not None:
            if value <= 0:
                raise forms.ValidationError("Total weight must be greater than 0.")
            # Check decimal places
            decimal_str = str(value)
            if '.' in decimal_str:
                decimal_places = len(decimal_str.split('.')[1])
                if decimal_places > 2:
                    raise forms.ValidationError("Total weight cannot have more than 2 decimal places.")
        return value

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set harvest_date to current date as default
        from datetime import date
        if 'harvest_date' in self.fields:
            self.fields['harvest_date'].initial = date.today()
        
        # Set commodity dropdown to exclude "Not Listed" (pk=1) and order alphabetically
        if 'commodity_id' in self.fields:
            self.fields['commodity_id'].queryset = CommodityType.objects.exclude(pk=1).order_by('name')
        
class RecordTransactionCreate(forms.ModelForm):
    location_type = forms.ChoiceField(label="Pick a Location Type *",choices=LOCATION_TYPE_CHOICES,widget=forms.RadioSelect(attrs={ 'style': 'margin-right: 5px;', 'placeholder' : 'Enter estimated land area...(optional)'}))
    farm_land = forms.ModelChoiceField(queryset=FarmLand.objects.none(),required=False,label="Select Farm Land",widget=forms.Select(attrs={'class': 'form-select',  'placeholder' : 'Enter Farm Land name...'}))

    manual_municipality = forms.ModelChoiceField(label="Manual: Municipality",queryset=MunicipalityName.objects.exclude(pk=14),required=False,widget=forms.Select(attrs={'class': 'form-select'}))
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
    min_expected_harvest = forms.DecimalField(
        label="Min Expected Harvest (kg) *", 
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '0.00',
            'maxlength': '12'
        })
    )
    max_expected_harvest = forms.DecimalField(
        label="Max Expected Harvest (kg) *", 
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '0.00',
            'maxlength': '12'
        })
    )

    class Meta:
        model = initPlantRecord
        fields = ["plant_date", "commodity_id", "min_expected_harvest", "max_expected_harvest", "remarks"]
        labels = {"plant_date": "Plant Date *","commodity_id": "Commodity Type *","remarks": "Remarks / Additional Notes"}
        widgets = {
            'plant_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'commodity_id': forms.Select(attrs={'class': 'form-control', 'id': 'id_commodity_id'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Enter remarks here...(optional)'}),
        }

    def clean_min_expected_harvest(self):
        value = self.cleaned_data.get('min_expected_harvest')
        if value is not None:
            if value <= 0:
                raise forms.ValidationError("Minimum expected harvest must be greater than 0.")
            # Check decimal places
            decimal_str = str(value)
            if '.' in decimal_str:
                decimal_places = len(decimal_str.split('.')[1])
                if decimal_places > 2:
                    raise forms.ValidationError("Minimum expected harvest cannot have more than 2 decimal places.")
        return value

    def clean_max_expected_harvest(self):
        value = self.cleaned_data.get('max_expected_harvest')
        if value is not None:
            if value <= 0:
                raise forms.ValidationError("Maximum expected harvest must be greater than 0.")
            # Check decimal places
            decimal_str = str(value)
            if '.' in decimal_str:
                decimal_places = len(decimal_str.split('.')[1])
                if decimal_places > 2:
                    raise forms.ValidationError("Maximum expected harvest cannot have more than 2 decimal places.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        min_harvest = cleaned_data.get('min_expected_harvest')
        max_harvest = cleaned_data.get('max_expected_harvest')
        
        if min_harvest and max_harvest and min_harvest > max_harvest:
            raise forms.ValidationError("Minimum expected harvest cannot be greater than maximum expected harvest.")
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set plant_date to current date as default
        from datetime import date
        if 'plant_date' in self.fields:
            self.fields['plant_date'].initial = date.today()
        
        # Set commodity dropdown to exclude "Not Listed" (pk=1) and order alphabetically
        if 'commodity_id' in self.fields:
            self.fields['commodity_id'].queryset = CommodityType.objects.exclude(pk=1).order_by('name')

class FarmlandRecordCreate(forms.ModelForm):
    farmland_name = forms.CharField(
        label="Farm Name *", 
        max_length=50, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Enter Farmland name...',
            'maxlength': '50'
        })
    )
    estimated_area = forms.DecimalField(
        label="Estimated Farm Area (in hectares) *", 
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Enter land area...',
            'maxlength': '12'
        })
    )
    municipality = forms.ModelChoiceField(label="Municipality of Farm *", queryset=MunicipalityName.objects.exclude(pk=14), widget=forms.Select(attrs={'class': 'form-select'}))
    barangay = forms.ModelChoiceField(label="Barangay of Farm *", queryset=BarangayName.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}))

    def clean_estimated_area(self):
        value = self.cleaned_data.get('estimated_area')
        if value is None:
            raise forms.ValidationError("Estimated area is required.")
        if value <= 0:
            raise forms.ValidationError("Estimated area must be greater than 0.")
        # Check decimal places
        decimal_str = str(value)
        if '.' in decimal_str:
            decimal_places = len(decimal_str.split('.')[1])
            if decimal_places > 2:
                raise forms.ValidationError("Estimated area cannot have more than 2 decimal places.")
        return value

    class Meta:
        model = FarmLand
        fields = ["farmland_name", "estimated_area", "municipality", "barangay"]
        labels = {"farmland_name": "Farm Name *", "estimated_area": "Farm Area (in hectares) *", "municipality": "Municipality of Farm *", "barangay": "Barangay of Farm *"}
        widgets = {
            'farmland_name': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_area': forms.TextInput(attrs={'class': 'form-control'}),
            'municipality': forms.Select(attrs={'class': 'form-select'}),
            'barangay': forms.Select(attrs={'class': 'form-select'}),
        }