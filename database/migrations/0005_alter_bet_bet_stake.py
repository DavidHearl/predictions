# Generated by Django 3.2.21 on 2024-05-10 10:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0004_auto_20240510_1051'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bet',
            name='bet_stake',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]