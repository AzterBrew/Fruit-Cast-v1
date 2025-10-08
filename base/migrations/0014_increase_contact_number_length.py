# Generated manually to increase contact number field length

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0013_remove_initharvestrecord_weight_per_unit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userinformation',
            name='contact_number',
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name='userinformation',
            name='emergency_contact_number',
            field=models.CharField(max_length=20),
        ),
    ]