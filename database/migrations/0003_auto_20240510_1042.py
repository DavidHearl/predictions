# Generated by Django 3.2.21 on 2024-05-10 09:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0002_auto_20240509_1856'),
    ]

    operations = [
        migrations.DeleteModel(
            name='OverallStatistics',
        ),
        migrations.AlterField(
            model_name='bet',
            name='bet_type',
            field=models.CharField(choices=[('over_0.5', 'Over 0.5'), ('over_1.5', 'Over 1.5'), ('under_3.5', 'Under 3.5'), ('under_4.5', 'Under 4.5'), ('under_5.5', 'Under 5.5'), ('win', 'Win')], max_length=100),
        ),
        migrations.AlterField(
            model_name='match',
            name='away_team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='away_team_name', to='database.team'),
        ),
        migrations.AlterField(
            model_name='match',
            name='away_team_goals',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='away_win_percentage',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='draw_percentage',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='expected_away_team_goals',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='expected_goals',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='expected_home_team_goals',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='home_team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='home_team_name', to='database.team'),
        ),
        migrations.AlterField(
            model_name='match',
            name='home_team_goals',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='home_win_percentage',
            field=models.FloatField(blank=True, null=True),
        ),
    ]