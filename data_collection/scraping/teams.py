import requests
import re
from bs4 import BeautifulSoup
from collections import Counter
from data_collection.models import *
import time


# Define Global Variables
SLEEP_TIME = 2 # Max requests 20 times per min
        

def build_fbref_urls():
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


def get_teams():
    """
    Builds all FBref season/league URLs, scrapes each for team links,
    deduplicates them, and returns only links that contain a season format (YYYY-YYYY).
    """
    # Retrieve URLs from the previous function
    urls = build_fbref_urls()

    all_team_links = []

    for url in urls:
        print(f"Scraping teams from {url}")
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/en/squads/") and "Stats" in href:
                    full_url = f"https://fbref.com{href}"
                    all_team_links.append(full_url)
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")

        time.sleep(SLEEP_TIME)
        
    # Filter for links containing a season format (YYYY-YYYY)
    season_links = [link for link in all_team_links if re.search(r"/\d{4}-\d{4}/", link)]

    # Deduplicate links
    unique_links = list(set(season_links))
    parsed_teams = []

    for link in unique_links:
        parts = link.strip('/').split('/')
        if len(parts) >= 8 and parts[4] == 'squads':
            team_id = parts[5]
            team_name = parts[7].replace('-Stats', '')
            parsed_teams.append([team_id, team_name])

    
    for item in parsed_teams:
        print(item)

    return parsed_teams
