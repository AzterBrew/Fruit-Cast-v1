
# FOR DISTRIBUTING THEM TOTAL DATA
# import pandas as pd
# import numpy as np

# # Commodity totals
# commodity_totals = {
#     "Banana": 48000,
#     "Mango": 540000,
#     "Rambutan": 90000,
#     "Pineapple": 90000,
#     "Papaya": 18000,
#     "Coffee": 90000,
#     "Calamansi": 3500,
#     "Avocado": 90000,
# }

# # Seasonal months mapping (1=Jan, ..., 12=Dec)
# seasonal_months = {
#     "Banana":      [1,2,3,4,5,6,7,8,9,10,11,12],
#     "Mango":       [4,5,6],
#     "Rambutan":    [8,9,10],
#     "Pineapple":   [5,6,7],
#     "Papaya":      [1,2,3,4,5,6,7,8,9,10,11,12],
#     "Coffee":      [11,12,1,2],
#     "Calamansi":   [7,8,9,10],
#     "Avocado":     [7,8,9],
# }

# months = [1,2,3,4,5,6,7,8,9,10,11,12]
# month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

# rows = []
# for commodity, total in commodity_totals.items():
#     season = set(seasonal_months[commodity])
#     # Assign higher weights to seasonal months
#     weights = []
#     for m in months:
#         if m in season:
#             weights.append(3)  # Seasonal months get 3x weight
#         else:
#             weights.append(1)
#     weights = np.array(weights)
#     weights = weights / weights.sum()
#     # Randomly distribute, but sum to total
#     values = np.random.multinomial(total, weights)
#     for m, v in zip(months, values):
#         rows.append({
#             "Commodity": commodity,
#             "Month": month_names[m-1],
#             "MonthNum": m,
#             "Value": v
#         })

# df = pd.DataFrame(rows)
# df_pivot = df.pivot(index="Commodity", columns="Month", values="Value").fillna(0).astype(int)
# df_pivot.to_csv("commodity_monthly_distribution.csv")
# print(df_pivot)


# FOR EXPORTING AS CSV THE GENERATED DATA

import pandas as pd

# Your data as a dictionary (replace with your actual values if needed)
data = {
    'Commodity': ['Avocado', 'Banana', 'Calamansi', 'Coffee', 'Mango', 'Papaya', 'Pineapple', 'Rambutan'],
    'Jan': [5068, 3867, 169, 13599, 30072, 1478, 5084, 4952],
    'Feb': [5022, 4127, 150, 13453, 29778, 1480, 5037, 4925],
    'Mar': [5190, 3976, 194, 4550, 30183, 1478, 5004, 4897],
    'Apr': [5014, 4004, 194, 4650, 90103, 1577, 5139, 5111],
    'May': [4970, 4051, 157, 4391, 90045, 1515, 14810, 5088],
    'Jun': [5008, 4031, 173, 4564, 89856, 1541, 15051, 4994],
    'Jul': [14838, 3923, 540, 4584, 30048, 1525, 14778, 5073],
    'Aug': [15072, 3883, 517, 4418, 29746, 1462, 5088, 15060],
    'Sep': [14997, 4075, 465, 4515, 29976, 1507, 5101, 14889],
    'Oct': [4896, 3989, 564, 4419, 30225, 1513, 5023, 14887],
    'Nov': [4878, 4077, 192, 13359, 30078, 1497, 4880, 4987],
    'Dec': [5047, 3997, 185, 13498, 29890, 1427, 5005, 5137],
}

df = pd.DataFrame(data)
df = df.set_index('Commodity')
df = df.T  # Transpose to have months as rows

# Map month names to numbers
month_map = {'Jan':1, 'Feb':2, 'Mar':3, 'Apr':4, 'May':5, 'Jun':6, 'Jul':7, 'Aug':8, 'Sep':9, 'Oct':10, 'Nov':11, 'Dec':12}

rows = []
for month_name, month_num in month_map.items():
    for commodity in df.columns:
        rows.append({
            'harvest_date': f'2023-{month_num:02d}-01',
            'commodity': commodity,
            'municipality': 5,  # or set a default value
            'barangay': '',      # or set a default value
            'total_weight_kg': df.loc[month_name, commodity]
        })

result_df = pd.DataFrame(rows)
result_df.to_csv('commodity_harvest_2023.csv', index=False)
pd.set_option('display.max_rows', None)  # Show all rows
print(result_df)