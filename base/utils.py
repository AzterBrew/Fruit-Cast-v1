from google import genai
from datetime import date, timedelta
from django.utils import timezone
from .models import CommodityType, ForecastResult, ForecastBatch
import json, calendar, os, joblib
from django.db import models

client = genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def get_alternative_recommendations():
    """
    Generates alternative fruit recommendations based on future low-supply trends.
    """
    # Define a low-supply threshold (in kg). Adjust this value as needed.
    low_supply_threshold = 100000 
    
    today = timezone.now()
    all_commodities = CommodityType.objects.exclude(pk=1)
    
    recommendations = {
        'short_term': [],
        'long_term': []
    }
    
    # try:
    #     latest_batch = ForecastBatch.objects.latest('generated_at')
    # except ForecastBatch.DoesNotExist:
    #     return recommendations # Return empty if no forecast data exists

    # for commodity in all_commodities:
    #     # Calculate predicted harvest month
    #     # Convert years_to_mature to days and add to today's date
    #     # Use a safe default of 1 if years_to_mature is not set
    #     years_to_mature = commodity.years_to_mature if commodity.years_to_mature is not None else 1
    #     future_date = today + timedelta(days=float(years_to_mature) * 365.25)
        
    #     predicted_month_num = future_date.month
    #     predicted_year = future_date.year
        
    #     # Check forecasted total supply for this commodity in the predicted harvest month
    #     total_forecasted_kg = ForecastResult.objects.filter(
    #         batch=latest_batch,
    #         commodity=commodity,
    #         forecast_month__number=predicted_month_num,
    #         forecast_year=predicted_year
    #     ).aggregate(total=models.Sum('forecasted_amount_kg'))['total']
        
    #     total_forecasted_kg = total_forecasted_kg if total_forecasted_kg is not None else 0

    #     # If the forecasted amount is low, get a recommendation from Gemini
    #     if total_forecasted_kg < low_supply_threshold:
    #         # Construct the prompt for the Gemini API
    #         prompt = f"""
    #         You are an expert agricultural consultant in the Philippines.
            
    #         Based on a forecast, there is a low predicted supply for {commodity.name} in {calendar.month_name[predicted_month_num]} {predicted_year}. This suggests a good opportunity for farmers to meet future demand.
            
    #         Provide a concise recommendation for planting this fruit. For each of the following land types, provide a brief comment on its suitability and any tips.
            
    #         Land Types: Clay Soil, Sandy Loam, Loam Soil, Volcanic Soil, Peat Soil.
            
    #         Format your response as a JSON object with keys matching the land types and values containing the comments.
    #         """
            
    #         try:
    #             model = genai.GenerativeModel('gemini-1.5-flash')
    #             response = model.generate_content(prompt)
                
    #             # Clean and parse the JSON response
    #             # Sometimes the API adds markdown `json` to the output.
    #             raw_text = response.text.replace("```json", "").replace("```", "").strip()
    #             land_type_recommendations = json.loads(raw_text)
                
    #             # Check if it's a short-term or long-term recommendation
    #             is_long_term = years_to_mature >= 1
                
    #             if is_long_term:
    #                 recommendations['long_term'].append({
    #                     'commodity_name': commodity.name,
    #                     'estimated_maturity': f"{years_to_mature} years",
    #                     'land_recommendations': land_type_recommendations
    #                 })
    #             else:
    #                 recommendations['short_term'].append({
    #                     'commodity_name': commodity.name,
    #                     'estimated_maturity': f"{int(years_to_mature * 12)} months",
    #                     'land_recommendations': land_type_recommendations
    #                 })

    #         except Exception as e:
    #             print(f"Error getting Gemini recommendation for {commodity.name}: {e}")
                    
    return recommendations

def samplegen():
    response = client.models.generate_content_stream(
        model="gemini-1.5-flash", 
        prompt="Whats the current state of the philippine government?"
        )
    
    print(response.text)
    
    if __name__ == "__main__":
        samplegen()