from django.contrib import admin
from .models import *


class SeasonAdmin(admin.ModelAdmin):
    list_display = ('season',)  # Remove the extra comma

class LeagueAdmin(admin.ModelAdmin):
    list_display = ('name',)

class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('league', 'season')

class TeamAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'league', 'season')


admin.site.register(Season, SeasonAdmin)
admin.site.register(League, LeagueAdmin)
admin.site.register(Competition, CompetitionAdmin)
admin.site.register(Team, TeamAdmin)
