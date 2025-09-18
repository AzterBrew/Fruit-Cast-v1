
import google.generativeai as genai
from datetime import timedelta, datetime
from django.utils import timezone
from .models import CommodityType, ForecastResult, ForecastBatch, Month, MunicipalityName
import json, calendar, os, joblib
from django.db import models
import numpy as np
import pandas as pd
from prophet import Prophet
from django.conf import settings
from django.core.files.storage import default_storage
from io import BytesIO

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_alternative_recommendations(selected_month=None, selected_year=None, selected_municipality_id=None):
    """
    Generates alternative fruit recommendations based on future low-supply trends.
    Combines multiple prompts into a single API call for efficiency.
    """
    # low_supply_threshold = 100000  # in kg
    if selected_month and selected_year:
        base_date = datetime(int(selected_year), int(selected_month), 1)
    else:
        base_date = timezone.now()

    all_commodities = CommodityType.objects.exclude(pk=1)
    low_supply_commodities = []

    try:
        latest_batch = ForecastBatch.objects.latest('generated_at')
    except ForecastBatch.DoesNotExist:
        return {'short_term': [], 'long_term': []}

     # If no municipality is selected, default to the 'Overall' ID (14)
    if selected_municipality_id is None:
        selected_municipality_id = 14

    # --- DYNAMIC THRESHOLD CALCULATION FOR A SPECIFIC MUNICIPALITY ---
    
    # 1. Get all forecasted amounts for all commodities for the given municipality
    amounts_per_commodity = ForecastResult.objects.filter(
        batch=latest_batch,
        forecast_year__gte=base_date.year,
        municipality=selected_municipality_id
    ).values('commodity').annotate(total_kg=models.Sum('forecasted_amount_kg'))
    
    forecasted_values = [item['total_kg'] for item in amounts_per_commodity]

    if not forecasted_values:
        print("No forecasted values found for the selected municipality.")
        return {'short_term': [], 'long_term': []}
    
    # Handle cases with insufficient data for a quartile calculation
    if len(forecasted_values) < 4:
        low_supply_threshold = np.median(forecasted_values) if forecasted_values else 0
    else:
        low_supply_threshold = np.quantile(forecasted_values, 0.25)
    
    print(f"Calculated Low Supply Threshold (Q1) for Municipality {selected_municipality_id}: {low_supply_threshold}")
    
    # --- END OF DYNAMIC THRESHOLD LOGIC ---
    
    # Step 2: Collect commodities with a forecasted supply below the threshold
    for commodity in all_commodities:
        years_to_mature = commodity.years_to_mature if commodity.years_to_mature is not None else 1
        future_date = base_date + timedelta(days=float(years_to_mature) * 365.25)
        
        predicted_month_num = future_date.month
        predicted_year = future_date.year

        # Check if the needed forecast date is within the stored database horizon (12 months)
        months_difference = (predicted_year - base_date.year) * 12 + (predicted_month_num - base_date.month)
        db_forecast_horizon = 12
        
        if months_difference <= db_forecast_horizon and months_difference >= 0:
            # Scenario A: Forecast is recent, get it from the database
            total_forecasted_kg = ForecastResult.objects.filter(
                batch=latest_batch,
                commodity=commodity,
                forecast_month__number=predicted_month_num,
                forecast_year=predicted_year,
                municipality=selected_municipality_id
            ).aggregate(total=models.Sum('forecasted_amount_kg'))['total']
            
            total_forecasted_kg = total_forecasted_kg if total_forecasted_kg is not None else 0
            
        else:
            # Scenario B: Forecast is too far in the future. Generate it on-demand.
            try:
                # Load the appropriate Prophet model for the specific municipality

                model_filename = f"prophet_{commodity.commodity_id}_{selected_municipality_id}.joblib"
                bucket_path = f"prophet_models/{model_filename}"

                # Check if the model file exists in the Spaces bucket
                if not default_storage.exists(bucket_path):
                    forecast_data = None
                    print("No trained model found.")
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
                
            except Exception as e:
                print(f"Error generating on-demand forecast for {commodity.name} in Municipality {selected_municipality_id}: {e}")
                continue
            
        # If the forecasted amount is low, add it to our list
        if total_forecasted_kg is not None and total_forecasted_kg < low_supply_threshold:
            low_supply_commodities.append({
                'name': commodity.name,
                'years_to_mature': years_to_mature,
                'predicted_month': calendar.month_name[predicted_month_num],
                'predicted_year': predicted_year
            })

    # If no low-supply commodities were found, return early
    if not low_supply_commodities:
        return {'short_term': [], 'long_term': []}

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
    
    # Step 3: Make a single API call
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(full_prompt)
        
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        full_recommendations = json.loads(raw_text)
        
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
                    'land_recommendations': rec_data.get('land_recommendations', {})
                }
                
                if is_long_term:
                    final_recommendations['long_term'].append(new_rec)
                else:
                    final_recommendations['short_term'].append(new_rec)
                    
        return final_recommendations

    except Exception as e:
        print(f"Error getting Gemini recommendations: {e}")
        return {'short_term': [], 'long_term': []}




# temporary simple code

# def get_alternative_recommendations():
#     """
#     Generates a single, simplified fruit recommendation for a specific commodity
#     to test API connectivity.
#     """
#     recommendations = {
#         'short_term': [],
#         'long_term': []
#     }

#     # Define a single, hardcoded commodity for testing purposes
#     commodity_name = "Mango"
#     predicted_month = 10 # October
#     predicted_year = 2026

#     # Construct the prompt for the Gemini API
#     prompt = f"""
#     You are an expert agricultural consultant in the Philippines.

#     Based on a forecast, there is a low predicted supply for {commodity_name} in {calendar.month_name[predicted_month]} {predicted_year}. This suggests a good opportunity for farmers to meet future demand.

#     Provide a concise recommendation for planting this fruit. For each of the following land types, provide a brief comment on its suitability and any tips.

#     Land Types: Clay Soil, Sandy Loam, Loam Soil, Volcanic Soil, Peat Soil.

#     Format your response as a JSON object with keys matching the land types and values containing the comments.
#     """

#     try:
#         model = genai.GenerativeModel('gemini-1.5-flash')
#         response = model.generate_content(prompt)

#         # Clean and parse the JSON response
#         raw_text = response.text.replace("```json", "").replace("```", "").strip()
#         land_type_recommendations = json.loads(raw_text)

#         # Append the simplified recommendation
#         recommendations['long_term'].append({
#             'commodity_name': commodity_name,
#             'reason': f"Projected low supply in {calendar.month_name[predicted_month]} {predicted_year}.",
#             'land_recommendations': land_type_recommendations
#         })

#     except Exception as e:
#         # It's important to return an empty dict on error, not let it crash
#         print(f"Error getting Gemini recommendation for {commodity_name}: {e}")
#         return {'short_term': [], 'long_term': []}

#     return recommendations