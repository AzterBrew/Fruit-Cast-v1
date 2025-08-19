from django import forms
from base.models import MunicipalityName, AccountType, CommodityType, Month

ACCOUNT_TYPE_CHOICES = [
    ('Administrator', 'Administrator'),
    ('Agriculturist', 'Agriculturist'),
]

SEX_CHOICES = [
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other')
]

class AssignAdminAgriForm(forms.Form):
    first_name = forms.CharField(label="First Name *",max_length=50,widget=forms.TextInput(attrs={'class': 'form-control','required': 'required','placeholder': 'Enter first name'}))
    middle_name = forms.CharField(label="Middle Name",max_length=50,required=False,widget=forms.TextInput(attrs={'class': 'form-control','placeholder': 'Optional'}))
    last_name = forms.CharField(label="Last Name *",max_length=50,widget=forms.TextInput(attrs={'class': 'form-control','required': 'required','placeholder': 'Enter last name'}))
    email = forms.EmailField(label="Email *",required=True,widget=forms.EmailInput(attrs={'class': 'form-control','required': 'required','placeholder': 'example@email.com'}))
    sex = forms.ChoiceField(label="Sex *",choices=SEX_CHOICES,widget=forms.RadioSelect(attrs={'class': 'form-check-input','required': 'required'}))
    account_type = forms.ChoiceField(label="Account Type *",choices=ACCOUNT_TYPE_CHOICES,widget=forms.Select(attrs={'class': 'form-select','required': 'required'}))
    municipality = forms.ModelChoiceField(
        label="Municipality",
        queryset=MunicipalityName.objects.all(),  # Exclude 'Overall' by default
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'municipality-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['municipality'].widget.attrs['disabled'] = True  # Default disabled


    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get("account_type")
        municipality = cleaned_data.get("municipality")

        # Agriculturists must have a municipality assigned
        if account_type == "Agriculturist" and not municipality:
            self.add_error("municipality", "Municipality is required for Agriculturist accounts.")
            
class CommodityTypeForm(forms.ModelForm):
    seasonal_months = forms.ModelMultipleChoiceField(queryset=Month.objects.all(),widget=forms.CheckboxSelectMultiple,required=False,label="Seasonal Months")
    years_to_mature = forms.IntegerField(label="Years to Mature", required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter years to mature'}))
    
    class Meta:
        model = CommodityType
        fields = ['name', 'average_weight_per_unit_kg', 'seasonal_months', 'years_to_mature']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'average_weight_per_unit_kg': forms.NumberInput(attrs={'class': 'form-control'}),
            'years_to_mature': forms.NumberInput(attrs={'class': 'form-control'}),
        }