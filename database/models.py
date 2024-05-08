from django.db import models


class OverallStatistics(models.Model):
    total_bets = models.IntegerField()
    correct_bets = models.IntegerField()
    incorrect_bets = models.IntegerField()
    bet_win_percentage = models.FloatField()
    
    average_bet_odds = models.FloatField()
    average_bet_stake = models.FloatField()
    average_bet_return = models.FloatField()

    pot = models.FloatField()
    profit_loss = models.FloatField()


class Team(models.Model):
    team_name = models.CharField(max_length=100)
    league = models.CharField(max_length=100, null=True)


class Match(models.Model):
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')

    date = models.DateTimeField(null=True)
    time = models.TimeField(null=True)
    
    home_win_percentage = models.FloatField(null=True)
    draw_percentage = models.FloatField(null=True)
    away_win_percentage = models.FloatField(null=True)
    
    expected_goals = models.FloatField(null=True)
    
    expected_home_team_goals = models.FloatField(null=True)
    expected_away_team_goals = models.FloatField(null=True)
    
    home_team_goals = models.IntegerField(null=True)
    away_team_goals = models.IntegerField(null=True)


class Bet(models.Model):
    bet_type = models.CharField(max_length=100)
    bet_stake = models.FloatField(null=True)
    bet_return = models.FloatField(null=True)
    bet_win = models.BooleanField(default=False)

    bet_odds_numerator = models.IntegerField(null=True)
    bet_odds_denominator = models.IntegerField(null=True)
    bet_decimal_odds = models.FloatField(null=True)
