from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
# Create your models here.
from base.models import *


# class Month(models.Model):
#     name = models.CharField(max_length=20)  # e.g., "January"
#     number = models.IntegerField()  # 1 = Jan, 12 = Dec

#     def __str__(self):
#         return self.name

# class CommodityType(models.Model):
#     name = models.CharField(max_length=255, unique=True)
#     average_weight_per_unit_kg = models.DecimalField(max_digits=10, decimal_places=3)
#     unit_name = models.CharField(max_length=100)
#     seasonal_months = models.ManyToManyField(Month, blank=True)

#     def __str__(self):
#         return self.name    

# sa admin panel, I should have checkboxes

class VerifiedHarvestRecord(models.Model):
    harvest_date = models.DateField()
    commodity_id = models.ForeignKey('base.CommodityType', on_delete=models.CASCADE)    # commodity_type = models.ForeignKey(CommodityType, on_delete=models.CASCADE)  REPLACE WITH THIS PAGKA NAMODIFY NA YUNG PAG RECORD BY COMMTYPE TABLE NA DROPDOWN
    total_weight_kg = models.DecimalField(max_digits=10,decimal_places=2)  # Already converted to kg
    weight_per_unit_kg = models.DecimalField(max_digits=10,decimal_places=2)  # Already converted to kg
    @property
    def estimated_unit_count(self):
        if self.weight_per_unit_kg:
            return self.total_weight_kg / self.weight_per_unit_kg
        return None
    
    municipality = models.ForeignKey('base.MunicipalityName', on_delete=models.SET_NULL, null=True, blank=True)
    barangay = models.ForeignKey('base.BarangayName', on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    date_verified = models.DateTimeField(default=timezone.now)
    verified_by = models.ForeignKey('base.AdminInformation', on_delete=models.CASCADE, null=True, blank=True)
    prev_record = models.ForeignKey('base.initHarvestRecord', on_delete=models.SET_NULL, null=True, blank=True)  #this connects to initial versoin thats also connected to the record table, which has hte location
    
    def __str__(self):
        return f"{self.commodity_id} ({self.total_weight_kg} kg) on {self.harvest_date}"

class VerifiedPlantRecord(models.Model):
    plant_date = models.DateField()
    commodity_id = models.ForeignKey('base.CommodityType', on_delete=models.CASCADE)    # commodity_type = models.ForeignKey(CommodityType, on_delete=models.CASCADE)  REPLACE WITH THIS PAGKA NAMODIFY NA YUNG PAG RECORD BY COMMTYPE TABLE NA DROPDOWN
    min_expected_harvest = models.DecimalField(max_digits=10, decimal_places=3)
    max_expected_harvest = models.DecimalField(max_digits=10, decimal_places=3)
    average_harvest_units = models.DecimalField(max_digits=10,decimal_places=2)    #count toh, not weight
    estimated_weight_kg = models.DecimalField(max_digits=10,decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    municipality = models.ForeignKey('base.MunicipalityName', on_delete=models.SET_NULL, null=True, blank=True)
    barangay = models.ForeignKey('base.BarangayName', on_delete=models.SET_NULL, null=True, blank=True)
    date_verified = models.DateTimeField(default=timezone.now, null=True, blank=True)
    verified_by = models.ForeignKey('base.AdminInformation', on_delete=models.CASCADE, null=True, blank=True)
    prev_record = models.ForeignKey('base.initPlantRecord', on_delete=models.SET_NULL, null=True, blank=True)

# average_harvest_units = (min_expected_harvest + max_expected_harvest) / 2
# estimated_weight_kg = average_harvest_units * avg_weight_per_unit_kg [avg weight per unit will be on the commodity type table]

    def __str__(self):
        return f"{self.commodity_id} ({self.estimated_weight_kg} kg est.) on {self.plant_date}"


class Notification(models.Model):
    account = models.ForeignKey('base.AccountsInformation', on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    notification_type = models.CharField(max_length=50, default="general")
    scheduled_for = models.DateTimeField(null=True, blank=True)
    linked_plant_record = models.ForeignKey('base.initPlantRecord', on_delete=models.SET_NULL, null=True, blank=True)
    redirect_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"Notif for {self.account.userinfo_id.firstname} {self.account.userinfo_id.lastname} - {self.message[:30]}"


class ForecastBatch(models.Model):
    batch_id = models.BigAutoField(primary_key=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey('base.AdminInformation', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Forecast Batch {self.batch_id} at {self.generated_at.strftime('%Y-%m-%d %H:%M')}"

class ForecastResult(models.Model):
    forecast_id = models.BigAutoField(primary_key=True)
    batch = models.ForeignKey(ForecastBatch, on_delete=models.CASCADE, null=True, blank=True, related_name='results')
    commodity = models.ForeignKey('base.CommodityType', on_delete=models.CASCADE)
    forecast_month = models.ForeignKey('base.Month', on_delete=models.CASCADE)
    forecast_year = models.IntegerField()
    municipality = models.ForeignKey('base.MunicipalityName', on_delete=models.CASCADE)
    # barangay = models.ForeignKey('base.BarangayName', on_delete=models.SET_NULL, null=True, blank=True)
    forecasted_amount_kg = models.FloatField()
    # forecasted_count_units = models.FloatField(null=True, blank=True)
    # seasonal_boost_applied = models.BooleanField(default=False)
    source_data_last_updated = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.commodity.name} - {self.forecast_month}/{self.forecast_year} in {self.municipality.municipality}"

# only model left unchanged


# class ForecastResult(models.Model):
#     municipality = models.CharField(max_length=100)
#     commodity_type = models.CharField(max_length=100)
#     forecast_month = models.CharField(max_length=50)  # e.g. "Dry", "Wet", or even a specific month/quarter
#     forecast_year = models.IntegerField()
#     forecasted_amount = models.FloatField()  # in kg, tons, etc.

#     generated_at = models.DateTimeField(default=timezone.now)
#     source_data_last_updated = models.DateTimeField()  # timestamp of the latest harvest data used

#     class Meta:
#         unique_together = ('municipality', 'commodity_type', 'forecast_month', 'forecast_year')

#     def __str__(self):
#         return f"{self.commodity_type} forecast in {self.municipality.name} for {self.forecast_month} {self.forecast_year}"




# plans for commodity type model: if the input type by users that are not in the commodity type table, 
# then it would take the data from their input and there is no defined average weight per unit


