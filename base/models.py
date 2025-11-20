from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from dashboard.models import * 

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and return a regular user with an email and password.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and return a superuser with an email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(email, password, **extra_fields)

    
class AuthUser(AbstractBaseUser):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
    
    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser
    
class AccountType(models.Model):
    account_type_id = models.BigAutoField(primary_key=True)
    account_type = models.CharField(max_length=50)
    # [Farmer, Agriculturist, Administrator]
    
class AccountStatus(models.Model):
    acc_stat_id = models.BigAutoField(primary_key=True)
    acc_status = models.CharField(max_length=50)    
    # NEWNEWNEW which should be inclusive of recordtransaction status 
    # Verified 2 
    # Pending 3 
    # Rejected 4
    # Archived 5
    # Suspended 6 
    # Removed 1

class MunicipalityName(models.Model):
    municipality_id = models.BigAutoField(primary_key=True)
    municipality = models.CharField(max_length=50)
    
    def __str__(self):
        return self.municipality
    
class BarangayName(models.Model):
    barangay_id = models.BigAutoField(primary_key=True)
    barangay = models.CharField(max_length=100) 
    municipality_id = models.ForeignKey(MunicipalityName,on_delete=models.CASCADE)
    
    def __str__(self):
        return self.barangay

class UserInformation(models.Model):
    auth_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  
    userinfo_id = models.BigAutoField(primary_key=True)
    lastname = models.CharField(max_length=255)
    firstname = models.CharField(max_length=255)
    middlename = models.CharField(max_length=255, blank=True, default="")
    nameextension = models.CharField(max_length=10, blank=True, default="")
    sex = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=20)
    user_email = models.EmailField(max_length=254)
    birthdate = models.DateField()
    emergency_contact_person = models.CharField(max_length=255)
    emergency_contact_number = models.CharField(max_length=20)
    address_details = models.CharField(max_length=255)
    barangay_id = models.ForeignKey(BarangayName,on_delete=models.CASCADE)
    municipality_id = models.ForeignKey(MunicipalityName,on_delete=models.CASCADE)
    religion = models.CharField(max_length=255,blank=True, default="", null=True)
    civil_status = models.CharField(max_length=50)
    rsbsa_ref_number = models.CharField(max_length=22, unique=True, null=True, blank=True, verbose_name="RSBSA Reference Number")
    hasfarmland = models.BooleanField(default=False)

class AdminInformation(models.Model):
    admin_id = models.BigAutoField(primary_key=True)
    first_added = models.DateTimeField(default=timezone.now)
    userinfo_id = models.ForeignKey(UserInformation, on_delete=models.CASCADE)
    municipality_incharge = models.ForeignKey(MunicipalityName, on_delete=models.CASCADE)
    @property
    def account_type(self):
        acc_info = AccountsInformation.objects.filter(userinfo_id=self.userinfo_id).select_related('account_type_id').first()
        if acc_info and acc_info.account_type_id:
            return acc_info.account_type_id.account_type
        return "Unknown"
        
class AccountsInformation(models.Model):
    account_id = models.BigAutoField(primary_key=True)
    account_register_date = models.DateTimeField()
    account_isverified = models.BooleanField(default=False)
    account_verified_date = models.DateTimeField(null=True, blank=True)
    account_verified_by = models.ForeignKey(AdminInformation, on_delete=models.CASCADE, null=True, blank=True)
    account_type_id = models.ForeignKey(AccountType, on_delete=models.CASCADE)
    acc_status_id = models.ForeignKey(AccountStatus, on_delete=models.CASCADE)    
    userinfo_id = models.ForeignKey(UserInformation, on_delete=models.CASCADE)
    

class UserLoginLog(models.Model):
    userlogin_id = models.BigAutoField(primary_key=True)
    account_id = models.ForeignKey(AccountsInformation,  on_delete=models.CASCADE)
    login_date = models.DateTimeField(auto_now_add=True)
    
    
class AdminUserManagement(models.Model):
    log_id = models.BigAutoField(primary_key=True)
    admin_id = models.ForeignKey(AdminInformation, on_delete=models.CASCADE)
    action_timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=255) # e.g., "Verified", "Rejected", "Archived"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f"Admin {self.admin_id} {self.action} on {self.content_type.model} ID {self.object_id}"
    
    
    
class FarmLand(models.Model):
    farminfo_id = models.BigAutoField(primary_key=True)
    farmland_name = models.CharField(max_length=255, default="")
    userinfo_id = models.ForeignKey(UserInformation, on_delete=models.CASCADE)
    municipality = models.ForeignKey(MunicipalityName, on_delete=models.CASCADE)
    barangay = models.ForeignKey(BarangayName,on_delete=models.CASCADE)
    estimated_area = models.FloatField(null=True,blank=True)
    
    def __str__(self):
        if self.estimated_area:
            return f"{self.farmland_name} ({self.estimated_area} hectares)"
        else :
            return self.farmland_name


class Month(models.Model):
    month_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=20)  # e.g., "January"
    number = models.IntegerField()  # 1 = Jan, 12 = Dec

    class Meta:
        ordering = ['number']
        
    def __str__(self):
        return self.name

class UnitMeasurement(models.Model):
    unit_id = models.BigAutoField(primary_key=True)
    unit_abrv = models.CharField(max_length=20)
    unit_full = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.unit_full} ({self.unit_abrv})"
    
class CommodityType(models.Model):
    commodity_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    average_weight_per_unit_kg = models.DecimalField(max_digits=10, decimal_places=3)
    seasonal_months = models.ManyToManyField(Month, blank=True)
    years_to_mature = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Number of years from planting to first harvest")
    years_to_bearfruit = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Number of years from first harvest to the next fruit bearing")
    def __str__(self):
        return self.name    


STATUS_CHOICES = [
    ('none', 'None'),
    ('submitted', 'Submitted'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
]
# choices for em record transaction

LOCATION_TYPE_CHOICES = [
    ('farm_land', 'Farm Land'),
    ('manual', 'Manual Input'),
]

# choices if user chooses farmland na owned nila o manual input lime municipality and barangay 

class RecordTransaction (models.Model):
    transaction_id = models.BigAutoField(primary_key=True)
    account_id = models.ForeignKey(AccountsInformation, on_delete=models.CASCADE)
    transaction_date = models.DateTimeField(default=timezone.now)
    date_verified = models.DateTimeField(null=True, blank=True)
    planting_failed = models.BooleanField(default=False)
    failure_reason = models.TextField(blank=True, null=True)
    location_type = models.CharField(choices=LOCATION_TYPE_CHOICES, max_length=20, default='manual')
    farm_land = models.ForeignKey(FarmLand, null=True, blank=True, on_delete=models.SET_NULL)
    manual_municipality = models.ForeignKey(MunicipalityName, null=True, blank=True, on_delete=models.SET_NULL)
    manual_barangay = models.ForeignKey(BarangayName, null=True, blank=True, on_delete=models.SET_NULL)
    
    def get_location_display(self):
        if self.location_type == 'farm_land' and self.farm_land:
            return f"{self.farm_land.farmland_name} - {self.farm_land.municipality.municipality}, {self.farm_land.barangay.barangay}"
        elif self.manual_barangay and self.manual_municipality:
            return f"{self.manual_barangay}, {self.manual_municipality}"
        elif self.manual_municipality:
            return f"{self.manual_municipality}"
        return "No location set"
    
class initPlantRecord(models.Model):
    plant_id = models.BigAutoField(primary_key=True)
    transaction = models.OneToOneField(RecordTransaction, on_delete=models.CASCADE)
    
    date_recorded = models.DateTimeField(default=timezone.now)
    plant_date = models.DateField()
    commodity_id = models.ForeignKey(CommodityType, on_delete=models.CASCADE)
    commodity_custom = models.CharField(max_length=255, blank=True)  # "Other"
    record_status = models.ForeignKey(AccountStatus, on_delete=models.CASCADE, null=True, blank=True, related_name='plant_status_transactions')
    min_expected_harvest = models.DecimalField(max_digits=10, decimal_places=3)
    max_expected_harvest = models.DecimalField(max_digits=10, decimal_places=3)
    remarks = models.TextField(blank=True)
    verified_by = models.ForeignKey(AdminInformation, on_delete=models.CASCADE, null=True, blank=True)
    date_verified = models.DateTimeField(default=timezone.now, null=True, blank=True)

class initHarvestRecord(models.Model):
    harvest_id = models.BigAutoField(primary_key=True)
    transaction = models.ForeignKey(RecordTransaction, on_delete=models.CASCADE)

    harvest_date = models.DateField()
    commodity_id = models.ForeignKey(CommodityType, on_delete=models.CASCADE)
    commodity_custom = models.CharField(max_length=255, blank=True)
    record_status = models.ForeignKey(AccountStatus, on_delete=models.CASCADE, null=True, blank=True, related_name='harvest_status_transactions')
    total_weight = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.ForeignKey(UnitMeasurement, on_delete=models.CASCADE)
    remarks = models.TextField(blank=True)
    verified_by = models.ForeignKey(AdminInformation, on_delete=models.CASCADE, null=True, blank=True)
    date_verified = models.DateTimeField(default=timezone.now, null=True, blank=True)
