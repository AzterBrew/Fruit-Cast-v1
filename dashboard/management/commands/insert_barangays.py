from django.core.management.base import BaseCommand
from base.models import BarangayName

class Command(BaseCommand):
    help = 'Insert barangay records'

    def handle(self, *args, **kwargs):
        data = [
            ('Bangkal',1), ('Calaylayan',1),('Capitangan',1),('Gabon',1),('Laon',1),('Mabatang',1),('Omboy',1),('Salian',1),('Wawa',1),
('Atilano L. Ricardo',2), ('Bagumbayan',2),('Banawang',2),('Binuangan',2),('Binukawan',2),('Ibaba',2),('Ibis',2),('Pag-asa',2),('Parang',2),
('Paysawan',2), ('Quinawan',2),('San Antonio',2),('Saysain',2),('Tabing-Ilog',2),
('Bagong Silang',3), ('Bagumbayan',3),('Cabog-Cabog',3),('Camacho',3),('Cataning',3),('Central',3),('Cupang North',3),('Cupang Proper',3),('Cupang West',3),
('Dangcol',3), ('Doña Francisca',3),('Ibayo',3),('Lote',3),('Malabia',3),('Munting Batangas',3),('Poblacion',3),('Pto. Rivas Ibaba',3),('Pto. Rivas Itaas',3),
('San Jose',3), ('Sibacan',3),('Talisay',3),('Tanato',3),('Tenejero',3),('Tortugas',3),('Tuyo',3),
('Aquino',4), ('Bangal',4), ('Bayan-bayanan',4), ('Bonifacio',4), ('Burgos',4), ('Colo',4), ('Daang Bago',4), ('Dalao',4), ('Del Pilar',4), ('Gen. Luna',4), ('Gomez',4), ('Happy Valley',4), ('Jose C. Payumo, Jr.',4), ('Kataasan',4), ('Layac',4), ('Luacan',4), ('Mabini Ext.',4), ('Mabini Proper',4), ('Magsaysay',4), ('Maligaya',4), ('Naparing',4), ('New San Jose',4), ('Old San Jose',4), ('Padre Dandan',4), ('Pag-asa',4), ('Pagalanggang',4), ('Payangan',4), ('Pentor',4), ('Pinulot',4), ('Pita',4), ('Rizal',4), ('Roosevelt',4), ('Roxas',4), ('Saguing',4), ('San Benito',4), ('San Isidro',4), ('San Pablo',4), ('San Ramon',4), ('San Simon',4), ('Santa Isabel',4), ('Santo Niño',4), ('Sapang Balas',4), ('Torres Bugauen',4), ('Tubo-tubo',4), ('Tucop',4), ('Zamora',4),
('A. Rivera',5), ('Almacen',5), ('Bacong',5), ('Balsic',5), ('Bamban',5), ('Burgos-Soliman',5), ('Cataning',5), ('Culis',5), ('Daungan',5), ('Judge Roman Cruz Sr.',5), ('Mabiga',5), ('Mabuco',5), ('Maite',5), ('Mambog-Mandama',5), ('Palihan',5), ('Pandatung',5), ('Pulo',5), ('Saba',5), ('Sacrifice Valley',5), ('San Pedro',5), ('Santo Cristo',5), ('Sumalo',5), ('Tipo',5),
('East Calaguiman',13), ('East Daang Bago',13), ('Gugo',13), ('Ibaba',13), ('Imelda',13), ('Lalawigan',13), ('Palili',13), ('San Juan',13), ('San Roque',13), ('Santa Lucia',13), ('Sapa',13), ('Tabing Ilog',13), ('West Calaguiman',13), ('West Daang Bago',13),
('Alangan',6), ('Duale',6), ('Kitang 2 & Luz',6), ('Kitang I',6), ('Lamao',6), ('Landing',6), ('Poblacion',6), ('Reformista',6), ('Saint Francis II',6), ('San Francisco de Asis',6), ('Townsite',6), ('Wawa',6),
('Ala-uli',12),  ('Bagumbayan',12),  ('Balut I',12),  ('Balut II',12),  ('Bantan Munti',12),  ('Burgos',12),  ('Del Rosario',12),  ('Diwa',12),  ('Landing',12),  ('Liyang',12),  ('Nagwaling',12),  ('Panilao',12),  ('Pantingan',12),  ('Poblacion',12),  ('Rizal',12),  ('Santa Rosa',12),  ('Wakas North',12),  ('Wakas South',12),  ('Wawa',12),
 ('Alas-asin',7), ('Alion',7), ('Balon-Anito',7), ('Baseco Country',7), ('Batangas II',7), ('Biaan',7), ('Cabcaben',7), ('Camaya',7), ('Ipag',7), ('Lucanin',7), ('Malaya',7), ('Maligaya',7), ('Mt. View',7), ('Poblacion',7), ('San Carlos',7), ('San Isidro',7), ('Sisiman',7), ('Townsite',7),
 ('Binaritan',8), ('Mabayo',8), ('Nagbalayong',8), ('Poblacion',8), ('Sabang',8),
('Arellano',11), ('Bagumbayan',11), ('Balagtas',11), ('Balut',11), ('Bantan',11), ('Bilolo',11), ('Calungusan',11), ('Camachile',11), ('Daang Bago',11), ('Daang Bilolo',11), ('Daang Pare',11), ('General Lim',11), ('Kapunitan',11), ('Lati',11), ('Lusungan',11), ('Puting Buhangin',11), ('Sabatan',11), ('San Vicente',11), ('Santa Elena',11), ('Santo Domingo',11), ('Villa Angeles',11), ('Wakas',11), ('Wawa',11),
('Apollo',9), ('Bagong Paraiso',9), ('Balut',9), ('Bayan',9), ('Calero',9), ('Centro I',9), ('Centro II',9), ('Dona',9), ('Kabalutan',9), ('Kaparangan',9), ('Maria Fe',9), ('Masantol',9), ('Mulawin',9), ('Pag-asa',9), ('Paking-Carbonero',9), ('Palihan',9), ('Pantalan Bago',9), ('Pantalan Luma',9), ('Parang Parang',9), ('Puksuan',9), ('Sibul',9), ('Silahis',9), ('Tagumpay',9), ('Tala',9), ('Talimundoc',9), ('Tapulao',9), ('Tenejero',9), ('Tugatog',9), ('Wawa',9)

        ]
        
        for barangay, municipality_id in data:
            BarangayName.objects.get_or_create(barangay=barangay, municipality_id_id=municipality_id)
        self.stdout.write(self.style.SUCCESS('Barangays inserted!'))