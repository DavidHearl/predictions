from django import forms
from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from .models import *

# Register your models here.
admin.site.register(Season)
admin.site.register(League)
admin.site.register(Team)
admin.site.register(ClubSeason)
admin.site.register(Player)
admin.site.register(MatchShot)
admin.site.register(MatchTeamStat)
admin.site.register(MatchPlayerStat)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("date", "home_team", "away_team", "home_score", "away_score", "league", "season")
    list_filter = ("league", "season")
    search_fields = ("home_team__name", "away_team__name")
    date_hierarchy = "date"


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("match", "predicted_result", "prob_home", "prob_draw", "prob_away",
                    "predicted_home_score", "predicted_away_score", "model_name", "updated_at")
    search_fields = ("match__home_team__name", "match__away_team__name")


@admin.register(MatchOdds)
class MatchOddsAdmin(admin.ModelAdmin):
    list_display = ("match", "source", "home_odds", "draw_odds", "away_odds",
                    "over25_odds", "under25_odds", "is_closing", "updated_at")
    list_filter = ("source", "is_closing")
    search_fields = ("match__home_team__name", "match__away_team__name")


@admin.register(TeamAlias)
class TeamAliasAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "source")
    list_filter = ("source",)
    search_fields = ("name", "team__name")

class BetForm(forms.ModelForm):
    class Meta:
        model = Bet
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        one_week_ago = timezone.now() - timedelta(days=7)
        self.fields['match'].queryset = Match.objects.filter(date__gte=one_week_ago)

class BetAdmin(admin.ModelAdmin):
    form = BetForm
    raw_id_fields = ['account']

admin.site.register(Bet, BetAdmin)
admin.site.register(BettingAccount)