from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
# Create your models here.
from base.models import *


class Month(models.Model):
    name = models.CharField(max_length=20)  # e.g., "January"
    number = models.IntegerField()  # 1 = Jan, 12 = Dec

    def __str__(self):
        return self.name

class CommodityType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    average_weight_per_unit_kg = models.DecimalField(max_digits=10, decimal_places=3)
    unit_name = models.CharField(max_length=100)
    seasonal_months = models.ManyToManyField(Month, blank=True)

    def __str__(self):
        return self.name    

# sa admin panel, I should have checkboxes

class VerifiedHarvestRecord(models.Model):
    harvest_date = models.DateField()
    commodity_type = models.CharField(max_length=255)
    # commodity_type = models.ForeignKey(CommodityType, on_delete=models.CASCADE)  REPLACE WITH THIS PAGKA NAMODIFY NA YUNG PAG RECORD BY COMMTYPE TABLE NA DROPDOWN
    commodity_spec = models.CharField(max_length=255, blank=True, null=True)
    total_weight_kg = models.DecimalField(max_digits=10,decimal_places=2)  # Already converted to kg
    weight_per_unit_kg = models.DecimalField(max_digits=10,decimal_places=2)  # Already converted to kg
    harvest_municipality = models.CharField(null=True,blank=True,max_length=255)
    harvest_barangay = models.CharField(null=True,blank=True,max_length=255)
    remarks = models.TextField(blank=True, null=True)
    date_verified = models.DateTimeField(default=timezone.now)
    verified_by = models.ForeignKey('base.AdminInformation', on_delete=models.CASCADE, null=True, blank=True)
    prev_record = models.ForeignKey('base.HarvestRecord', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.commodity_type} ({self.total_weight_kg} kg) on {self.harvest_date}"

class VerifiedPlantRecord(models.Model):
    plant_date = models.DateField()
    commodity_type = models.CharField(max_length=255)
    # commodity_type = models.ForeignKey(CommodityType, on_delete=models.CASCADE)   REPLACE WITH THIS PAGKA NAMODIFY NA YUNG PAG RECORD BY COMMTYPE TABLE NA DROPDOWN
    commodity_spec = models.CharField(max_length=255, blank=True, null=True)
    expected_harvest_date = models.DateField(null=True, blank=True)
    estimated_weight_kg = models.DecimalField(max_digits=10,decimal_places=2, null=True, blank=True)
    plant_municipality = models.CharField(null=True,blank=True,max_length=255)
    plant_barangay = models.CharField(null=True,blank=True,max_length=255)
    min_expected_harvest = models.IntegerField()
    max_expected_harvest = models.IntegerField()
    average_harvest_units = models.DecimalField(max_digits=10,decimal_places=2)    #count toh, not weight
    land_area = models.FloatField()
    remarks = models.TextField(blank=True, null=True)
    date_verified = models.DateTimeField(default=timezone.now, null=True, blank=True)
    verified_by = models.ForeignKey('base.AdminInformation', on_delete=models.CASCADE, null=True, blank=True)
    prev_record = models.ForeignKey('base.PlantRecord', on_delete=models.SET_NULL, null=True, blank=True)
    # latitude = models.FloatField(null=True, blank=True)
    # longitude = models.FloatField(null=True, blank=True)
# average_harvest_units = (min_expected_harvest + max_expected_harvest) / 2
# estimated_weight_kg = average_harvest_units * avg_weight_per_unit_kg [avg weight per unit will be on the commodity type table]

    def __str__(self):
        return f"{self.commodity_type} ({self.estimated_weight_kg} kg est.) on {self.plant_date}"



class ForecastResult(models.Model):
    municipality = models.CharField(max_length=100)
    commodity_type = models.CharField(max_length=100)
    forecast_month = models.CharField(max_length=50)  # e.g. "Dry", "Wet", or even a specific month/quarter
    forecast_year = models.IntegerField()
    forecasted_amount = models.FloatField()  # in kg, tons, etc.

    generated_at = models.DateTimeField(default=timezone.now)
    source_data_last_updated = models.DateTimeField()  # timestamp of the latest harvest data used

    class Meta:
        unique_together = ('municipality', 'commodity_type', 'forecast_month', 'forecast_year')

    def __str__(self):
        return f"{self.commodity_type} forecast in {self.municipality.name} for {self.forecast_month} {self.forecast_year}"


class Notification(models.Model):
    account_id = models.ForeignKey('base.AccountsInformation', on_delete=models.CASCADE)  # Link to AccountsInformation
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.account_info.userinfo_id.firstname} {self.account_info.userinfo_id.lastname} at {self.created_at}"


# plans for commodity type model: if the input type by users that are not in the commodity type table, 
# then it would take the data from their input and there is no defined average weight per unit


