import requests
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from collections import Counter
from data_collection.models import *
from urllib.parse import quote
from django.db import transaction


SLEEP_TIME = 3.1  # Max requests 20 times per min


def build_team_urls():
    """
    Returns a list of FBref team URLs (one per team-season).
    Format: https://fbref.com/en/squads/{team_id}/{season}/{team_name}-Stats
    """
    urls = []

    club_seasons = ClubSeason.objects.select_related("team", "season")

    for cs in club_seasons:
        team_id = cs.team.unique_code
        team_name_slug = cs.team.name.replace(" ", "-")
        season_str = cs.season.name

        url = f"https://fbref.com/en/squads/{team_id}/{season_str}/{team_name_slug}-Stats"
        urls.append(url)

    for url in urls:
        print(url)

    return urls


def extract_player_urls():
    """
    Builds FBref team URLs and extracts player profile URLs from each team season page.
    Stops collecting links after encountering the 'Premier League, Premier League' <h2> tag,
    which marks the start of unrelated content.
    Adds players to the database only if they do not already exist.
    """

    # Build team URLs
    team_urls = []
    club_seasons = ClubSeason.objects.select_related("team", "season")
    for cs in club_seasons:
        team_id = cs.team.unique_code
        team_name_slug = cs.team.name.replace(" ", "-")
        season_str = cs.season.name
        url = f"https://fbref.com/en/squads/{team_id}/{season_str}/{team_name_slug}-Stats"
        team_urls.append(url)

    print(f"Found {len(team_urls)} team season URLs.")

    seen_urls = set()

    for team_url in team_urls:
        print(f"\nScraping players from: {team_url}")
        try:
            response = requests.get(team_url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            time.sleep(SLEEP_TIME)
        except Exception as e:
            print(f"Request failed: {e}")
            continue

        player_links = []
        for tag in soup.find_all(['a', 'h2']):
            if tag.name == 'h2' and 'Premier League, Premier League' in tag.text:
                break
            if tag.name == 'a':
                href = tag.get('href', '')
                if re.match(r"^/en/players/[a-zA-Z0-9]{8}/[^/]+$", href):
                    full_url = f"https://fbref.com{href}"
                    if full_url not in seen_urls:
                        player_links.append(full_url)
                        seen_urls.add(full_url)

        print(f"Found {len(player_links)} unique player profiles:")
        for url in player_links:
            print(f" - {url}")

        with transaction.atomic():
            for url in player_links:
                name = url.rstrip('/').split('/')[-1].replace('-', ' ')
                Player.objects.update_or_create(
                    player_url=url,
                    defaults={'name': name}
                )

# USED TO DOWNLOAD A PLAYERS PAGE TO PARSE THE SRTUCTURE. A URL IS REQUIRED TO RUN.
# def download_player_html(player_url, filename="player.html", retries=3, delay=5):
#     """
#     Downloads raw HTML for a player page with retries on timeout errors.

#     Args:
#         player_url (str): Full FBref player URL
#         filename (str): Name to save the HTML file as
#         retries (int): Number of retries on failure
#         delay (int): Delay in seconds between retries
#     """
#     for attempt in range(1, retries + 1):
#         try:
#             print(f"Downloading player page: {player_url} (Attempt {attempt})")
#             response = requests.get(player_url, timeout=20)
#             response.raise_for_status()

#             with open(filename, "w", encoding="utf-8") as f:
#                 f.write(response.text)

#             print(f" - Saved HTML to {filename}")
#             return

#         except requests.exceptions.Timeout:
#             print(" - Timeout. Retrying...")
#             sleep(delay)

#         except Exception as e:
#             print(f" - Error downloading page: {e}")
#             break

#     print(f" - Failed to download page after {retries} attempts.")


def populate_player_details():
    players = Player.objects.filter(player_url__isnull=False)
    print(f"Checking {players.count()} players...\n")

    for index, player in enumerate(players, start=1):
        if all([
            player.unique_code,
            player.position,
            player.footed,
            player.height,
            player.weight,
            player.birth_date,
            player.nationality
        ]):
            continue

        print(f"[{index}/{players.count()}] Scraping: {player.name} -> {player.player_url}")

        try:
            response = requests.get(player.player_url, timeout=15)
            html = response.text  # Save HTML as string
            # Optional debug save:
            # with open("player_debug.html", "w", encoding="utf-8") as f:
            #     f.write(html)

            soup = BeautifulSoup(html, "html.parser")

        except Exception as e:
            print(f"Failed to fetch page for {player.name}: {e}")
            time.sleep(SLEEP_TIME)
            continue

        # Extract unique_code from player_url
        match = re.search(r"/en/players/([a-zA-Z0-9]{8})/", player.player_url)
        unique_code = match.group(1) if match else player.unique_code

        # Initial fallback values
        position = player.position
        footed = player.footed
        height = player.height
        weight = player.weight
        birth_date = player.birth_date
        nationality = player.nationality

        meta = soup.find("div", id="meta")
        if meta:
            text_blocks = meta.find_all("p")

            for p in text_blocks:
                text = p.get_text(" ", strip=True)

                # Position (if available)
                if text.startswith("Position:"):
                    position = text.replace("Position:", "").strip()

                # Height and weight
                elif "cm" in text and "kg" in text:
                    match = re.search(r"(\d{3})cm.*?(\d{2,3})kg", text)
                    if match:
                        height = float(match.group(1))
                        weight = float(match.group(2))

                # Birth date
                elif "Born:" in text and birth_date is None:
                    match = re.search(r"Born:\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})", text)
                    if match:
                        try:
                            birth_date = datetime.strptime(match.group(1).replace(",", ""), "%B %d %Y").date()
                        except ValueError:
                            pass

                # Nationality
                elif ("Citizenship:" in text or "National Team:" in text) and nationality is None:
                    link = p.find("a")
                    if link:
                        nationality = link.text.strip()

        # Save if anything was updated
        Player.objects.filter(id=player.id).update(
            unique_code=unique_code,
            position=position,
            footed=footed,
            height=height,
            weight=weight,
            birth_date=birth_date,
            nationality=nationality
        )

        time.sleep(SLEEP_TIME)