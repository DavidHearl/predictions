"""Import results, stats and odds from football-data.co.uk.

Examples:
    python manage.py import_football_data                       # all leagues, last 4 seasons + fixtures
    python manage.py import_football_data --leagues E0,E1
    python manage.py import_football_data --start-season 2019-2020
    python manage.py import_football_data --fixtures-only       # just refresh upcoming fixtures/odds
"""
from django.core.management.base import BaseCommand, CommandError

from data_collection.models import League, Season
from data_collection.scraping.football_data import (
    import_fixtures, import_results, season_name_for_date,
)
from datetime import date


class Command(BaseCommand):
    help = "Import results/odds CSVs and upcoming fixtures from football-data.co.uk"

    def add_arguments(self, parser):
        parser.add_argument("--leagues", type=str, default="",
                            help="Comma-separated fd codes (e.g. E0,E1). Default: all configured leagues.")
        parser.add_argument("--start-season", type=str, default="",
                            help="Earliest season to import, e.g. 2021-2022. Default: 3 seasons before current.")
        parser.add_argument("--fixtures-only", action="store_true",
                            help="Only refresh upcoming fixtures and odds.")
        parser.add_argument("--no-fixtures", action="store_true",
                            help="Skip the upcoming-fixtures refresh.")

    def handle(self, *args, **options):
        leagues = League.objects.exclude(fd_code__isnull=True).exclude(fd_code="")
        if options["leagues"]:
            wanted = {code.strip().upper() for code in options["leagues"].split(",")}
            leagues = leagues.filter(fd_code__in=wanted)
        if not leagues.exists() and not options["fixtures_only"]:
            raise CommandError("No matching leagues with fd_code set. Run `manage.py setup_sources` first.")

        current_season_name = season_name_for_date(date.today())
        current_start = int(current_season_name.split("-")[0])

        if not options["fixtures_only"]:
            if options["start_season"]:
                try:
                    first_start = int(options["start_season"].split("-")[0])
                except (ValueError, IndexError):
                    raise CommandError("--start-season must look like 2021-2022")
            else:
                first_start = current_start - 3

            season_names = [f"{y}-{y + 1}" for y in range(first_start, current_start + 1)]
            self.stdout.write(f"Importing seasons {season_names[0]} .. {season_names[-1]} "
                              f"for {', '.join(l.fd_code for l in leagues)}")

            for season_name in season_names:
                season, _ = Season.objects.get_or_create(name=season_name)
                for league in leagues:
                    created, updated = import_results(league, season)
                    self.stdout.write(
                        f"  {league.fd_code} {season_name}: {created} new matches, {updated} updated"
                    )

        if not options["no_fixtures"]:
            created, updated = import_fixtures()
            self.stdout.write(self.style.SUCCESS(
                f"Fixtures refresh: {created} new, {updated} updated (with current odds)"
            ))

        self.stdout.write(self.style.SUCCESS("football-data import complete."))
