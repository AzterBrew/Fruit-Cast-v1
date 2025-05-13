from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from dashboard.models import * 
# Create your models here.
# class ExtendedUser(models.Model):
#     user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     created = models.DateTimeField(auto_now_add=True)
#     phone_number = models.IntegerField(blank=True, null=True)  

# superuser is 
# email : emmsumbad
# pass : moasumbad

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
    
# I NEED TO REMIGRATE 
class AccountType(models.Model):
    account_type_id = models.BigAutoField(primary_key=True)
    account_type = models.CharField(max_length=50)
    
class ItemStatus(models.Model):
    item_status_id = models.BigAutoField(primary_key=True)
    item_status = models.CharField(max_length=50)    

class UserInformation(models.Model):
    auth_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)    
    userinfo_id = models.BigAutoField(primary_key=True)
    lastname = models.CharField(max_length=255)
    firstname = models.CharField(max_length=255)
    middlename = models.CharField(max_length=255, blank=True, default="")
    nameextension = models.CharField(max_length=10, blank=True, default="")
    sex = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=15)
    user_email = models.EmailField(max_length=254)
    birthdate = models.DateField()
    emergency_contact_person = models.CharField(max_length=255)
    emergency_contact_number = models.CharField(max_length=15)
    address_details = models.CharField(max_length=255)
    barangay = models.CharField(max_length=255)
    municipality = models.CharField(max_length=255)
    religion = models.CharField(max_length=255)
    civil_status = models.CharField(max_length=50)
    rsbsa_ref_number = models.CharField(max_length=22, unique=True, null=True, blank=True, verbose_name="RSBSA Reference Number")
    

class AdminInformation(models.Model):
    admin_id = models.BigAutoField(primary_key=True)
    userinfo_id = models.ForeignKey(UserInformation, on_delete=models.CASCADE)
    role = models.CharField(max_length=255)
    first_added = models.DateTimeField(default=timezone.now)
    
class AccountsInformation(models.Model):
    account_id = models.BigAutoField(primary_key=True)
    userinfo_id = models.ForeignKey(UserInformation, on_delete=models.CASCADE)
    account_type_id = models.ForeignKey(AccountType, on_delete=models.CASCADE)
    item_status_id = models.ForeignKey(ItemStatus, on_delete=models.CASCADE)
    account_register_date = models.DateTimeField()
    account_verified_date = models.DateTimeField(null=True, blank=True)
    account_isverified = models.BooleanField(default=False) #default na false since di verified agad
    account_verified_by = models.ForeignKey(AdminInformation, on_delete=models.CASCADE, null=True, blank=True)

class UserLoginLog(models.Model):
    userlogin_id = models.BigAutoField(primary_key=True)
    account_id = models.ForeignKey(AccountsInformation,  on_delete=models.CASCADE)
    login_date = models.DateTimeField(auto_now_add=True)

class Transaction(models.Model):
    transaction_id = models.BigAutoField(primary_key=True)
    account_id = models.ForeignKey(AccountsInformation, on_delete=models.CASCADE)
    transaction_date = models.DateTimeField(default=timezone.now)
    # transaction_date = models.DateTimeField(auto_now=True)
    transaction_type = models.CharField(max_length=255) #this is if harvest o plant type
    item_status_id = models.ForeignKey(ItemStatus, on_delete=models.CASCADE, related_name="transaction_status")
    tr_verified_date = models.DateTimeField(null=True, blank=True)
    tr_isverified = models.BooleanField(default=False) #default na false since di verified agad
    tr_verified_by = models.ForeignKey(AdminInformation, on_delete=models.CASCADE, null=True, blank=True)

class HarvestRecord(models.Model):
    harvest_id = models.BigAutoField(primary_key=True)
    transaction_id = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    harvest_date = models.DateField()
    commodity_type = models.CharField(null=True,max_length=255)
    # commodity_type = models.ForeignKey('dashboard.CommodityType', on_delete=models.CASCADE, null=True)
    commodity_spec = models.CharField(max_length=255, blank=True)
    total_weight = models.DecimalField(max_digits=10,decimal_places=2)
    unit = models.CharField(max_length=50)
    weight_per_unit = models.DecimalField(max_digits=10,decimal_places=2)
    harvest_location = models.CharField(max_length=255)
    remarks = models.TextField(blank=True)

class PlantRecord(models.Model):
    plant_id = models.BigAutoField(primary_key=True)
    transaction_id = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    plant_date = models.DateField()
    commodity_type = models.CharField(max_length=255)
    commodity_spec = models.CharField(max_length=255,blank=True)
    expected_harvest_date = models.DateField()
    plant_location = models.CharField(max_length=255)
    min_expected_harvest = models.IntegerField()
    max_expected_harvest = models.IntegerField()
    land_area = models.FloatField()
    remarks = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)



# BTW CHange the account_register_date in the Accounts table as NULL




