"""Seed/refresh the League and Season tables with data-source identifiers.

Idempotent: existing leagues are matched by fbref league_id (then by name) and
enriched with football-data / understat codes rather than duplicated.
"""
from datetime import date

from django.core.management.base import BaseCommand

from data_collection.models import League, Season

LEAGUES = [
    # (fbref id, name, country, teams, fd_code, understat_slug)
    # Second divisions are tracked too: pooled country fits mean promoted teams
    # arrive in the top flight with a real rating instead of a blank one.
    (9,  "Premier League",  "England",  20, "E0",  "EPL"),
    (10, "Championship",    "England",  24, "E1",  None),
    (15, "League One",      "England",  24, "E2",  None),
    (12, "La Liga",         "Spain",    20, "SP1", "La_liga"),
    (17, "Segunda Division", "Spain",   22, "SP2", None),
    (11, "Serie A",         "Italy",    20, "I1",  "Serie_A"),
    (18, "Serie B",         "Italy",    20, "I2",  None),
    (20, "Bundesliga",      "Germany",  18, "D1",  "Bundesliga"),
    (33, "2 Bundesliga",    "Germany",  18, "D2",  None),
    (13, "Ligue 1",         "France",   18, "F1",  "Ligue_1"),
    (60, "Ligue 2",         "France",   18, "F2",  None),
]

FIRST_SEASON_START = 2019


def current_season_start_year(today=None):
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


class Command(BaseCommand):
    help = "Create/update League rows (with source codes) and Season rows up to the current season."

    def handle(self, *args, **options):
        for league_id, name, country, teams, fd_code, understat_slug in LEAGUES:
            league = (
                League.objects.filter(league_id=league_id).first()
                or League.objects.filter(name__iexact=name).first()
            )
            if league is None:
                league = League(league_id=league_id, name=name)
                verb = "Created"
            else:
                verb = "Updated"
            league.name = league.name or name
            league.country = country
            league.league_id = league_id
            league.number_of_teams = teams
            league.fd_code = fd_code
            league.understat_slug = understat_slug
            league.save()
            self.stdout.write(f"{verb} league: {league.name} (fd={fd_code}, understat={understat_slug})")

        created = 0
        for year in range(FIRST_SEASON_START, current_season_start_year() + 1):
            _, was_created = Season.objects.get_or_create(name=f"{year}-{year + 1}")
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f"Seasons up to {current_season_start_year()}-{current_season_start_year() + 1} ensured "
            f"({created} new)."
        ))
