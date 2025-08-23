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
admin.site.register(Match)
admin.site.register(MatchShot)
admin.site.register(MatchTeamStat)
admin.site.register(MatchPlayerStat)
admin.site.register(Prediction)

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