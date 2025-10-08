# Replace 'your_app' and 'YourModel' with your actual app and model names
from base.models import AccountStatus 

# Example A: View ALL records
all_records = AccountStatus.objects.all()
for record in all_records:
    print(record.acc_stat_id, record.acc_status)

# Example B: Filter records (e.g., to view the recommendation data)
# Assuming you have a Model named 'Recommendation'
# from base.models import Recommendation 
# recommendations = Recommendation.objects.filter(municipality_id=14).order_by('-generated_at')
# for rec in recommendations:
#     print(f"ID: {rec.id} | Date: {rec.generated_at} | Data: {rec.json_data[:50]}...")

# To exit the shell:
exit()