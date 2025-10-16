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
from administrator.tasks import retrain_selective_models_task
from dashboard.models import VerifiedHarvestRecord, ForecastResult, ForecastBatch
from base.models import CommodityType, MunicipalityName

def test_selective_retraining_fix():
    """Test the selective retraining fix"""
    
    print("=== Testing Selective Retraining Fix ===")
    
    # 1. Check if Pineapple and Pilar exist
    try:
        pineapple = CommodityType.objects.get(name='Pineapple')
        pilar = MunicipalityName.objects.get(municipality='Pilar')
        overall = MunicipalityName.objects.get(pk=14)
        
        print(f"✅ Found Pineapple (ID: {pineapple.commodity_id})")
        print(f"✅ Found Pilar (ID: {pilar.municipality_id})")
        print(f"✅ Found Overall (ID: {overall.municipality_id}): {overall.municipality}")
    except Exception as e:
        print(f"❌ Error finding entities: {e}")
        return
    
    # 2. Check existing data
    pilar_pineapple_records = VerifiedHarvestRecord.objects.filter(
        commodity_id=pineapple,
        municipality=pilar
    ).count()
    
    overall_pineapple_records = VerifiedHarvestRecord.objects.filter(
        commodity_id=pineapple
    ).exclude(municipality_id=14).count()
    
    print(f"\nData availability:")
    print(f"📊 Pilar-Pineapple records: {pilar_pineapple_records}")
    print(f"📊 Total Pineapple records (for Overall): {overall_pineapple_records}")
    
    # 3. Check current forecasts before test
    pilar_forecasts = ForecastResult.objects.filter(
        commodity=pineapple,
        municipality=pilar
    ).count()
    
    overall_forecasts = ForecastResult.objects.filter(
        commodity=pineapple,
        municipality=overall
    ).count()
    
    print(f"\nCurrent forecasts:")
    print(f"🔮 Pilar-Pineapple forecasts: {pilar_forecasts}")
    print(f"🔮 Overall-Pineapple forecasts: {overall_forecasts}")
    
    # 4. Test the selective retraining call
    print(f"\n=== Testing Selective Retraining Call ===")
    
    commodity_municipality_pairs = [
        {
            'commodity_id': pineapple.commodity_id,
            'municipality_id': pilar.municipality_id
        }
    ]
    
    print(f"Test pairs: {commodity_municipality_pairs}")
    
    # Manual call (without Celery) to test the function directly
    try:
        from administrator.tasks import retrain_selective_models_task
        # Call the function directly to test the logic
        result = retrain_selective_models_task(commodity_municipality_pairs)
        print(f"✅ Selective retraining completed: {result}")
        
        # Check forecasts after retraining
        new_pilar_forecasts = ForecastResult.objects.filter(
            commodity=pineapple,
            municipality=pilar
        ).count()
        
        new_overall_forecasts = ForecastResult.objects.filter(
            commodity=pineapple,
            municipality=overall
        ).count()
        
        print(f"\nForecasts after retraining:")
        print(f"🔮 Pilar-Pineapple forecasts: {new_pilar_forecasts}")
        print(f"🔮 Overall-Pineapple forecasts: {new_overall_forecasts}")
        
        if new_overall_forecasts > 0:
            print("✅ Overall forecasts are correctly generated!")
        else:
            print("❌ Overall forecasts are missing!")
            
    except Exception as e:
        print(f"❌ Error during selective retraining: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_selective_retraining_fix()