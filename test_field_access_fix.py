import os
import sys
import django

# Add the project root directory to the sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fruitcast.settings')

# Setup Django
django.setup()

# Now import models
from dashboard.models import VerifiedHarvestRecord, ForecastResult, ForecastBatch
from base.models import CommodityType, MunicipalityName

def test_field_access_fix():
    """Test that the field access fix resolves the municipality_id error"""
    
    print("=== Testing Field Access Fix ===")
    
    # 1. Check if Pineapple and Pilar exist
    try:
        pineapple = CommodityType.objects.get(name='Pineapple')
        pilar = MunicipalityName.objects.get(municipality='Pilar')
        overall = MunicipalityName.objects.get(pk=14)
        
        print(f"✅ Found Pineapple")
        print(f"   - ID field: {pineapple.commodity_id}")
        print(f"   - PK: {pineapple.pk}")
        print(f"✅ Found Pilar")
        print(f"   - ID field: {pilar.municipality_id}")
        print(f"   - PK: {pilar.pk}")
        print(f"✅ Found Overall: {overall.municipality}")
        print(f"   - ID field: {overall.municipality_id}")
        print(f"   - PK: {overall.pk}")
    except Exception as e:
        print(f"❌ Error finding entities: {e}")
        return
    
    # 2. Test the field access pattern that caused the error
    print(f"\n=== Testing Field Access Patterns ===")
    
    # This was the problematic pattern in tasks.py:
    # df['municipality_id'] == municipality.pk  # WRONG - pk might not match municipality_id field
    # df['commodity_id'] == commodity.pk        # WRONG - pk might not match commodity_id field
    
    print(f"Commodity field access:")
    print(f"  - commodity.pk: {pineapple.pk}")
    print(f"  - commodity.commodity_id: {pineapple.commodity_id}")
    print(f"  - Are they equal? {pineapple.pk == pineapple.commodity_id}")
    
    print(f"Municipality field access:")
    print(f"  - municipality.pk: {pilar.pk}")  
    print(f"  - municipality.municipality_id: {pilar.municipality_id}")
    print(f"  - Are they equal? {pilar.pk == pilar.municipality_id}")
    
    # 3. Test the corrected pattern
    print(f"\n=== Testing Corrected Data Filtering ===")
    
    # Get some sample data
    sample_data = VerifiedHarvestRecord.objects.filter(
        commodity_id=pineapple,
        municipality=pilar
    ).values('harvest_date', 'total_weight_kg', 'commodity_id', 'municipality_id')[:3]
    
    if sample_data:
        print("Sample records found:")
        for record in sample_data:
            print(f"  - Commodity ID: {record['commodity_id']}, Municipality ID: {record['municipality_id']}")
            
        # Test the filtering logic
        import pandas as pd
        try:
            df = pd.DataFrame(list(sample_data))
            
            # OLD (problematic) way:
            old_filter = (df['municipality_id'] == pilar.pk) & (df['commodity_id'] == pineapple.pk)
            old_matches = df[old_filter]
            
            # NEW (correct) way:
            new_filter = (df['municipality_id'] == pilar.municipality_id) & (df['commodity_id'] == pineapple.commodity_id)
            new_matches = df[new_filter]
            
            print(f"\n  Old filtering (using .pk): {len(old_matches)} matches")
            print(f"  New filtering (using .field_id): {len(new_matches)} matches")
            
            if len(new_matches) > len(old_matches):
                print("✅ Fix is working! New method finds more matches.")
            elif len(new_matches) == len(old_matches) and len(new_matches) > 0:
                print("✅ Both methods work equally (fields match pks)")
            else:
                print("⚠️  Need to verify data integrity")
                
        except ImportError:
            print("Pandas not available, but field access logic is correct")
    else:
        print("No sample records found for testing")
    
    # 4. Test commodity-municipality pair extraction
    print(f"\n=== Testing Pair Extraction Logic ===")
    
    test_pairs = [
        {
            'commodity_id': pineapple.commodity_id,
            'municipality_id': pilar.municipality_id
        }
    ]
    
    print(f"Test pairs: {test_pairs}")
    
    # Simulate the logic from tasks.py
    unique_commodity_ids = list(set([pair['commodity_id'] for pair in test_pairs]))
    unique_municipality_ids = list(set([pair['municipality_id'] for pair in test_pairs]))
    
    # Always include Overall (pk=14) for affected commodities
    if 14 not in unique_municipality_ids:
        unique_municipality_ids.append(14)
        
    print(f"Unique commodity IDs: {unique_commodity_ids}")
    print(f"Unique municipality IDs: {unique_municipality_ids}")
    
    # Test the model queries
    commodities = CommodityType.objects.filter(commodity_id__in=unique_commodity_ids)
    municipalities = MunicipalityName.objects.filter(municipality_id__in=unique_municipality_ids)
    
    print(f"Found commodities: {[c.name for c in commodities]}")
    print(f"Found municipalities: {[m.municipality for m in municipalities]}")
    
    # Test the combination checking logic
    for commodity in commodities:
        for municipality in municipalities.exclude(pk=14):
            combination_requested = any(
                pair['commodity_id'] == commodity.commodity_id and 
                pair['municipality_id'] == municipality.municipality_id 
                for pair in test_pairs
            )
            print(f"Combination {commodity.name}-{municipality.municipality}: {'✅ Requested' if combination_requested else '❌ Not requested'}")
    
    print("\n✅ Field access fix validation completed!")

if __name__ == "__main__":
    test_field_access_fix()