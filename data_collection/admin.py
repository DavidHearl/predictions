from django.contrib import admin
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