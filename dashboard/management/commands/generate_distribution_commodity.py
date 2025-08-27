import pandas as pd
import numpy as np

# Commodity totals
commodity_totals = {
    "Banana": 48000,
    "Mango": 540000,
    "Rambutan": 90000,
    "Pineapple": 90000,
    "Papaya": 18000,
    "Coffee": 90000,
    "Calamansi": 3500,
    "Avocado": 90000,
}

# Seasonal months mapping (1=Jan, ..., 12=Dec)
seasonal_months = {
    "Banana":      [1,2,3,4,5,6,7,8,9,10,11,12],
    "Mango":       [4,5,6],
    "Rambutan":    [8,9,10],
    "Pineapple":   [5,6,7],
    "Papaya":      [1,2,3,4,5,6,7,8,9,10,11,12],
    "Coffee":      [11,12,1,2],
    "Calamansi":   [7,8,9,10],
    "Avocado":     [7,8,9],
}

months = [1,2,3,4,5,6,7,8,9,10,11,12]
month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

rows = []
for commodity, total in commodity_totals.items():
    season = set(seasonal_months[commodity])
    # Assign higher weights to seasonal months
    weights = []
    for m in months:
        if m in season:
            weights.append(3)  # Seasonal months get 3x weight
        else:
            weights.append(1)
    weights = np.array(weights)
    weights = weights / weights.sum()
    # Randomly distribute, but sum to total
    values = np.random.multinomial(total, weights)
    for m, v in zip(months, values):
        rows.append({
            "Commodity": commodity,
            "Month": month_names[m-1],
            "MonthNum": m,
            "Value": v
        })

df = pd.DataFrame(rows)
df_pivot = df.pivot(index="Commodity", columns="Month", values="Value").fillna(0).astype(int)
df_pivot.to_csv("commodity_monthly_distribution.csv")
print(df_pivot)