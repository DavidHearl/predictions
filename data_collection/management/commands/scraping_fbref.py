from django.core.management.base import BaseCommand
from data_collection.scraping.teams import *
from data_collection.scraping.players import *
from data_collection.scraping.matches import *


class Command(BaseCommand):
    help = (
        "Scrapes football data from FBref (teams, fixtures, players, matches). "
        "Fixtures (URLs + tables) are obtained earlier in the pipeline so you can "
        "see schedules and basic match data sooner."
    )

    def add_arguments(self, parser):
        # Optional flags to run subsets without editing code
        parser.add_argument("--only-fixtures", action="store_true",
                            help="Run only fixture URL build + fixture table scrape.")
        parser.add_argument("--from-fixtures", action="store_true",
                            help="Start at fixtures (skip seasons/teams) and continue the normal flow from there.")
        parser.add_argument("--no-process-matches", action="store_true",
                            help="Skip processing detailed match pages (shots, stats, player performances).")
        parser.add_argument("--no-players", action="store_true",
                            help="Skip player URL/detail scraping.")

    def handle(self, *args, **options):
        print("\n=== Starting FBref Scraping Pipeline ===")

        # fbref sits behind aggressive bot protection these days; check before
        # grinding through hundreds of URLs that will all fail.
        from data_collection.scraping.http import fetch
        probe = fetch("https://fbref.com/en/", retries=1)
        if probe is None:
            print(
                "WARNING: fbref.com is not reachable from here (likely a 403 from its "
                "bot protection). The pipeline will run but most requests may fail.\n"
                "Results and odds are better sourced via: manage.py import_football_data"
            )

        only_fixtures = options["only_fixtures"]
        from_fixtures = options["from_fixtures"]
        no_process_matches = options["no_process_matches"]
        no_players = options["no_players"]

        # ---------------------------------------------------------------------
        # Step 0–2: Seasons/Teams (SKIP if starting from fixtures)
        # ---------------------------------------------------------------------
        if not (only_fixtures or from_fixtures):
            # 1) Build season-league URLs
            urls = build_season_urls()
            print(f"build_season_urls(): {len(urls)} urls generated")

            # 2) Populate team data (Team, ClubSeason, etc.)
            populate_team_data()

        # ---------------------------------------------------------------------
        # Step 3–4: FIXTURES moved up (URLs + tables)
        # ---------------------------------------------------------------------
        # 3) Build fixture URLs for each league/season
        fixture_urls = build_fixture_urls()
        print(f"build_fixture_urls(): {len(fixture_urls)} fixture urls (new/total depending on implementation)")

        # 4) Scrape fixture tables (dates, teams, scores, basic info)
        get_fixture_tables()
        print("get_fixture_tables(): fixture tables collected")

        if only_fixtures:
            print("\n=== Fixtures phase complete (per --only-fixtures) ===")
            return

        # ---------------------------------------------------------------------
        # Step 5: Team URLs (for player scraping)
        # ---------------------------------------------------------------------
        # If we started from fixtures, we still need team URLs for players.
        team_urls = build_team_urls()
        print(f"build_team_urls(): {len(team_urls)} team urls (new/total depending on implementation)")

        # ---------------------------------------------------------------------
        # Step 6–7: Players (optional if you only care about fixtures now)
        # ---------------------------------------------------------------------
        if not no_players:
            extract_player_urls()
            populate_player_details()
        else:
            print("Skipping player scraping per --no-players")

        # ---------------------------------------------------------------------
        # Step 8: Match detail pages (optional if you don’t need deep stats now)
        # ---------------------------------------------------------------------
        if not no_process_matches:
            process_all_matches()
        else:
            print("Skipping detailed match processing per --no-process-matches")

        print("\n=== FBref Scraping Pipeline Complete ===")