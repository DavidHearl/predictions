import requests
from bs4 import BeautifulSoup
from collections import Counter
from data_collection.models import *


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
            
            # Note: You should ideally have fbref_id as a field in your League model
            # This is a fallback assuming Premier League has ID 9
            if hasattr(league, 'fbref_id'):
                league_id = league.fbref_id
            else:
                # Hardcoded league ID - consider adding fbref_id field to League model
                league_id = 9  # This assumes Premier League, might not work for other leagues
            
            url = f"https://fbref.com/en/comps/{league_id}/{season_str}/{season_str}-{league_slug}-Stats"
            urls.append(url)
    
    return urls



# def get_teams(url="https://fbref.com/en/comps/9/2023-2024/2023-2024-Premier-League-Stats"):
#     print(f"Scraping teams from {url}")

#     response = requests.get(url)
#     soup = BeautifulSoup(response.content, "html.parser")

#     team_links = []

#     for a in soup.find_all("a", href=True):
#         href = a["href"]
#         if href.startswith("/en/squads/") and "Stats" in href:
#             full_url = f"https://fbref.com{href}"
#             team_links.append(full_url)

#     print(f"\n Found {len(team_links)} raw team links.")

#     # Deduplication
#     link_counts = Counter(team_links)
#     duplicates = {url: count for url, count in link_counts.items() if count > 1}

#     if duplicates:
#         print("\n Duplicate links:")
#         for url, count in duplicates.items():
#             print(f" - {url} ({count} times)")

#     unique_links = list(set(team_links))
#     print(f"\n {len(unique_links)} unique team links.")

#     return unique_links
