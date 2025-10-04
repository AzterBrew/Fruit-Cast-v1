#!/usr/bin/env python
"""Test script to debug Orani municipality registration issue"""
import os
import sys
import django

# Setup Django environment
if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fruitcast.settings")
    django.setup()

from base.models import Municipality, Barangay, AccountType, AccountStatus
from base.forms import RegistrationForm

def test_orani_registration():
    print("=" * 60)
    print("🔍 TESTING ORANI MUNICIPALITY REGISTRATION")
    print("=" * 60)
    
    # Check Orani municipality
    print("\n1. Checking Orani Municipality...")
    try:
        orani = Municipality.objects.get(pk=9)
        print(f"✅ Found Orani: {orani.municipality_name} (ID: {orani.municipality_id})")
    except Municipality.DoesNotExist:
        print("❌ Orani municipality (ID: 9) not found!")
        return
    
    # Check barangays for Orani
    print("\n2. Checking Barangays for Orani...")
    barangays = Barangay.objects.filter(municipality_id=9)
    print(f"📍 Found {barangays.count()} barangays for Orani:")
    for b in barangays[:5]:  # Show first 5
        print(f"   🔸 {b.barangay_name} (ID: {b.barangay_id})")
    if barangays.count() > 5:
        print(f"   ... and {barangays.count() - 5} more")
    
    if barangays.count() == 0:
        print("❌ No barangays found for Orani!")
        return
    
    # Check AccountType and AccountStatus
    print("\n3. Checking AccountType and AccountStatus...")
    farmer_types = AccountType.objects.filter(account_type__iexact="Farmer")
    verified_statuses = AccountStatus.objects.filter(acc_status__iexact="Verified")
    
    print(f"👤 AccountType 'Farmer': {farmer_types.count()} found")
    print(f"✅ AccountStatus 'Verified': {verified_statuses.count()} found")
    
    if farmer_types.count() == 0:
        print("❌ No 'Farmer' AccountType found!")
        return
    
    if verified_statuses.count() == 0:
        print("❌ No 'Verified' AccountStatus found!")
        return
    
    # Test form validation
    print("\n4. Testing Form Validation...")
    test_data = {
        'username': 'test_orani_user',
        'email': 'test@orani.com',
        'password1': 'ComplexPassword123!',
        'password2': 'ComplexPassword123!',
        'first_name': 'Test',
        'last_name': 'User',
        'middle_name': 'Middle',
        'suffix': '',
        'birthday': '1990-01-01',
        'sex': 'Male',
        'contact_number': '09123456789',
        'municipality': '9',  # Orani
        'barangay': str(barangays.first().barangay_id),  # First barangay
        'purok': 'Test Purok',
        'street': 'Test Street'
    }
    
    print(f"📝 Test data prepared with municipality: {test_data['municipality']}")
    print(f"📝 Test data prepared with barangay: {test_data['barangay']}")
    
    form = RegistrationForm(test_data)
    print(f"📋 Form created, checking validity...")
    
    if form.is_valid():
        print("✅ Form is valid!")
        print("📝 Form cleaned data:")
        for key, value in form.cleaned_data.items():
            print(f"   🔸 {key}: {value}")
    else:
        print("❌ Form validation failed!")
        print("🔥 Form errors:")
        for field, errors in form.errors.items():
            print(f"   🔸 {field}: {errors}")
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    test_orani_registration()