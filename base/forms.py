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
    ('Dinalupihan', 'Dinalupihan'),
    ('Hermosa', 'Hermosa'),
    ('Limay', 'Limay'),
    ('Mariveles' ,'Mariveles'),
    ('Morong' ,'Morong'),
    ('Orani', 'Orani'),
    ('Orion', 'Orion'),
    ('Pilar', 'Pilar'),
    ('Samal', 'Samal')
]

class CustomUserInformationForm(forms.ModelForm):
    
    sex = forms.ChoiceField(choices=SEX_CHOICES, widget=forms.RadioSelect)
    
    birthdate = forms.DateField(label="Date of Birth",widget=forms.DateInput(attrs={'type': 'date'}))
    
    nameextension = forms.CharField(label="Name Extension",widget=forms.TextInput(attrs={'placeholder' : 'Leave blank if not applicable'}))
    municipality = forms.ChoiceField(choices=MUNICIPALITY_CHOICES, widget=forms.Select)
    
    class Meta:
        model = UserInformation
        fields = ["lastname", "firstname", "middlename", "nameextension", "sex", "birthdate", "barangay", "municipality"]
        labels = {"lastname": "Last Name", "firstname": "First Name", "middlename" : "Middle Name", "nameextension" : "Name Extension", "sex" : "Sex", "birthdate" : "Date of Birth", "barangay": "Barangay", "municipality" : "Municipality"}


class UserContactAndAccountForm(forms.ModelForm):
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$', 
        message="Phone number must be entered in the format: '+639XXXXXXXXX'.")
    contact_number = forms.CharField(validators=[phone_regex], max_length=17, widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX'}))
    
    emergency_contact_number = forms.CharField(label="Emergency Contact Person's Contact No.",widget=forms.TextInput(attrs={'type': 'tel', 'placeholder': '+639XXXXXXXXX'}))
    
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput
    )


    class Meta:
        model = UserInformation
        fields = ["full_Address", "emergency_contact_person", "emergency_contact_number", "user_email","contact_number" ]
        labels = {"full_Address" : "Full Address", "emergency_contact_person" : "Emergency Contact Person", "emergency_contact_number" : "Emergency Contact Person's Contact No.", "user_email" : "Email Address", "contact_number" : "Contact Number" }

