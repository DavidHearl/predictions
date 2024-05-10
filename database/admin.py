from django.contrib import admin
from .models import Team, Match, Bet


class TeamAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'league')


class MatchAdmin(admin.ModelAdmin):
    list_display = ('home_team', 'away_team', 'date', 'home_win_percentage', 'draw_percentage', 'away_win_percentage', 'expected_goals', 'expected_home_team_goals', 'expected_away_team_goals', 'home_team_goals', 'away_team_goals')


class BetAdmin(admin.ModelAdmin):
    list_display = ('match', 'bet_type', 'bet_stake', 'bet_return', 'bet_win', 'bet_odds_numerator', 'bet_odds_denominator', 'bet_decimal_odds')


admin.site.register(Team, TeamAdmin)
admin.site.register(Match, MatchAdmin)
admin.site.register(Bet, BetAdmin)
