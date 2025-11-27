from django.core.management.base import BaseCommand
from base.models import *
from django.db.models import Count
import json


class Command(BaseCommand):
    help = 'Check and display current database records for debugging'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Specify a specific model to check (e.g., municipality, commodity, account)',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json', 'summary'],
            default='table',
            help='Output format: table, json, or summary',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Limit number of records to display (default: 50)',
        )

    def handle(self, *args, **options):
        model_filter = options['model']
        output_format = options['format']
        limit = options['limit']
        
        self.stdout.write(self.style.SUCCESS('=== FRUITCAST DATABASE STATUS ===\n'))
        
        if model_filter:
            self.check_specific_model(model_filter, output_format, limit)
        else:
            self.check_all_models(output_format, limit)

    def check_specific_model(self, model_name, output_format, limit):
        """Check a specific model"""
        model_name = model_name.lower()
        
        if 'municipal' in model_name:
            self.display_municipalities(output_format, limit)
        elif 'barangay' in model_name:
            self.display_barangays(output_format, limit)
        elif 'commodity' in model_name:
            self.display_commodities(output_format, limit)
        elif 'account' in model_name and 'type' in model_name:
            self.display_account_types(output_format, limit)
        elif 'account' in model_name and 'status' in model_name:
            self.display_account_statuses(output_format, limit)
        elif 'user' in model_name:
            self.display_users(output_format, limit)
        elif 'month' in model_name:
            self.display_months(output_format, limit)
        elif 'unit' in model_name:
            self.display_units(output_format, limit)
        else:
            self.stdout.write(
                self.style.ERROR(f'Unknown model: {model_name}\n')
                + 'Available models: municipality, barangay, commodity, account_type, account_status, user, month, unit'
            )

    def check_all_models(self, output_format, limit):
        """Check all models with summary"""
        if output_format == 'summary':
            self.display_summary()
        else:
            self.display_municipalities(output_format, min(limit, 20))
            self.display_commodities(output_format, min(limit, 20))
            self.display_account_types(output_format, min(limit, 20))
            self.display_users(output_format, min(limit, 10))

    def display_summary(self):
        """Display a summary of all models"""
        models_info = [
            ('Municipalities', MunicipalityName.objects.count()),
            ('Barangays', BarangayName.objects.count()),
            ('Commodity Types', CommodityType.objects.count()),
            ('Account Types', AccountType.objects.count()),
            ('Account Statuses', AccountStatus.objects.count()),
            ('Users', AuthUser.objects.count()),
            ('Months', Month.objects.count()),
            ('Unit Measurements', UnitMeasurement.objects.count()),
            ('Plant Records', initPlantRecord.objects.count()),
            ('Harvest Records', initHarvestRecord.objects.count()),
            ('Transactions', RecordTransaction.objects.count()),
        ]
        
        self.stdout.write(self.style.WARNING('DATABASE SUMMARY:'))
        for model_name, count in models_info:
            status = '✓' if count > 0 else '✗'
            color = self.style.SUCCESS if count > 0 else self.style.ERROR
            self.stdout.write(f'{status} {color(f"{model_name:<20}: {count:>6} records")}')
        
        self.stdout.write('')

    def display_municipalities(self, output_format, limit):
        """Display municipalities"""
        municipalities = MunicipalityName.objects.all()[:limit]
        
        if output_format == 'json':
            data = [{'id': m.municipality_id, 'name': m.municipality} for m in municipalities]
            self.stdout.write(json.dumps(data, indent=2))
        else:
            self.stdout.write(self.style.WARNING('MUNICIPALITIES:'))
            for municipality in municipalities:
                barangay_count = BarangayName.objects.filter(municipality_id=municipality).count()
                self.stdout.write(
                    f'  ID: {municipality.municipality_id:>2} | {municipality.municipality:<20} | Barangays: {barangay_count}'
                )
            self.stdout.write(f'Total: {MunicipalityName.objects.count()} municipalities\n')

    def display_barangays(self, output_format, limit):
        """Display barangays"""
        barangays = BarangayName.objects.select_related('municipality_id').all()[:limit]
        
        if output_format == 'json':
            data = [
                {
                    'id': b.barangay_id, 
                    'name': b.barangay, 
                    'municipality': b.municipality_id.municipality
                } 
                for b in barangays
            ]
            self.stdout.write(json.dumps(data, indent=2))
        else:
            self.stdout.write(self.style.WARNING('BARANGAYS:'))
            for barangay in barangays:
                self.stdout.write(
                    f'  ID: {barangay.barangay_id:>3} | {barangay.barangay:<25} | {barangay.municipality_id.municipality}'
                )
            self.stdout.write(f'Total: {BarangayName.objects.count()} barangays\n')

    def display_account_types(self, output_format, limit):
        """Display account types"""
        account_types = AccountType.objects.all()[:limit]
        
        if output_format == 'json':
            data = [{'id': a.account_type_id, 'type': a.account_type} for a in account_types]
            self.stdout.write(json.dumps(data, indent=2))
        else:
            self.stdout.write(self.style.WARNING('ACCOUNT TYPES:'))
            for acc_type in account_types:
                user_count = AuthUser.objects.filter(account_type_id=acc_type).count()
                self.stdout.write(
                    f'  ID: {acc_type.account_type_id} | {acc_type.account_type:<15} | Users: {user_count}'
                )
            self.stdout.write(f'Total: {AccountType.objects.count()} account types\n')

    def display_account_statuses(self, output_format, limit):
        """Display account statuses"""
        statuses = AccountStatus.objects.all()[:limit]
        
        if output_format == 'json':
            data = [{'id': s.acc_status_id, 'status': s.acc_status} for s in statuses]
            self.stdout.write(json.dumps(data, indent=2))
        else:
            self.stdout.write(self.style.WARNING('ACCOUNT STATUSES:'))
            for status in statuses:
                user_count = AuthUser.objects.filter(acc_status_id=status).count()
                self.stdout.write(
                    f'  ID: {status.acc_status_id} | {status.acc_status:<12} | Users: {user_count}'
                )
            self.stdout.write(f'Total: {AccountStatus.objects.count()} account statuses\n')

    def display_users(self, output_format, limit):
        """Display users (limited info for privacy)"""
        users = AuthUser.objects.select_related('account_type_id', 'acc_status_id').all()[:limit]
        
        if output_format == 'json':
            data = [
                {
                    'id': u.user_id,
                    'username': u.username,
                    'account_type': u.account_type_id.account_type if u.account_type_id else None,
                    'status': u.acc_status_id.acc_status if u.acc_status_id else None,
                    'created': u.date_joined.isoformat() if u.date_joined else None
                }
                for u in users
            ]
            self.stdout.write(json.dumps(data, indent=2))
        else:
            self.stdout.write(self.style.WARNING('USERS (Sample):'))
            for user in users:
                account_type = user.account_type_id.account_type if user.account_type_id else 'No type'
                status = user.acc_status_id.acc_status if user.acc_status_id else 'No status'
                self.stdout.write(
                    f'  ID: {user.user_id:>3} | {user.username:<20} | {account_type:<12} | {status}'
                )
            self.stdout.write(f'Total: {AuthUser.objects.count()} users\n')

    def display_months(self, output_format, limit):
        """Display months"""
        months = Month.objects.all().order_by('number')[:limit]
        
        if output_format == 'json':
            data = [{'id': m.id, 'name': m.name, 'number': m.number} for m in months]
            self.stdout.write(json.dumps(data, indent=2))
        else:
            self.stdout.write(self.style.WARNING('MONTHS:'))
            for month in months:
                self.stdout.write(f'  {month.number:>2} | {month.name}')
            self.stdout.write('')

    def display_units(self, output_format, limit):
        """Display unit measurements"""
        units = UnitMeasurement.objects.all()[:limit]
        
        if output_format == 'json':
            data = [{'id': u.unit_id, 'abbreviation': u.unit_abrv, 'full': u.unit_full} for u in units]
            self.stdout.write(json.dumps(data, indent=2))
        else:
            self.stdout.write(self.style.WARNING('UNIT MEASUREMENTS:'))
            for unit in units:
                self.stdout.write(f'  ID: {unit.unit_id} | {unit.unit_abrv:<3} | {unit.unit_full}')
            self.stdout.write('')
            seasonal_months = commodity.seasonal_months.count()
            self.stdout.write(f'  - {commodity.name} ({commodity.average_weight_per_unit_kg}kg avg, {seasonal_months} seasonal months)')
        
        # Check Users
        users = AuthUser.objects.all()
        self.stdout.write(f'\nUsers: {users.count()}')
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('Database check completed!'))