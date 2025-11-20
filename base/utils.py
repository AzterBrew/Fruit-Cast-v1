
import google.generativeai as genai
from datetime import timedelta, datetime
from django.utils import timezone
from .models import CommodityType, ForecastResult, ForecastBatch, Month, MunicipalityName
import json, calendar, os, joblib
from django.db import models
try:
    import numpy as np
    import pandas as pd
    from prophet import Prophet
except ImportError:
    # Handle missing dependencies gracefully
    np = None
    pd = None
    Prophet = None
from django.conf import settings
from django.core.files.storage import default_storage
from io import BytesIO

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_alternative_recommendations(selected_month=None, selected_year=None, selected_municipality_id=None):
    """
    Generates alternative fruit recommendations based on future low-supply trends.
    Combines multiple prompts into a single API call for efficiency.
    """
    print(f"🔍 Starting recommendations for month={selected_month}, year={selected_year}, municipality={selected_municipality_id}")
    
    # Check if Gemini API key is configured
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        return {'short_term': [], 'long_term': []}
    else:
        print(f"🔑 API key configured (length: {len(api_key)} chars)")
    
    # low_supply_threshold = 100000  # in kg
    if selected_month and selected_year:
        base_date = datetime(int(selected_year), int(selected_month), 1)
    else:
        base_date = timezone.now()

    print(f"📅 Using base date: {base_date}")

    all_commodities = CommodityType.objects.exclude(pk=1)
    print(f"🌾 Found {all_commodities.count()} commodities to analyze")
    
    low_supply_commodities = []

    try:
        latest_batch = ForecastBatch.objects.latest('generated_at')
        print(f"📊 Using forecast batch: {latest_batch.batch_id} (generated at {latest_batch.generated_at})")
    except ForecastBatch.DoesNotExist:
        print("❌ No forecast batch found in database")
        return {'short_term': [], 'long_term': []}

    if selected_municipality_id is None:
        selected_municipality_id = 14

    print(f"🏙️ Using municipality ID: {selected_municipality_id}")

    # --- DYNAMIC THRESHOLD CALCULATION FOR A SPECIFIC MUNICIPALITY ---
    
    # 1. Get all forecasted amounts for all commodities for the given municipality
    amounts_per_commodity = ForecastResult.objects.filter(
        batch=latest_batch,
        forecast_year__gte=base_date.year,
        municipality=selected_municipality_id
    ).values('commodity').annotate(total_kg=models.Sum('forecasted_amount_kg'))
    
    print(f"📈 Found {amounts_per_commodity.count()} commodity forecasts for municipality {selected_municipality_id}")
    
    forecasted_values = [item['total_kg'] for item in amounts_per_commodity]

    if not forecasted_values:
        print("❌ No forecasted values found for the selected municipality.")
        return {'short_term': [], 'long_term': []}
    
    # Handle cases with insufficient data for a quartile calculation
    if len(forecasted_values) < 4:
        low_supply_threshold = np.median(forecasted_values) if forecasted_values else 0
        print(f"⚠️ Using median threshold due to insufficient data points: {low_supply_threshold}")
    else:
        low_supply_threshold = np.quantile(forecasted_values, 0.25)
    
    print(f"📊 Calculated Low Supply Threshold (Q1) for Municipality {selected_municipality_id}: {low_supply_threshold}")
    print(f"📋 Forecasted values range: min={min(forecasted_values)}, max={max(forecasted_values)}, count={len(forecasted_values)}")
     
    # --- END OF DYNAMIC THRESHOLD LOGIC ---
    
    # Step 2: Collect commodities with a forecasted supply below the threshold
    commodities_checked = 0
    for commodity in all_commodities:
        commodities_checked += 1
        years_to_mature = commodity.years_to_mature if commodity.years_to_mature is not None else 1
        future_date = base_date + timedelta(days=float(years_to_mature) * 365.25)
        
        predicted_month_num = future_date.month
        predicted_year = future_date.year

        # Check if the needed forecast date is within the stored database horizon (12 months)
        months_difference = (predicted_year - base_date.year) * 12 + (predicted_month_num - base_date.month)
        db_forecast_horizon = 12
        
        if months_difference <= db_forecast_horizon and months_difference >= 0:
            total_forecasted_kg = ForecastResult.objects.filter(
                batch=latest_batch,
                commodity=commodity,
                forecast_month__number=predicted_month_num,
                forecast_year=predicted_year,
                municipality=selected_municipality_id
            ).aggregate(total=models.Sum('forecasted_amount_kg'))['total']
            
            total_forecasted_kg = total_forecasted_kg if total_forecasted_kg is not None else 0
            print(f"🔍 {commodity.name}: DB forecast = {total_forecasted_kg} kg (threshold: {low_supply_threshold})")
            
        else:
            try:
                # Load the appropriate Prophet model for the specific municipality

                model_filename = f"prophet_{commodity.commodity_id}_{selected_municipality_id}.joblib"
                bucket_path = f"prophet_models/{model_filename}"

                # Check if the model file exists in the Spaces bucket
                if not default_storage.exists(bucket_path):
                    forecast_data = None
                    print(f"⚠️ No trained model found for {commodity.name}")
                else:
                    # Open the file from the bucket and load it with joblib
                    with default_storage.open(bucket_path, 'rb') as f:
                        m = joblib.load(f)

                    # Create a future dataframe for the specific date
                    future_df = pd.DataFrame({'ds': [future_date]})
                    
                    # Predict the amount
                    forecasted_amount_series = m.predict(future_df)['yhat']
                    
                    # Extract the single value
                    total_forecasted_kg = forecasted_amount_series.iloc[0] if not forecasted_amount_series.empty else 0
                    print(f"🔮 {commodity.name}: Prophet forecast = {total_forecasted_kg} kg")
                
            except Exception as e:
                print(f"❌ Error generating on-demand forecast for {commodity.name} in Municipality {selected_municipality_id}: {e}")
                continue
            
        # If the forecasted amount is low, add it to our list
        if total_forecasted_kg is not None and total_forecasted_kg < low_supply_threshold:
            low_supply_commodities.append({
                'name': commodity.name,
                'years_to_mature': years_to_mature,
                'predicted_month': calendar.month_name[predicted_month_num],
                'predicted_year': predicted_year,
                'forecasted_amount': total_forecasted_kg 
            })
            print(f"✅ {commodity.name} added to low-supply list (forecast: {total_forecasted_kg} < threshold: {low_supply_threshold})")

    print(f"📊 Checked {commodities_checked} commodities, found {len(low_supply_commodities)} with low supply")

    if not low_supply_commodities:
        print("💭 No low-supply commodities found, returning empty recommendations")
        return {'short_term': [], 'long_term': []}

    # Limit to maximum 8 commodities to avoid overwhelming the API
    if len(low_supply_commodities) > 8:
        print(f"⚠️ Too many commodities ({len(low_supply_commodities)}), limiting to top 8 by lowest forecast")
        # Sort by forecasted amount (lowest first) and take top 8
        low_supply_commodities = sorted(low_supply_commodities, key=lambda x: x.get('forecasted_amount', 0))[:8]
        print(f"🎯 Reduced to {len(low_supply_commodities)} commodities for API call")

    # Step 2: Construct a single, comprehensive prompt
    prompt_list = []
    for item in low_supply_commodities:
        prompt_list.append(
            f"Commodity: {item['name']}, "
            f"Projected low supply in: {item['predicted_month']} {item['predicted_year']}. "
            "Please provide a concise recommendation for planting this fruit on Clay Soil, Sandy Loam, Loam Soil, Volcanic Soil, and Peat Soil."
        )

    full_prompt = (
        """You are an expert agricultural consultant in the Philippines.
        
        Based on a forecast, there are several fruits with low predicted supply in the future. This suggests a good opportunity for farmers to meet future demand.

        For each of the following low-supply commodities, provide a concise planting recommendation. The recommendations should include suitability and tips for each of the specified land types.

        Commodities and details:
        """ + "\n".join(prompt_list) + """

        Format your entire response as a single JSON object. The keys should be the commodity names, and the values should be JSON objects containing the `reason` for the recommendation and the `land_recommendations` for each land type.
        
        Example format:
        {
          "Commodity A": {
            "reason": "This fruit is projected to have low supply due to...",
            "land_recommendations": {
              "Clay Soil": "...",
              "Sandy Loam": "...",
              "Loam Soil": "...",
              "Volcanic Soil": "...",
              "Peat Soil": "..."
            }
          },
          "Commodity B": {
            "reason": "...",
            "land_recommendations": {
              ...
            }
          }
        }
        """
    )
    
    # Step 3: Make a single API call with timeout handling
    print(f"🚀 Starting Gemini API call for {len(low_supply_commodities)} commodities")
    print(f"📝 Prompt length: {len(full_prompt)} characters")
    
    # Test basic network connectivity
    try:
        import urllib.request
        print("🌐 Testing network connectivity...")
        urllib.request.urlopen('https://google.com', timeout=5)
        print("✅ Network connectivity confirmed")
    except Exception as network_error:
        print(f"❌ Network connectivity issue: {network_error}")
        print("💡 This might explain the API timeouts")
    
    try:
        import signal
        import concurrent.futures
        
        def api_call_with_timeout():
            try:
                print("🔧 Initializing Gemini model...")
                model = genai.GenerativeModel('gemini-2.0-flash')
                print("📡 Making API request...")
                response = model.generate_content(full_prompt)
                print("✅ Received response from Gemini API")
                return response
            except Exception as api_error:
                print(f"❌ API call failed with error: {type(api_error).__name__}: {api_error}")
                raise api_error
        
        # Use ThreadPoolExecutor with timeout to prevent hanging
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(api_call_with_timeout)
            try:
                # Increase timeout to 30 seconds for better reliability
                print("⏱️ Waiting for API response (30s timeout)...")
                response = future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                print("⏰ Gemini API call timed out after 30 seconds")
                print("💡 Try reducing the number of commodities or checking API performance")
                return {'short_term': [], 'long_term': []}
            except Exception as future_error:
                print(f"💥 Future execution failed: {type(future_error).__name__}: {future_error}")
                return {'short_term': [], 'long_term': []}
        
        if not response:
            print("❌ Received None response from Gemini API")
            return {'short_term': [], 'long_term': []}
            
        if not hasattr(response, 'text') or not response.text:
            print("❌ Empty or invalid response text from Gemini API")
            print(f"📊 Response object: {type(response)}")
            if hasattr(response, '__dict__'):
                print(f"📋 Response attributes: {list(response.__dict__.keys())}")
            return {'short_term': [], 'long_term': []}
        
        print(f"📄 Received response text length: {len(response.text)} characters")
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        print(f"🧹 Cleaned response text length: {len(raw_text)} characters")
        
        try:
            full_recommendations = json.loads(raw_text)
            print(f"✅ Successfully parsed JSON with {len(full_recommendations)} items")
        except json.JSONDecodeError as json_error:
            print(f"❌ Failed to parse JSON response from Gemini: {json_error}")
            print(f"📄 Raw response (first 500 chars): {raw_text[:500]}...")
            print(f"📄 Raw response (last 200 chars): ...{raw_text[-200:]}")
            return {'short_term': [], 'long_term': []}
        
        final_recommendations = {
            'short_term': [],
            'long_term': []
        }
        
        # Parse the single JSON response and categorize recommendations
        for commodity in low_supply_commodities:
            commodity_name = commodity['name']
            if commodity_name in full_recommendations:
                rec_data = full_recommendations[commodity_name]
                is_long_term = commodity['years_to_mature'] >= 1
                
                new_rec = {
                    'commodity_name': commodity_name,
                    'reason': rec_data.get('reason', 'Reason not provided.'),
                    'estimated_maturity': f"{commodity['years_to_mature']} years" if is_long_term else f"{int(commodity['years_to_mature'] * 12)} months",
                    'land_recommendations': rec_data.get('land_recommendations', {}),
                    'forecasted_amount': commodity.get('forecasted_amount', 0),  # Include for sorting
                    'predicted_month': commodity.get('predicted_month', 'Unknown'),
                    'predicted_year': commodity.get('predicted_year', 'Unknown')
                }
                
                if is_long_term:
                    final_recommendations['long_term'].append(new_rec)
                else:
                    final_recommendations['short_term'].append(new_rec)
                    
        return final_recommendations

    except ImportError:
        print("❌ concurrent.futures not available, falling back to basic call")
        # Fallback for environments without concurrent.futures
        try:
            print("🔧 Fallback: Initializing Gemini model...")
            model = genai.GenerativeModel('gemini-2.0-flash')
            print("📡 Fallback: Making direct API request...")
            response = model.generate_content(full_prompt)
            print("✅ Fallback: Received response from Gemini API")
            
            if not response:
                print("❌ Fallback: Received None response")
                return {'short_term': [], 'long_term': []}
                
            if not hasattr(response, 'text') or not response.text:
                print("❌ Fallback: Empty or invalid response text")
                return {'short_term': [], 'long_term': []}
            
            print(f"📄 Fallback: Response text length: {len(response.text)} characters")
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            full_recommendations = json.loads(raw_text)
            print(f"✅ Fallback: Successfully parsed JSON with {len(full_recommendations)} items")
            
            final_recommendations = {'short_term': [], 'long_term': []}
            
            for commodity in low_supply_commodities:
                commodity_name = commodity['name']
                if commodity_name in full_recommendations:
                    rec_data = full_recommendations[commodity_name]
                    is_long_term = commodity['years_to_mature'] >= 1
                    
                    new_rec = {
                        'commodity_name': commodity_name,
                        'reason': rec_data.get('reason', 'Reason not provided.'),
                        'estimated_maturity': f"{commodity['years_to_mature']} years" if is_long_term else f"{int(commodity['years_to_mature'] * 12)} months",
                        'land_recommendations': rec_data.get('land_recommendations', {}),
                        'forecasted_amount': commodity.get('forecasted_amount', 0), 
                        'predicted_month': commodity.get('predicted_month', 'Unknown'),
                        'predicted_year': commodity.get('predicted_year', 'Unknown')
                    }
                    
                    if is_long_term:
                        final_recommendations['long_term'].append(new_rec)
                    else:
                        final_recommendations['short_term'].append(new_rec)
                        
            return final_recommendations
            
        except Exception as fallback_error:
            print(f"💥 Fallback API call also failed: {type(fallback_error).__name__}: {fallback_error}")
            print(f"📋 Fallback error details: {str(fallback_error)}")
            import traceback
            print(f"📚 Fallback traceback: {traceback.format_exc()}")
            return {'short_term': [], 'long_term': []}
            
    except Exception as e:
        print(f"💥 Unexpected error getting Gemini recommendations: {type(e).__name__}: {e}")
        print(f"📋 Error details: {str(e)}")
        import traceback
        print(f"📚 Full traceback: {traceback.format_exc()}")
        return {'short_term': [], 'long_term': []}
