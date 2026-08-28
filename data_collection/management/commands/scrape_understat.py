"""Merge understat.com xG into MatchTeamStat for leagues that understat covers.

Examples:
    python manage.py scrape_understat                     # current season, all covered leagues
    python manage.py scrape_understat --start-season 2021-2022
"""
from datetime import date

from django.core.management.base import BaseCommand

from data_collection.models import League, Season
from data_collection.scraping.football_data import season_name_for_date
from data_collection.scraping.understat import import_league_season_xg


class Command(BaseCommand):
    help = "Import xG per match from understat.com league pages"

    def add_arguments(self, parser):
        parser.add_argument("--leagues", type=str, default="",
                            help="Comma-separated understat slugs (e.g. EPL,La_liga). Default: all configured.")
        parser.add_argument("--start-season", type=str, default="",
                            help="Earliest season, e.g. 2021-2022. Default: current season only.")

    def handle(self, *args, **options):
        leagues = League.objects.exclude(understat_slug__isnull=True).exclude(understat_slug="")
        if options["leagues"]:
            wanted = {slug.strip() for slug in options["leagues"].split(",")}
            leagues = leagues.filter(understat_slug__in=wanted)

        current_season_name = season_name_for_date(date.today())
        current_start = int(current_season_name.split("-")[0])
        if options["start_season"]:
            first_start = int(options["start_season"].split("-")[0])
        else:
            first_start = current_start

        for year in range(first_start, current_start + 1):
            season_name = f"{year}-{year + 1}"
            season, _ = Season.objects.get_or_create(name=season_name)
            for league in leagues:
                updated, missing = import_league_season_xg(league, season)
                self.stdout.write(
                    f"  {league.name} {season_name}: xG merged into {updated} matches"
                    + (f" ({missing} not found locally)" if missing else "")
                )

        self.stdout.write(self.style.SUCCESS("understat xG import complete."))
