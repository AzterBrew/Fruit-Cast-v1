from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from dashboard.models import *

# class CommodityTypeForm(forms.ModelForm):
#     class Meta:
#         model = CommodityType
#         fields = ['name', 'average_weight_per_unit_kg', 'unit_name', 'seasonal_months']
#         widgets = {
#             'seasonal_months': forms.CheckboxSelectMultiple(),  # or SelectMultiple
#         }