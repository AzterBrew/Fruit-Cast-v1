from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.management import call_command
import os
from base.models import *


class Command(BaseCommand):
    help = 'Initialize the database with essential data for FruitCast system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of data even if it exists',
        )
        parser.add_argument(
            '--use-fixtures',
            action='store_true',
            help='Load data from JSON fixtures instead of creating programmatically',
        )
        parser.add_argument(
            '--fixtures-only',
            action='store_true',
            help='Only load from fixtures, skip programmatic creation',
        )

    def handle(self, *args, **options):
        force = options['force']
        use_fixtures = options['use_fixtures']
        fixtures_only = options['fixtures_only']
        
        with transaction.atomic():
            self.stdout.write(self.style.SUCCESS('Starting database initialization...'))
            
            if fixtures_only:
                # Load all data from fixtures only
                self.load_all_fixtures(force)
            elif use_fixtures:
                # Load from fixtures where available, fallback to programmatic
                self.load_from_fixtures_with_fallback(force)
            else:
                # Use programmatic setup (original behavior)
                self.setup_programmatically(force)
            
            self.stdout.write(
                self.style.SUCCESS('Database initialization completed successfully!')
            )

    def load_all_fixtures(self, force):
        """Load all data from JSON fixtures"""
        if force:
            self.stdout.write('Clearing existing data...')
            # Clear in reverse order of dependencies
            BarangayName.objects.all().delete()
            MunicipalityName.objects.all().delete()
            UnitMeasurement.objects.all().delete()
            Month.objects.all().delete()
            AccountStatus.objects.all().delete()
            AccountType.objects.all().delete()
        
        fixtures = [
            'account_types.json',
            'account_statuses.json', 
            'months.json',
            'unit_measurements.json',
            'bataan_municipalities.json',
            'bataan_barangays.json'
        ]
        
        for fixture in fixtures:
            try:
                call_command('loaddata', fixture)
                self.stdout.write(f'✓ Loaded {fixture}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to load {fixture}: {e}')
                )
        
        # Setup commodities programmatically since no fixture exists
        self.setup_commodity_types(force)
        self.setup_seasonal_relationships()

    def load_from_fixtures_with_fallback(self, force):
        """Load from fixtures where available, use programmatic for others"""
        # Try fixtures first
        try:
            self.load_all_fixtures(force)
            self.stdout.write('Using fixtures for core data...')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Fixture loading failed, using programmatic setup: {e}')
            )
            self.setup_programmatically(force)
        
        # Always setup commodities programmatically (includes seasonal relationships)
        self.setup_commodity_types(force)
        self.setup_seasonal_relationships()

    def setup_programmatically(self, force):
        """Original programmatic setup"""
        # Setup account types
        self.setup_account_types(force)
        
        # Setup account statuses
        self.setup_account_statuses(force)
        
        # Setup months
        self.setup_months(force)
        
        # Setup unit measurements
        self.setup_unit_measurements(force)
        
        # Setup municipalities (using JSON fixture or manual setup)
        self.setup_municipalities(force)
        
        # Setup barangays for all municipalities
        self.setup_barangays(force)
        
        # Setup commodity types
        self.setup_commodity_types(force)
        
        # Setup seasonal relationships
        self.setup_seasonal_relationships()

    def setup_account_types(self, force):
        """Setup account types"""
        if AccountType.objects.exists() and not force:
            self.stdout.write('Account types already exist, skipping...')
            return
            
        if force:
            AccountType.objects.all().delete()
            
        account_types = ['Farmer', 'Administrator','Agriculturist']
        
        for acc_type in account_types:
            obj, created = AccountType.objects.get_or_create(
                account_type=acc_type
            )
            if created:
                self.stdout.write(f'Created account type: {acc_type}')

    def setup_account_statuses(self, force):
        """Setup account statuses"""
        if AccountStatus.objects.exists() and not force:
            self.stdout.write('Account statuses already exist, skipping...')
            return
            
        if force:
            AccountStatus.objects.all().delete()
            
        statuses = [
            'Removed',     # 1
            'Verified',    # 2
            'Pending',     # 3
            'Rejected',    # 4
            'Archived',    # 5
            'Suspended'    # 6
        ]
        
        for status in statuses:
            obj, created = AccountStatus.objects.get_or_create(
                acc_status=status
            )
            if created:
                self.stdout.write(f'Created account status: {status}')

    def setup_months(self, force):
        """Setup months"""
        if Month.objects.exists() and not force:
            self.stdout.write('Months already exist, skipping...')
            return
            
        if force:
            Month.objects.all().delete()
            
        months = [
            ('January', 1), ('February', 2), ('March', 3), ('April', 4),
            ('May', 5), ('June', 6), ('July', 7), ('August', 8),
            ('September', 9), ('October', 10), ('November', 11), ('December', 12)
        ]
        
        for name, number in months:
            obj, created = Month.objects.get_or_create(
                name=name,
                number=number
            )
            if created:
                self.stdout.write(f'Created month: {name}')

    def setup_unit_measurements(self, force):
        """Setup unit measurements"""
        if UnitMeasurement.objects.exists() and not force:
            self.stdout.write('Unit measurements already exist, skipping...')
            return
            
        if force:
            UnitMeasurement.objects.all().delete()
            
        units = [
            ('kg', 'kilogram'),
            ('g', 'gram'),
            ('t', 'tonne'),
            ('lb', 'pound'),
        ]
        
        for abrv, full in units:
            obj, created = UnitMeasurement.objects.get_or_create(
                unit_abrv=abrv,
                unit_full=full
            )
            if created:
                self.stdout.write(f'Created unit: {full} ({abrv})')

    def setup_municipalities(self, force):
        """Setup Bataan municipalities with specific PKs to match JSON fixture"""
        if MunicipalityName.objects.exists() and not force:
            self.stdout.write('Municipalities already exist, skipping...')
            return
            
        if force:
            MunicipalityName.objects.all().delete()
            
        # Use the same PK mapping as in the JSON fixture
        municipalities_with_pk = [
            (1, 'Abucay'),
            (2, 'Bagac'), 
            (3, 'Balanga'),
            (4, 'Dinalupihan'),
            (5, 'Hermosa'),
            (6, 'Limay'),
            (7, 'Mariveles'),
            (8, 'Morong'),
            (9, 'Orani'),
            (11, 'Orion'),  # Note: PK 10 is skipped to match your JSON
            (12, 'Pilar'),
            (13, 'Samal'),
            (14, 'Overall in Bataan')
        ]
        
        for pk, municipality_name in municipalities_with_pk:
            obj, created = MunicipalityName.objects.get_or_create(
                municipality_id=pk,
                defaults={'municipality': municipality_name}
            )
            if created:
                self.stdout.write(f'Created municipality: {municipality_name} (ID: {pk})')
            elif obj.municipality != municipality_name:
                # Update if the name differs
                obj.municipality = municipality_name
                obj.save()
                self.stdout.write(f'Updated municipality: {municipality_name} (ID: {pk})')

    def setup_barangays(self, force):
        """Setup all Bataan barangays with specific PKs to match JSON fixture"""
        if BarangayName.objects.exists() and not force:
            self.stdout.write('Barangays already exist, skipping...')
            return
            
        if force:
            BarangayName.objects.all().delete()
        
        # All barangays with their PKs and municipality mappings
        barangays_data = [
            # Abucay (municipality_id = 1)
            (1, 'Bangkal', 1), (2, 'Calaguiman', 1), (3, 'Capitangan', 1),
            (4, 'Gabon', 1), (5, 'Laon', 1), (6, 'Mabatang', 1),
            (7, 'Omboy', 1), (8, 'Salian', 1), (9, 'Wawa', 1),
            
            # Bagac (municipality_id = 2)
            (10, 'Bagumbayan', 2), (11, 'Binuangan', 2), (12, 'Dahican', 2),
            (13, 'Ibaba', 2), (14, 'Ibis', 2), (15, 'Looc', 2),
            (16, 'Pag-asa', 2), (17, 'Parang', 2), (18, 'Paysawan', 2),
            (19, 'Saysain', 2), (20, 'Tabing-dagat', 2), (21, 'Tupul', 2),
            
            # Balanga (municipality_id = 3)
            (22, 'Bagong Silang', 3), (23, 'Bagumbayan', 3), (24, 'Cabog-cabog', 3),
            (25, 'Cataning', 3), (26, 'Central', 3), (27, 'Cupang North', 3),
            (28, 'Cupang Proper', 3), (29, 'Cupang West', 3), (30, 'Dangcol', 3),
            (31, 'Doña Francisca', 3), (32, 'Ibayo', 3), (33, 'Lote', 3),
            (34, 'Malabia', 3), (35, 'Munting Batangas', 3), (36, 'Pampanga', 3),
            (37, 'Peñaranda', 3), (38, 'Poblacion', 3), (39, 'Puerto Rivas Ibaba', 3),
            (40, 'Puerto Rivas Itaas', 3), (41, 'Puerto Rivas Lote', 3), (42, 'San Jose', 3),
            (43, 'Sibacan', 3), (44, 'Talisay', 3), (45, 'Tanato', 3),
            (46, 'T.M. Kalaw', 3), (47, 'Tortugas', 3), (48, 'Tuyo', 3),
            
            # Dinalupihan (municipality_id = 4)
            (49, 'Aglao', 4), (50, 'Almacen', 4), (51, 'Bacao', 4),
            (52, 'Bagong Daan', 4), (53, 'Bangal', 4), (54, 'Bayan-bayanan', 4),
            (55, 'Benuan', 4), (56, 'Bonifacio (Poblacion)', 4), (57, 'Burgos (Poblacion)', 4),
            (58, 'Colo', 4), (59, 'Dalao', 4), (60, 'Del Pilar (Poblacion)', 4),
            (61, 'Gen. Luna (Poblacion)', 4), (62, 'Gomok', 4), (63, 'Happy Valley', 4),
            (64, 'Jacinto (Poblacion)', 4), (65, 'Jose C. Payumo, Jr.', 4), (66, 'Kataasan', 4),
            (67, 'Layac', 4), (68, 'Luacan', 4), (69, 'Mabini', 4),
            (70, 'Maligaya (Poblacion)', 4), (71, 'Mambog', 4), (72, 'Manggahan', 4),
            (73, 'Napco', 4), (74, 'New San Jose', 4), (75, 'New Sitio', 4),
            (76, 'Old San Jose (Poblacion)', 4), (77, 'Pag-asa (Poblacion)', 4), (78, 'Padre Dandan (Poblacion)', 4),
            (79, 'Palanginan', 4), (80, 'Payangan', 4), (81, 'Pinulot', 4),
            (82, 'Pita', 4), (83, 'Poblacion', 4), (84, 'President Roxas (Poblacion)', 4),
            (85, 'Roosevelt', 4), (86, 'San Benito', 4), (87, 'San Pablo', 4),
            (88, 'San Ramon', 4), (89, 'San Simon', 4), (90, 'Santa Isabel', 4),
            (91, 'Santo Niño (Poblacion)', 4), (92, 'Sapa', 4), (93, 'Sitio Maligaya', 4),
            (94, 'Tubo-tubong', 4), (95, 'Tukop', 4), (96, 'Zamora (Poblacion)', 4),
            
            # Hermosa (municipality_id = 5)
            (97, 'A. Mabini', 5), (98, 'Almacen', 5), (99, 'Bacong', 5),
            (100, 'Balsic', 5), (101, 'Culis', 5), (102, 'Daungan', 5),
            (103, 'Hermosa', 5), (104, 'Judge R.S. Roman', 5), (105, 'Mabuco', 5),
            (106, 'Maite', 5), (107, 'Mambog', 5), (108, 'Palihan', 5),
            (109, 'Pantalan Lote', 5), (110, 'Pulo', 5), (111, 'Sacrifice Valley', 5),
            (112, 'Saint Francis', 5), (113, 'San Pedro', 5), (114, 'San Vicente', 5),
            (115, 'Santa Cruz', 5), (116, 'Santo Cristo', 5), (117, 'Sumalo', 5),
            (118, 'Tapulao', 5), (119, 'Tipo', 5),
            
            # Limay (municipality_id = 6)
            (120, 'Alangan', 6), (121, 'Bote', 6), (122, 'Duale', 6),
            (123, 'Kitang I (Poblacion)', 6), (124, 'Kitang II (Poblacion)', 6), (125, 'Lamao', 6),
            (126, 'Landing', 6), (127, 'Luacan', 6), (128, 'Luz', 6),
            (129, 'Paking-Sapa', 6), (130, 'Reformista', 6), (131, 'San Roque', 6),
            (132, 'Wawa', 6),
            
            # Mariveles (municipality_id = 7)
            (133, 'Alion', 7), (134, 'Balon-Anito', 7), (135, 'Baseco', 7),
            (136, 'Batangas II', 7), (137, 'Biaan', 7), (138, 'Cabcaben', 7),
            (139, 'Camaya', 7), (140, 'Fabrica', 7), (141, 'Ipag', 7),
            (142, 'Lucanin', 7), (143, 'Malaya', 7), (144, 'Maligaya', 7),
            (145, 'Mt. View', 7), (146, 'Poblacion', 7), (147, 'San Carlos', 7),
            (148, 'San Isidro', 7), (149, 'Sisiman', 7), (150, 'Townsite', 7),
            
            # Morong (municipality_id = 8)
            (151, 'Anupat', 8), (152, 'Binaritan', 8), (153, 'Nagbalayong', 8),
            (154, 'Poblacion', 8), (155, 'Sabang', 8),
            
            # Orani (municipality_id = 9)
            (156, 'Bagong Daan', 9), (157, 'Balut', 9), (158, 'Bayan', 9),
            (159, 'Calero', 9), (160, 'Capitol', 9), (161, 'Cataning', 9),
            (162, 'Centro I', 9), (163, 'Centro II', 9), (164, 'Dalao', 9),
            (165, 'Kaparangan', 9), (166, 'Masantol', 9), (167, 'Mulawin', 9),
            (168, 'Pag-asa', 9), (169, 'Palihan', 9), (170, 'Pantalan Bago', 9),
            (171, 'Pantalan Luma', 9), (172, 'Parang Parang', 9), (173, 'Puksuan', 9),
            (174, 'Sibul', 9), (175, 'Silahis', 9), (176, 'Tala', 9),
            (177, 'Talimundoc', 9), (178, 'Tapulao', 9), (179, 'Tenejero', 9),
            (180, 'Tugatog', 9), (181, 'Tuyo', 9), (182, 'Wawa', 9),
            
            # Orion (municipality_id = 11)
            (183, 'Arellano (Poblacion)', 11), (184, 'Bagumbayan (Poblacion)', 11), (185, 'Balagtas', 11),
            (186, 'Balut', 11), (187, 'Bantan', 11), (188, 'Calungusan', 11),
            (189, 'Capunitan', 11), (190, 'Daang Bago', 11), (191, 'Daang Pare', 11),
            (192, 'General Lim (Poblacion)', 11), (193, 'Liyang', 11), (194, 'Pantalan Bago', 11),
            (195, 'Pantalan Luma', 11), (196, 'Pilar', 11), (197, 'Poblacion', 11),
            (198, 'Puting Buhangin', 11), (199, 'San Roque', 11), (200, 'San Vicente', 11),
            (201, 'Santa Elena', 11), (202, 'Santo Domingo', 11), (203, 'Talimundoc', 11),
            (204, 'Villa Angeles', 11), (205, 'Wawa', 11),
            
            # Pilar (municipality_id = 12)
            (206, 'Ala-uli', 12), (207, 'Balut', 12), (208, 'Bantan', 12),
            (209, 'Buas', 12), (210, 'Del Rosario', 12), (211, 'Diwa', 12),
            (212, 'Landing', 12), (213, 'Liyang', 12), (214, 'Nagwaling', 12),
            (215, 'Panilao', 12), (216, 'Pantingan', 12), (217, 'Poblacion', 12),
            (218, 'San Antonio', 12), (219, 'San Isidro', 12), (220, 'San Rafael', 12),
            (221, 'Santa Rosa', 12), (222, 'Tanato', 12), (223, 'Wakas North', 12),
            (224, 'Wakas South', 12),
            
            # Samal (municipality_id = 13)
            (225, 'Gugo', 13), (226, 'Imelda', 13), (227, 'Lalawigan', 13),
            (228, 'Palog', 13), (229, 'Pamatawan', 13), (230, 'San Juan', 13),
            (231, 'Santa Lucia', 13), (232, 'Sapa', 13), (233, 'Tabing Ilog', 13),
            (234, 'Tabing-dagat', 13), (235, 'Ward I (Poblacion)', 13), (236, 'Ward II (Poblacion)', 13),
            (237, 'Ward III (Poblacion)', 13), (238, 'Ward IV (Poblacion)', 13)
        ]
        
        created_count = 0
        for pk, barangay_name, municipality_id in barangays_data:
            obj, created = BarangayName.objects.get_or_create(
                barangay_id=pk,
                defaults={
                    'barangay': barangay_name,
                    'municipality_id_id': municipality_id
                }
            )
            if created:
                created_count += 1
                if created_count % 20 == 0:  # Progress indicator
                    self.stdout.write(f'Created {created_count} barangays...')
            elif obj.barangay != barangay_name or obj.municipality_id_id != municipality_id:
                # Update if data differs
                obj.barangay = barangay_name
                obj.municipality_id_id = municipality_id
                obj.save()
                self.stdout.write(f'Updated barangay: {barangay_name} (ID: {pk})')
        
        self.stdout.write(f'✓ Setup complete: {created_count} barangays created, {len(barangays_data)} total')

    def load_municipalities_from_fixture(self, force):
        """Alternative: Load municipalities from JSON fixture"""
        if MunicipalityName.objects.exists() and not force:
            self.stdout.write('Municipalities already exist, skipping...')
            return
            
        if force:
            MunicipalityName.objects.all().delete()
            
        try:
            call_command('loaddata', 'bataan_municipalities.json')
            self.stdout.write('Loaded municipalities from JSON fixture')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to load municipalities fixture: {e}')
            )
 