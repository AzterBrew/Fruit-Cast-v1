from django.core.management.base import BaseCommand
from dashboard.models import VerifiedHarvestRecord, VerifiedPlantRecord
import random
from datetime import datetime, timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = "Generates and inserts additional random harvest and plant records into the database"

    def handle(self, *args, **kwargs):
        commodity_types = ["Pineapple", "Lanzones", "Rambutan", "Guava", "Durian", "Mangosteen", "Calamansi", "Watermelon","Avocado", "Pomelo"]
        
        # Seasonal data for common Philippine fruits
        fruit_seasons = {
            # "Mango": ("March", "June"),
            # "Banana": ("All Year", "All Year"),
            # "Papaya": ("All Year", "All Year"),
            "Pineapple": ("March", "June"),
            "Lanzones": ("September", "November"),
            "Rambutan": ("August", "October"),
            "Guava": ("August", "October"),
            "Durian": ("August", "October"),
            "Mangosteen": ("July", "September"),
            "Calamansi": ("August", "October"),
            "Watermelon": ("March", "July"),
            "Avocado": ("July", "September"),
            "Pomelo": ("August", "October"),
        }
        
        MUNICIPALITY_BARANGAY_MAP = {
            "Abucay": ["Bangkal", "Calaylayan", "Capitangan", "Gabon", "Laon", "Mabatang", "Omboy", "Salian", "Wawa"],
            "Bagac": ["Atilano L. Ricardo", "Bagumbayan", "Banawang", "Binuangan", "Binukawan", "Ibaba", "Ibis", "Pag-asa", "Parang", "Paysawan", "Quinawan", "San Antonio", "Saysain", "Tabing-Ilog"],
            "Balanga": ["Bagong Silang", "Bagumbayan", "Cabog-Cabog", "Camacho", "Cataning", "Central", "Cupang North", "Cupang Proper", "Cupang West", "Dangcol", "Doña Francisca", "Ibayo", "Lote", "Malabia", "Munting Batangas", "Poblacion", "Pto. Rivas Ibaba", "Pto. Rivas Itaas", "San Jose", "Sibacan", "Talisay", "Tanato", "Tenejero", "Tortugas", "Tuyo"],
            "Dinalupihan": ["Almacen", "Bangal", "Bayan-bayanan", "Bonifacio", "Burgos", "Colo", "Daang Bago", "Dalao", "Del Pilar", "Del Rosario", "Dinalupihan Proper", "Gugo", "Happy Valley", "Hermosa", "Jose C. Payumo, Jr.", "Kataasan", "Layac", "Luacan", "Maligaya", "Naparing", "New San Jose", "Old San Jose", "Pagalanggang", "Pag-asa", "Padre Dandan", "Payangan", "Pentor", "Pinulot", "Pita", "Roosevelt", "Saguing", "San Carlos", "San Isidro", "San Jose", "San Pablo", "San Ramon", "San Vicente", "Santa Isabel", "Santa Lucia", "Santa Maria", "Santo Niño", "Sapang Balas", "Torres Bugauen", "Tubo-tubo", "Tucop", "Zulueta"],
            "Hermosa": ["A. Rivera", "Almacen", "Bacong", "Balsic", "Bamban", "Burgos Soliman", "Cataning", "Culis", "Daungan", "Mabiga", "Mabuco", "Maite", "Mambog", "Palihan", "Pandatung", "Pandilisan", "Pulo", "Sacrifice Valley", "San Pedro", "Sapa", "Sumalo", "Tipo", "Tugatog"],
            "Limay": ["Alangan", "Lamao", "Limay", "Liyang", "Luz", "Reformista", "San Francisco de Asis", "San Roque", "Santa Rosa", "Townsite", "Wawa", "Kitang II"],
            "Mariveles": ["Alas-asin", "Alion", "Balon Anito", "Baseco Country", "Batangas II", "Biaan", "Cabcaben", "Camaya", "Ipag", "Lucanin", "Malaya", "Maligaya", "Mt. View", "Poblacion", "San Carlos", "Sisiman", "Townsite", "Wawa"],
            "Morong": ["Binaritan", "Mabayo", "Nagbalayong", "Poblacion", "Sabang"],
            "Orani": ["Apollo", "Bayan", "Calero", "Daan Pare", "General Lim", "Mabayo", "Mulawin", "Pag-asa", "Palihan", "Pantalan Bago", "Pantalan Luma", "Parang", "Poblacion", "Salian", "San Juan", "San Ramon", "Santa Cruz", "Santa Lucia", "Santo Niño", "Sibul", "Silahis", "Sumalo", "Tala", "Tapulao", "Tenejero", "Tugatog", "Wawa", "West Daang Bago", "West Tapulao"],
            "Orion": ["Arellano", "Bagumbayan", "Balagtas", "Bantan Munti", "Bantan Grande", "Bilolo", "Calungusan", "Capunitan", "Daan Bilolo", "Daang Pare", "Lati", "Lusungan", "Puting Buhangin", "Sabatan", "San Carlos", "San Vicente", "Santa Elena", "Santo Domingo", "Santo Niño", "Tagumpay", "Tikiw", "Wakas North", "Wakas South"],
            "Pilar": ["Alauli", "Balut", "Bantan Munti", "Bantan Grande", "Burgos", "Del Rosario", "Diwa", "Liyang", "Nagwaling", "Panilao", "Pantingan", "Poblacion", "Rizal", "Santa Rosa", "Sapa", "Sibacan", "Wakas", "Wawa", "Villa"],
            "Samal": ["East Calaguiman", "Gugo", "Imelda", "Lalawigan", "Palili", "San Juan", "San Roque", "Santa Lucia", "Santa Rosa", "Sapa", "Sibacan", "West Calaguiman", "West Daang Bago", "West Tapulao"]
        }

        # Helper to convert month names to datetime ranges
        def get_season_dates(start_month, end_month, year_range=(2024, 2025)):
            dates = []
            for year in range(year_range[0], year_range[1] + 1):
                if start_month == "All Year" or end_month == "All Year":
                    start_date = datetime(year, 1, 1)
                    end_date = datetime(year, 12, 31)
                else:
                    start = datetime.strptime(f"{start_month} {year}", "%B %Y")
                    end = datetime.strptime(f"{end_month} {year}", "%B %Y")
                    # Ensure end is after start, or roll over to next year
                    if end < start:
                        end = datetime.strptime(f"{end_month} {year + 1}", "%B %Y")
                    end += timedelta(days=30)  # Approximate end-of-month
                    start_date = start
                    end_date = end
                dates.append((start_date, end_date))
            return dates

        # Generate 5 sample harvest dates per fruit type, within its seasonal range
        sample_harvests = {}
        for fruit, (start, end) in fruit_seasons.items():
            date_ranges = get_season_dates(start, end)
            dates = []
            for start_date, end_date in date_ranges:
                for _ in range(3):  # 3 random dates per year
                    rand_day = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
                    dates.append(rand_day.date())
            sample_harvests[fruit] = sorted(dates)
                        
        def generate_municipality_and_barangay():
            # Pick a random municipality
            municipality = random.choice(list(MUNICIPALITY_BARANGAY_MAP.keys()))
            # Pick a barangay from that municipality
            barangay = random.choice(MUNICIPALITY_BARANGAY_MAP[municipality])
            return municipality, barangay

        # HARVEST
        for _ in range(100):
            municipality, barangay = generate_municipality_and_barangay()
            commodity = random.choice(commodity_types)
            harvest_date = random.choice(sample_harvests[commodity])
            VerifiedHarvestRecord.objects.create(
                harvest_date=harvest_date,
                commodity_type=random.choice(commodity_types),
                commodity_spec=f"Spec {random.randint(1,3)}",
                total_weight_kg=round(random.uniform(100, 1000), 2),
                weight_per_unit_kg=round(random.uniform(0.1, 3.0), 2),
                harvest_municipality=municipality,
                harvest_barangay=barangay,
                remarks="",
                date_verified=timezone.now(),
                verified_by=None,
                prev_record=None
            )

        self.stdout.write(self.style.SUCCESS("✅ 100 additional harvest records added."))

        # PLANT
        for _ in range(100):
            municipality, barangay = generate_municipality_and_barangay()
            commodity = random.choice(commodity_types)
            plant_date = random.choice(sample_harvests[commodity])
            min_harvest = random.randint(100, 500)
            max_harvest = min_harvest + random.randint(0, 200)
            avg_units = round((min_harvest + max_harvest) / 2, 2)
            avg_weight_per_unit = round(random.uniform(0.1, 3.0), 2)
            est_weight = round(avg_units * avg_weight_per_unit, 2)
            VerifiedPlantRecord.objects.create(
                plant_date=plant_date,
                commodity_type=random.choice(commodity_types),
                commodity_spec=f"Spec {random.randint(1,3)}",
                expected_harvest_date=plant_date + timedelta(days=random.randint(60, 150)),
                estimated_weight_kg=est_weight,
                plant_municipality=municipality,
                plant_barangay = barangay,
                min_expected_harvest=min_harvest,
                max_expected_harvest=max_harvest,
                average_harvest_units=avg_units,
                land_area=round(random.uniform(100, 1000), 2),
                remarks="",
                date_verified=timezone.now(),
                verified_by=None,
                prev_record=None
            )

        self.stdout.write(self.style.SUCCESS("✅ 100 additional plant records added."))
    #     commodity_types = ["Mango", "Banana", "Papaya", "Pineapple", "Lanzones", "Rambutan", "Guava", "Durian", "Mangosteen", "Calamansi"]
    #     locations = ["Balanga", "Orani", "Dinalupihan", "Abucay", "Hermosa", "Samal", "Pilar", "Bagac", "Morong", "Mariveles"]
    #     start_date = datetime(2024, 1, 1)
    #     end_date = datetime(2025, 12, 31)

    #     def random_date(start, end):
    #         return start + timedelta(days=random.randint(0, (end - start).days))

    #     # ✅ Generate 100 VerifiedHarvestRecord objects
    #     for _ in range(100):
    #         harvest_date = random_date(start_date, end_date).date()
    #         VerifiedHarvestRecord.objects.create(
    #             harvest_date=harvest_date,
    #             commodity_type=random.choice(commodity_types),
    #             commodity_spec=f"Spec {random.randint(1,3)}",
    #             total_weight_kg=round(random.uniform(100, 1000), 2),
    #             weight_per_unit_kg=round(random.uniform(0.1, 3.0), 2),
    #             harvest_location=random.choice(locations),
    #             remarks="",
    #             date_verified=timezone.now(),
    #             verified_by=None,
    #             prev_record=None
    #         )

    #     self.stdout.write(self.style.SUCCESS("✅ 100 additional harvest records added."))

    #     # ✅ Generate 100 VerifiedPlantRecord objects
    #     for _ in range(100):
    #         plant_date = random_date(start_date, end_date).date()
    #         min_harvest = random.randint(100, 500)
    #         max_harvest = min_harvest + random.randint(0, 200)
    #         avg_units = round((min_harvest + max_harvest) / 2, 2)
    #         avg_weight_per_unit = round(random.uniform(0.1, 3.0), 2)
    #         est_weight = round(avg_units * avg_weight_per_unit, 2)
    #         VerifiedPlantRecord.objects.create(
    #             plant_date=plant_date,
    #             commodity_type=random.choice(commodity_types),
    #             commodity_spec=f"Spec {random.randint(1,3)}",
    #             expected_harvest_date=plant_date + timedelta(days=random.randint(60, 150)),
    #             estimated_weight_kg=est_weight,
    #             plant_municipality=random.choice(locations),
    #             min_expected_harvest=min_harvest,
    #             max_expected_harvest=max_harvest,
    #             average_harvest_units=avg_units,
    #             land_area=round(random.uniform(100, 1000), 2),
    #             remarks="",
    #             date_verified=timezone.now(),
    #             verified_by=None,
    #             prev_record=None
    #         )

        