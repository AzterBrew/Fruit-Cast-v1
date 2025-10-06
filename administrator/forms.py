from django import forms
from base.models import MunicipalityName, AccountType, CommodityType, Month, VerifiedHarvestRecord

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
        queryset=MunicipalityName.objects.exclude(pk=14),  # Exclude 'Overall' municipality
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'municipality-select'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Extract user from kwargs
        super().__init__(*args, **kwargs)
        self.fields['municipality'].widget.attrs['disabled'] = True  # Default disabled
        
        # If user is not a superuser, restrict account type to Agriculturist only
        if user and not user.is_superuser:
            self.fields['account_type'].choices = [('Agriculturist', 'Agriculturist')]
            self.fields['account_type'].initial = 'Agriculturist'
            self.fields['account_type'].widget.attrs.update({
                'readonly': True,
                'disabled': True,
                'class': 'form-select',
                'style': 'background-color: #f8f9fa; cursor: not-allowed;'
            })
            # Always enable municipality for non-superusers since they can only create agriculturists
            self.fields['municipality'].widget.attrs['disabled'] = False
            self.fields['municipality'].required = True


    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get("account_type")
        municipality = cleaned_data.get("municipality")

        # Agriculturists must have a municipality assigned
        if account_type == "Agriculturist" and not municipality:
            self.add_error("municipality", "Municipality is required for Agriculturist accounts.")
            
class CommodityTypeForm(forms.ModelForm):
    seasonal_months = forms.ModelMultipleChoiceField(queryset=Month.objects.all(),widget=forms.CheckboxSelectMultiple,required=False,label="Seasonal Months")
    years_to_mature = forms.DecimalField(label="Years to Mature", required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter years (e.g., 2.5)', 'step': '0.01'}))
    years_to_bearfruit = forms.DecimalField(label="Years to Bear Fruit after Maturing", required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter years (e.g., 0.5)', 'step': '0.01'}))
    
    class Meta:
        model = CommodityType
        fields = ['name', 'average_weight_per_unit_kg', 'seasonal_months', 'years_to_mature', 'years_to_bearfruit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter commodity name (e.g., Mango)'}),
            'average_weight_per_unit_kg': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter weight in kg (e.g., 4.50)', 'step': '0.001'}),
            'years_to_mature': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter years (e.g., 2.5)', 'step': '0.01'}),
            'years_to_bearfruit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter years (e.g., 0.5)', 'step': '0.01'}),
        }
        
class VerifiedHarvestRecordForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude pk=1 (usually 'Not Listed' or similar) from commodity choices
        self.fields['commodity_id'].queryset = CommodityType.objects.exclude(pk=1)
    
    class Meta:
        model = VerifiedHarvestRecord
        fields = [
            "harvest_date", "commodity_id", "total_weight_kg", "weight_per_unit_kg",
            "municipality", "barangay", "remarks"
        ]
        widgets = {
            "harvest_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "commodity_id": forms.Select(attrs={"class": "form-select"}),
            "total_weight_kg": forms.NumberInput(attrs={"class": "form-control"}),
            "weight_per_unit_kg": forms.NumberInput(attrs={"class": "form-control"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }