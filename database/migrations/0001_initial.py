# Generated by Django 3.2.25 on 2024-05-08 21:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Bet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bet_type', models.CharField(max_length=100)),
                ('bet_stake', models.FloatField(null=True)),
                ('bet_return', models.FloatField(null=True)),
                ('bet_win', models.BooleanField(default=False)),
                ('bet_odds_numerator', models.IntegerField(null=True)),
                ('bet_odds_denominator', models.IntegerField(null=True)),
                ('bet_decimal_odds', models.FloatField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='OverallStatistics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_bets', models.IntegerField()),
                ('correct_bets', models.IntegerField()),
                ('incorrect_bets', models.IntegerField()),
                ('bet_win_percentage', models.FloatField()),
                ('average_bet_odds', models.FloatField()),
                ('average_bet_stake', models.FloatField()),
                ('average_bet_return', models.FloatField()),
                ('pot', models.FloatField()),
                ('profit_loss', models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('team_name', models.CharField(max_length=100)),
                ('league', models.CharField(max_length=100, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(null=True)),
                ('time', models.TimeField(null=True)),
                ('home_win_percentage', models.FloatField(null=True)),
                ('draw_percentage', models.FloatField(null=True)),
                ('away_win_percentage', models.FloatField(null=True)),
                ('expected_goals', models.FloatField(null=True)),
                ('expected_home_team_goals', models.FloatField(null=True)),
                ('expected_away_team_goals', models.FloatField(null=True)),
                ('home_team_goals', models.IntegerField(null=True)),
                ('away_team_goals', models.IntegerField(null=True)),
                ('away_team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='away_matches', to='database.team')),
                ('home_team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='home_matches', to='database.team')),
            ],
        ),
    ]
