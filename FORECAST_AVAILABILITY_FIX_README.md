# Forecast Data Availability Fix

## Problem Solved

Previously, when selective retraining was performed on specific commodity-municipality combinations, the forecast views would only show data from the latest batch. This meant that:

1. **Data Loss**: If selective retraining created a new batch with only 5 commodity-municipality combinations, the other combinations from older batches would become unavailable
2. **Inconsistent Availability**: Users would see forecasts disappear after selective retraining
3. **Broken User Experience**: The system appeared to lose existing forecast data

## Solution Implemented

### 1. Created Utility Function (`dashboard/utils.py`)

Added `get_latest_forecasts_by_combination()` function that:
- Gets the latest forecast for each unique commodity-municipality-month-year combination
- Works regardless of which batch the forecast came from
- Ensures that selective retraining doesn't hide older forecasts

### 2. Updated All Forecast Queries (`dashboard/views.py`)

**Modified Functions:**
- `forecast()` - Main forecast view with charts and data
- `forecast_bycommodity()` - Commodity summary view  
- `forecast_csv()` - CSV export functionality
- `forecast_pdf()` - PDF export functionality
- Choropleth map data queries

**Changes Made:**
- Replaced `latest_batch` filtering with the new utility function
- Each forecast query now gets the latest forecast per combination instead of filtering by single batch
- Maintains data integrity while supporting selective retraining optimization

## Technical Details

### Before (Problematic Code):
```python
# This caused data loss - only showed forecasts from latest batch
latest_batch = forecast_qs.order_by('-batch__generated_at').values_list('batch', flat=True).first()
if latest_batch:
    forecast_qs = forecast_qs.filter(batch=latest_batch)
```

### After (Fixed Code):
```python
# This shows latest forecast for each combination regardless of batch
forecast_qs = get_latest_forecasts_by_combination(forecast_qs)
```

### How the Utility Function Works:
```python
def get_latest_forecasts_by_combination(base_queryset):
    # For each unique commodity-municipality-month-year combination,
    # find the batch with the latest generation date
    latest_batch_for_combination = ForecastResult.objects.filter(
        commodity=OuterRef('commodity'),
        municipality=OuterRef('municipality'),
        forecast_month=OuterRef('forecast_month'),
        forecast_year=OuterRef('forecast_year')
    ).order_by('-batch__generated_at').values('batch__generated_at')[:1]
    
    # Return only forecasts with the latest batch date for each combination
    return base_queryset.filter(
        batch__generated_at=Subquery(latest_batch_for_combination)
    )
```

## Testing Instructions

### 1. Before Testing
Make sure you have some forecast data from multiple batches:
- Full retraining batch (all commodity-municipality combinations)
- Selective retraining batch (partial combinations)

### 2. Test Scenarios

**Scenario A: Full Forecast View**
1. Go to the main forecast page
2. Select any commodity and municipality
3. Verify that forecast data is available even for combinations not in the latest batch

**Scenario B: Commodity Summary View**  
1. Go to forecast by commodity page
2. Select a month/year that has both old and new batch data
3. Verify all commodities show forecast values, not just recently retrained ones

**Scenario C: Map Visualization**
1. Check the choropleth map
2. Verify all municipalities show forecast data
3. Switch between different commodities and months

**Scenario D: Export Functions**
1. Export forecast data as CSV
2. Export forecast data as PDF
3. Verify all commodities appear in exports, not just recently retrained ones

### 3. Expected Results
- **Data Continuity**: All forecast combinations remain available
- **Latest Data**: When multiple forecasts exist for the same combination, the latest one is shown
- **Selective Training Compatibility**: New selective retraining results appear immediately
- **Performance**: No significant performance impact on query execution

## Benefits

1. **Maintains Data Integrity**: No forecast data is lost after selective retraining
2. **Supports Optimization**: Selective retraining still works and shows updated forecasts
3. **Consistent User Experience**: Users always see comprehensive forecast data
4. **Backwards Compatible**: Works with existing batch system without breaking changes

## Files Modified

1. `dashboard/utils.py` - Added utility function
2. `dashboard/views.py` - Updated all forecast queries to use utility function

## Database Impact

- **No schema changes required**
- **No data migration needed** 
- **Improved query efficiency** for multi-batch scenarios
- **Maintains existing batch tracking** for audit purposes