#!/usr/bin/env python3
"""
Test script to verify CSV upload functionality
"""
import csv
import io
from datetime import datetime

def test_multiple_date_formats():
    """Test multiple date format parsing"""
    test_dates = [
        "2024-08-15",  # YYYY-MM-DD
        "15/08/2024",  # DD/MM/YYYY
        "08/15/2024",  # MM/DD/YYYY (should work)
        "2024/08/15",  # YYYY/MM/DD (should fail)
        "invalid"      # Invalid format
    ]
    
    date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
    
    for test_date in test_dates:
        parsed = None
        format_used = None
        
        for date_format in date_formats:
            try:
                parsed = datetime.strptime(test_date, date_format).date()
                format_used = date_format
                break
            except ValueError:
                continue
        
        if parsed:
            print(f"✅ '{test_date}' -> {parsed} (using {format_used})")
        else:
            print(f"❌ '{test_date}' -> Invalid date format")

def test_municipality_matching():
    """Test municipality name matching"""
    municipalities = ["Balanga City", "Abucay", "Bagac", "Dinalupihan"]
    test_names = ["Balanga", "balanga", "BALANGA", "Balanga City", "balanga city", "Abucay", "abucay"]
    
    for test_name in test_names:
        if test_name.lower() == 'balanga':
            normalized = 'Balanga City'
        else:
            normalized = test_name
            
        # Find exact match (case-insensitive)
        found = None
        for muni in municipalities:
            if muni.lower() == normalized.lower():
                found = muni
                break
        
        if found:
            print(f"✅ '{test_name}' -> '{found}'")
        else:
            print(f"❌ '{test_name}' -> No match found")

def test_encoding_support():
    """Test encoding support for special characters"""
    test_data = [
        "Balañga,Mañgo,100.5",
        "Hermosa,Piña,75.0",
        "Orión,Calamansi,25.25",
        "Regular,Apple,50.0"
    ]
    
    # Test different encodings
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for data in test_data:
        print(f"\nTesting: {data}")
        
        for encoding in encodings:
            try:
                # Simulate encoding then decoding
                encoded = data.encode(encoding)
                decoded = encoded.decode(encoding)
                print(f"  ✅ {encoding}: {decoded}")
                break
            except UnicodeEncodeError:
                print(f"  ❌ {encoding}: Encoding failed")
            except UnicodeDecodeError:
                print(f"  ❌ {encoding}: Decoding failed")

if __name__ == "__main__":
    print("🧪 Testing CSV Upload Functionality\n")
    
    print("1. Testing Multiple Date Formats:")
    print("-" * 40)
    test_multiple_date_formats()
    
    print("\n2. Testing Municipality Name Matching:")
    print("-" * 40)
    test_municipality_matching()
    
    print("\n3. Testing Encoding Support:")
    print("-" * 40)
    test_encoding_support()
    
    print("\n✅ All tests completed!")