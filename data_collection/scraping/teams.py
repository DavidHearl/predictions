import requests
import re
import time

from bs4 import BeautifulSoup
from collections import Counter
from data_collection.models import *
from urllib.parse import quote


# Define Global Variables
SLEEP_TIME = 3.5 # Max requests 20 times per min
        

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
    Only first 20 valid team links per season are processed.
    """
    urls = build_season_urls()

    for url in urls:
        print(f"Scraping teams from {url}")
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract season name from URL
            season_match = re.search(r"/(\d{4}-\d{4})/", url)
            if not season_match:
                print(f"Could not extract season from URL: {url}")
                continue
            season_name = season_match.group(1)

            try:
                season_obj = Season.objects.get(name=season_name)
            except Season.DoesNotExist:
                print(f"Season {season_name} not found in database.")
                continue

            # Extract league object
            league_obj = None
            for league in League.objects.all():
                if league.name.replace(" ", "-") in url:
                    league_obj = league
                    break
            if not league_obj:
                print(f"League not found for URL: {url}")
                continue

            team_data = []
            seen_ids = set()

            # Parse up to 20 unique team links
            for a in soup.find_all("a", href=True):
                if len(team_data) >= 20:
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

            # Insert into DB
            for team_id, team_name in team_data:
                team_obj, _ = Team.objects.get_or_create(
                    unqiue_code=team_id,
                    defaults={"name": team_name}
                )
                ClubSeason.objects.get_or_create(
                    team=team_obj,
                    season=season_obj,
                    league=league_obj
                )

                print(f"Added: {team_name} ({team_id}) for {season_name}")

        except Exception as e:
            print(f"Failed to scrape {url}: {e}")

        time.sleep(SLEEP_TIME)
