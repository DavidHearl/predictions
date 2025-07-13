from django.core.management.base import BaseCommand
from data_collection.scraping.teams import *
from data_collection.scraping.players import *
from data_collection.scraping.matches import *


class Command(BaseCommand):
    help = "Scrapes football data from FBref including teams, players, and matches"

    def handle(self, *args, **options):
        """
        Executes the full scraping pipeline in sequence to collect football data.
        
        The pipeline is designed to be run in order, with each step building on the data
        collected in previous steps. The intention is for repeated data to be quickly
        identified and skipped to improve overall runtime.
        
        Pipeline steps:
        1. Build season-league URLs - Generates URLs for each league in each season
        2. Populate teams - Extracts team names and IDs from league pages
        3. Build team URLs - Creates URLs for each team's season page
        4. Extract player URLs - Collects player profile links from team pages
        5. Populate player details - Scrapes detailed player information
        6. Build fixture URLs - Creates URLs for match schedule pages
        7. Get fixture tables - Extracts basic match information
        8. Process match details - Collects comprehensive match statistics
        """
        
        print("\n=== Starting FBref Scraping Pipeline ===")
        
        # Step 1: Generate URLs for all season-league combinations
        # Format: https://fbref.com/en/comps/<league_id>/<season>/<season>-<league>-Stats
        # This function returns all URLs needed for the next step
        urls = build_season_urls()
        print(f"build_season_urls(): {len(urls)} urls generated")

        # Step 2: For each season-league URL, extract teams and their unique IDs
        # Populates the Team and ClubSeason models with team names, IDs, and league relationships
        # Skips URLs where we already have the expected number of teams
        populate_team_data()

        # Step 3: Generate team-specific URLs for player data collection
        # Uses the populated Team and ClubSeason information to build URLs for each team's season page
        # Format: https://fbref.com/en/squads/<team_id>/<season>/<team_name>-Stats
        team_urls = build_team_urls()

        # Step 4: From each team URL, extract player profile links
        # Creates Player records with names and URLs, to be populated with details later
        # Avoids duplicate players by checking URLs against the database
        extract_player_urls()

        # Step 5: For each player URL, collect detailed player information
        # Scrapes player position, physical attributes, nationality, and demographics
        # Updates existing Player records with the new information
        populate_player_details()

        # Step 6: Build fixture URLs for match data collection
        # Format: https://fbref.com/en/comps/<league_id>/<season>/schedule/<season>-<league>-Scores-and-Fixtures
        fixture_urls = build_fixture_urls()

        # Step 7: Collect match basic information (dates, teams, scores)
        # Populates the Match model with basic match data including dates, teams, scores, and venues
        # Also extracts match detail URLs for the next step
        get_fixture_tables()

        # Step 8: Process match detail pages to extract comprehensive statistics
        # Collects shots, team stats, and player performance data for each match
        # Skips matches that already have complete data
        process_all_matches()
        
        print("\n=== FBref Scraping Pipeline Complete ===")