#!/usr/bin/env python
"""
Test script to diagnose the forecast data availability issue after selective retraining.
"""
import os
import sys
import django
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fruitcast.settings')
django.setup()

from dashboard.models import ForecastResult, ForecastBatch
from dashboard.utils import get_latest_forecasts_by_combination
from base.models import CommodityType, MunicipalityName
# Don't import views with missing dependencies

def main():
    print("=== Testing Fix for Forecast Availability Issue ===\n")
    
    # Test with combinations that should have data after selective retraining
    try:
        # Test Papaya - Dinalupihan (recent batch 269)
        papaya = CommodityType.objects.get(name="Papaya") 
        dinalupihan = MunicipalityName.objects.get(municipality="Dinalupihan")
        
        print(f"=== Testing: {papaya.name} - {dinalupihan.municipality} ===")
        
        # Test the utility function directly
        base_qs = ForecastResult.objects.filter(
            commodity_id=papaya.commodity_id,
            municipality_id=dinalupihan.municipality_id
        )
        latest_forecasts = get_latest_forecasts_by_combination(base_qs).order_by('forecast_year', 'forecast_month__number')
        
        print(f"✅ Found {latest_forecasts.count()} forecast results for {papaya.name} - {dinalupihan.municipality}")
        
        if latest_forecasts.count() > 0:
            print("Sample forecast results:")
            for forecast in latest_forecasts[:5]:
                print(f"  {forecast.forecast_month.name} {forecast.forecast_year}: {forecast.forecasted_amount_kg}kg (Batch {forecast.batch.batch_id})")
            
            # Test forecast generation as would happen in the view
            forecast_dates = []
            forecast_values_list = []
            
            for result in latest_forecasts:
                from datetime import datetime
                forecast_date = datetime(result.forecast_year, result.forecast_month.number, 1)
                forecast_dates.append(forecast_date)
                forecast_values_list.append(float(result.forecasted_amount_kg))
            
            # Test future forecast data creation
            future_forecast_data = []
            for result in latest_forecasts:
                forecast_date = datetime(result.forecast_year, result.forecast_month.number, 1)
                if forecast_date >= datetime(2025, 1, 1):
                    future_forecast_data.append([
                        forecast_date.strftime('%b %Y'),
                        round(float(result.forecasted_amount_kg), 2),
                        result.forecast_month.number,
                        result.forecast_year
                    ])
            
            print(f"✅ Generated {len(future_forecast_data)} forecast data points for charts/tables")
            if future_forecast_data:
                print("Sample future forecasts:")
                for data_point in future_forecast_data[:3]:
                    print(f"  {data_point[0]}: {data_point[1]} kg")
        else:
            print("❌ No forecast data found!")
        
        print("\n" + "="*60 + "\n")
        
        # Test a combination that might not be in recent selective batches
        print("=== Testing: Mango - Abucay (should use older batch data) ===")
        mango = CommodityType.objects.get(name="Mango")
        abucay = MunicipalityName.objects.get(municipality="Abucay")
        
        base_qs_mango = ForecastResult.objects.filter(
            commodity_id=mango.commodity_id,
            municipality_id=abucay.municipality_id
        )
        latest_forecasts_mango = get_latest_forecasts_by_combination(base_qs_mango).order_by('forecast_year', 'forecast_month__number')
        
        print(f"✅ Found {latest_forecasts_mango.count()} forecast results for {mango.name} - {abucay.municipality}")
        
        if latest_forecasts_mango.count() > 0:
            print("Sample forecast results:")
            for forecast in latest_forecasts_mango[:3]:
                print(f"  {forecast.forecast_month.name} {forecast.forecast_year}: {forecast.forecasted_amount_kg}kg (Batch {forecast.batch.batch_id})")
        else:
            print("❌ No forecast data found!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("=== Testing Summary ===")
    print("The fix should ensure that:")
    print("1. ✅ Forecast data is retrieved regardless of historical data availability")
    print("2. ✅ Latest forecast per combination is used (not just latest batch)")
    print("3. ✅ Charts and tables display available forecast data")
    print("4. ✅ No 'No Forecast Data Available' message when forecasts exist")
    
    # Test overall forecasts (municipality_id=14)
    print("\n=== Testing Overall Forecasts (municipality_id=14) ===")
    overall_municipality = MunicipalityName.objects.get(municipality_id=14)
    base_qs_overall = ForecastResult.objects.filter(
        commodity_id=papaya.commodity_id,
        municipality_id=14
    )
    latest_forecasts_overall = get_latest_forecasts_by_combination(base_qs_overall)
    print(f"✅ Found {latest_forecasts_overall.count()} overall forecast results for {papaya.name}")
    
    if latest_forecasts_overall.count() > 0:
        print("Sample overall forecasts:")
        for forecast in latest_forecasts_overall[:3]:
            print(f"  {forecast.forecast_month.name} {forecast.forecast_year}: {forecast.forecasted_amount_kg}kg (Batch {forecast.batch.batch_id})")

if __name__ == "__main__":
    main()