# Generated by Django 5.2.2 on 2025-06-18 21:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_collection', '0011_rename_unqiue_code_team_unique_code'),
    ]

    operations = [
        migrations.RenameField(
            model_name='matchteamstat',
            old_name='shots_off_target',
            new_name='total_shots',
        ),
    ]
