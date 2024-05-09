from django.db import models


class Team(models.Model):
    team_name = models.CharField(max_length=100)
    league = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.team_name


class Match(models.Model):
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_team_name')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_team_name')

    date = models.DateTimeField(blank=True, null=True)
    
    home_win_percentage = models.FloatField(blank=True,null=True)
    draw_percentage = models.FloatField(blank=True,null=True)
    away_win_percentage = models.FloatField(blank=True,null=True)
    
    expected_goals = models.FloatField(blank=True,null=True)
    
    expected_home_team_goals = models.FloatField(blank=True, null=True)
    expected_away_team_goals = models.FloatField(blank=True, null=True)
    
    home_team_goals = models.IntegerField(blank=True,null=True)
    away_team_goals = models.IntegerField(blank=True,null=True)


# class Bet(models.Model):
#     match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='bets', null=True)
#     bet_type = models.CharField(max_length=100)
#     bet_stake = models.FloatField(null=True)
#     bet_return = models.FloatField(null=True)
#     bet_win = models.BooleanField(default=False)

#     bet_odds_numerator = models.IntegerField(null=True)
#     bet_odds_denominator = models.IntegerField(null=True)
#     bet_decimal_odds = models.FloatField(null=True)


# class OverallStatistics(models.Model):
#     total_bets = models.IntegerField()
#     correct_bets = models.IntegerField()
#     incorrect_bets = models.IntegerField()
#     bet_win_percentage = models.FloatField()
    
#     average_bet_odds = models.FloatField()
#     average_bet_stake = models.FloatField()
#     average_bet_return = models.FloatField()

#     pot = models.FloatField()
#     profit_loss = models.FloatField()

