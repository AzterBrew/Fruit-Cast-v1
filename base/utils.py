import google.generativeai as genai
from datetime import date, timedelta
from django.utils import timezone
from .models import CommodityType, ForecastResult, ForecastBatch
import json, calendar, os, joblib
from django.db import models

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

import google.generativeai as genai
from datetime import timedelta
from django.utils import timezone
from .models import CommodityType, ForecastResult, ForecastBatch
import json, calendar, os, joblib
from django.db import models

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_alternative_recommendations():
    """
    Generates alternative fruit recommendations based on future low-supply trends.
    Combines multiple prompts into a single API call for efficiency.
    """
    low_supply_threshold = 100000  # in kg
    today = timezone.now()
    all_commodities = CommodityType.objects.exclude(pk=1)
    
    # List to store commodities with low supply
    low_supply_commodities = []

    try:
        latest_batch = ForecastBatch.objects.latest('generated_at')
    except ForecastBatch.DoesNotExist:
        return {'short_term': [], 'long_term': []}

    # Step 1: Collect all low-supply commodities first
    for commodity in all_commodities:
        years_to_mature = commodity.years_to_mature if commodity.years_to_mature is not None else 1
        future_date = today + timedelta(days=float(years_to_mature) * 365.25)
        
        predicted_month_num = future_date.month
        predicted_year = future_date.year
        
        total_forecasted_kg = ForecastResult.objects.filter(
            batch=latest_batch,
            commodity=commodity,
            forecast_month__number=predicted_month_num,
            forecast_year=predicted_year
        ).aggregate(total=models.Sum('forecasted_amount_kg'))['total']
        
        total_forecasted_kg = total_forecasted_kg if total_forecasted_kg is not None else 0

        # If the forecasted amount is low, add it to our list
        if total_forecasted_kg < low_supply_threshold:
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