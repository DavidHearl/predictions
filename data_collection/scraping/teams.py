import requests
import re
import time

from bs4 import BeautifulSoup
from collections import Counter
from data_collection.models import *
from urllib.parse import quote


# Define Global Variables
SLEEP_TIME = 3.75 # Max requests 20 times per min
        

def build_season_urls():
    """
    Constructs FBref URLs for all Seasons and Leagues in the database.
    Returns a list of URLs for all season-league combinations.
    """
    seasons = Season.objects.all()
    leagues = League.objects.all()
    
    urls = []
    
    for season in seasons:
        for league in leagues:
            # Replaces spaces in the league name with hyphens
            league_slug = league.name.replace(" ", "-")
            season_str = season.name
            league_id = league.league_id
            
            url = f"https://fbref.com/en/comps/{league_id}/{season_str}/{season_str}-{league_slug}-Stats"
            urls.append(url)

    return urls


def populate_team_data():
    """
    Scrapes team IDs and names from each season-league page.
    Inserts valid Team and ClubSeason records into the database.
    Only processes URLs where teams are missing from the database.
    """
    print("\n=== Starting Team Data Population ===")
    urls = build_season_urls()

    skipped_urls = 0
    processed_urls = 0
    total_new_teams = 0
    total_new_club_seasons = 0

    total_urls = len(urls)
    print(f"Processing {total_urls} season-league URLs...\n")

    for i, url in enumerate(urls, 1):
        try:
            # Extract season name from URL
            season_match = re.search(r"/(\d{4}-\d{4})/", url)
            if not season_match:
                print(f"[{i}/{total_urls}] Skipped – could not extract season from URL: {url}")
                skipped_urls += 1
                continue
            season_name = season_match.group(1)

            try:
                season_obj = Season.objects.get(name=season_name)
            except Season.DoesNotExist:
                print(f"[{i}/{total_urls}] Skipped – season '{season_name}' not found in database")
                skipped_urls += 1
                continue

            # Extract league object
            league_obj = None
            for league in League.objects.all():
                if league.name.replace(" ", "-") in url:
                    league_obj = league
                    break
            if not league_obj:
                print(f"[{i}/{total_urls}] Skipped – league not found in URL: {url}")
                skipped_urls += 1
                continue

            # Check if we already have all teams for this season-league
            existing_count = ClubSeason.objects.filter(
                season=season_obj,
                league=league_obj
            ).count()

            if existing_count >= league_obj.number_of_teams:
                print(f"[{i}/{total_urls}] Skipped – already has {existing_count}/{league_obj.number_of_teams} teams for {league_obj.name} {season_name}")
                skipped_urls += 1
                continue

            # If we're here, we need to process this URL
            processed_urls += 1
            print(f"[{i}/{total_urls}] Processing: {season_name} {league_obj.name}")

            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")

            team_data = []
            seen_ids = set()

            for a in soup.find_all("a", href=True):
                if len(team_data) >= league_obj.number_of_teams:
                    break

                href = a["href"]
                if href.startswith("/en/squads/") and "Stats" in href:
                    parts = href.strip("/").split("/")
                    if len(parts) >= 5:
                        team_id = parts[2]
                        team_name = parts[4].replace("-Stats", "").replace("-", " ")

                        if team_id in seen_ids:
                            continue

                        seen_ids.add(team_id)
                        team_data.append((team_id, team_name))

            if not team_data:
                print(f"[{i}/{total_urls}] Warning – No teams found on page for {season_name} {league_obj.name}")
                continue

            new_teams = 0
            new_club_seasons = 0

            for team_id, team_name in team_data:
                team_obj, team_created = Team.objects.get_or_create(
                    unique_code=team_id,
                    defaults={"name": team_name}
                )
                if team_created:
                    new_teams += 1

                club_season, season_created = ClubSeason.objects.get_or_create(
                    team=team_obj,
                    season=season_obj,
                    league=league_obj
                )
                if season_created:
                    new_club_seasons += 1
                    total_new_club_seasons += 1

            total_new_teams += new_teams

            print(f"[{i}/{total_urls}] {season_name} {league_obj.name}: {new_teams} new teams, {new_club_seasons} new club-season entries")

        except Exception as e:
            print(f"[{i}/{total_urls}] Error processing {url}: {e}")
            continue

        time.sleep(SLEEP_TIME)

    # Final summary
    print(f"\n=== Team Data Population Complete ===")
    print(f"- URLs skipped: {skipped_urls}")
    print(f"- URLs processed: {processed_urls}")
    print(f"- Total new Team objects added: {total_new_teams}")
    print(f"- Total new ClubSeason entries added: {total_new_club_seasons}")
