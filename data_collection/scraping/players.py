import requests
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from collections import Counter
from data_collection.models import *
from urllib.parse import quote
from django.db import transaction


SLEEP_TIME = 3.75  # Max requests 20 times per min


def build_team_urls():
    """
    Returns a list of FBref team URLs (one per team-season).
    Format: https://fbref.com/en/squads/{team_id}/{season}/{team_name}-Stats
    """
    print("\n=== Building Team URLs ===")
    urls = []
    
    club_seasons = ClubSeason.objects.select_related("team", "season")
    total = club_seasons.count()
    
    print(f"Found {total} club-season combinations in database")

    for cs in club_seasons:
        if not cs.team.unique_code:
            print(f"  - Skipping {cs.team.name} ({cs.season.name}): missing team code")
            continue
            
        team_id = cs.team.unique_code
        team_name_slug = cs.team.name.replace(" ", "-")
        season_str = cs.season.name

        url = f"https://fbref.com/en/squads/{team_id}/{season_str}/{team_name_slug}-Stats"
        urls.append(url)

    print(f"Generated {len(urls)} team URLs\n")
    return urls


def extract_player_urls(limit=None):
    """
    Builds FBref team URLs and extracts player profile URLs from each team season page.
    Adds players to the database only if they do not already exist.
    """
    print("\n=== Extracting Player URLs ===")

    team_urls = build_team_urls()
    if limit:
        team_urls = team_urls[:limit]
        print(f"Limiting scrape to first {limit} team URLs\n")

    existing_player_urls = set(
        Player.objects.exclude(player_url__isnull=True).values_list("player_url", flat=True)
    )

    print(f"Found {len(existing_player_urls)} existing player URLs in database")
    print(f"Processing {len(team_urls)} team season pages...\n")

    new_players_added = 0
    processed_urls = 0
    seen_urls = set()
    failed_requests = []

    for i, team_url in enumerate(team_urls, 1):
        print(f"[{i}/{len(team_urls)}] Requesting: {team_url}")

        try:
            response = requests.get(team_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
        except Exception as e:
            print(f"  - Failed: {str(e).splitlines()[0]}")
            failed_requests.append((i, team_url, str(e)))
            continue

        time.sleep(SLEEP_TIME)

        player_links = []
        for tag in soup.find_all(['a', 'h2']):
            if tag.name == 'h2' and 'Premier League, Premier League' in tag.text:
                break
            if tag.name == 'a':
                href = tag.get('href', '')
                if re.match(r"^/en/players/[a-zA-Z0-9]{8}/[^/]+$", href):
                    full_url = f"https://fbref.com{href}"
                    if full_url not in seen_urls and full_url not in existing_player_urls:
                        player_links.append(full_url)
                        seen_urls.add(full_url)

        new_links = len(player_links)
        processed_urls += 1
        new_players_added += new_links

        if new_links > 0:
            print(f"  - Added {new_links} new player profiles")
        else:
            print(f"  - No new profiles found")

        with transaction.atomic():
            for url in player_links:
                name = url.rstrip('/').split('/')[-1].replace('-', ' ')
                Player.objects.update_or_create(
                    player_url=url,
                    defaults={'name': name}
                )

        if i % 50 == 0 or i == len(team_urls):
            print(f"\n--- Progress: {i}/{len(team_urls)} teams scraped, {new_players_added} new players total ---\n")

    print(f"\n=== Player URL Extraction Complete ===")
    print(f"- Teams processed: {processed_urls}")
    print(f"- Total new player profiles added: {new_players_added}")

    if failed_requests:
        print(f"\n{len(failed_requests)} failed requests:")
        for i, url, error in failed_requests[:5]:
            print(f"  [{i}] {url} – {error.splitlines()[0]}")
        if len(failed_requests) > 5:
            print(f"  ...and {len(failed_requests) - 5} more")


def populate_player_details():
    """
    Iterates through players in the database with URLs but missing detailed information.
    Scrapes position, footed, height, weight, birth date, and nationality.
    """
    print("\n=== Populating Player Details ===")

    players = Player.objects.filter(
        player_url__isnull=False
    ).filter(
        models.Q(unique_code__isnull=True) | 
        models.Q(position__isnull=True) |
        models.Q(footed__isnull=True) |
        models.Q(height__isnull=True) |
        models.Q(weight__isnull=True) |
        models.Q(birth_date__isnull=True) |
        models.Q(nationality__isnull=True)
    )

    total_players = players.count()
    print(f"Found {total_players} players needing additional details\n")

    updated_players = 0
    already_complete = 0

    for index, player in enumerate(players, 1):
        print(f"[{index}/{total_players}] Scraping: {player.name}")

        try:
            response = requests.get(player.player_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"  - Failed to fetch page: {e}")
            time.sleep(SLEEP_TIME)
            continue

        time.sleep(SLEEP_TIME)

        match = re.search(r"/en/players/([a-zA-Z0-9]{8})/", player.player_url)
        unique_code = match.group(1) if match else player.unique_code

        # Preserve existing data where possible
        position = player.position
        footed = player.footed
        height = player.height
        weight = player.weight
        birth_date = player.birth_date
        nationality = player.nationality

        changes_made = False
        meta = soup.find("div", id="meta")
        if meta:
            for p in meta.find_all("p"):
                text = p.get_text(" ", strip=True)

                if text.startswith("Position:") and not position:
                    position = text.replace("Position:", "").strip()
                    changes_made = True

                elif "cm" in text and "kg" in text:
                    match = re.search(r"(\d{3})cm.*?(\d{2,3})kg", text)
                    if match:
                        if not height:
                            height = float(match.group(1))
                            changes_made = True
                        if not weight:
                            weight = float(match.group(2))
                            changes_made = True

                elif "Born:" in text and not birth_date:
                    match = re.search(r"Born:\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})", text)
                    if match:
                        try:
                            birth_date = datetime.strptime(match.group(1).replace(",", ""), "%B %d %Y").date()
                            changes_made = True
                        except ValueError:
                            pass

                elif ("Citizenship:" in text or "National Team:" in text) and not nationality:
                    link = p.find("a")
                    if link:
                        nationality = link.text.strip()
                        changes_made = True

                elif "Footed:" in text and not footed:
                    if "right" in text.lower():
                        footed = "right"
                        changes_made = True
                    elif "left" in text.lower():
                        footed = "left"
                        changes_made = True
                    elif "both" in text.lower():
                        footed = "both"
                        changes_made = True

        if changes_made or unique_code != player.unique_code:
            Player.objects.filter(id=player.id).update(
                unique_code=unique_code,
                position=position,
                footed=footed,
                height=height,
                weight=weight,
                birth_date=birth_date,
                nationality=nationality
            )
            print(f"  - Updated player information")
            updated_players += 1
        else:
            print(f"  - No new information found")
            already_complete += 1

        if index % 10 == 0 or index == total_players:
            print(f"\n--- Progress Summary ({index}/{total_players}) ---")
            print(f"- Players updated: {updated_players}")
            print(f"- Players already complete: {already_complete}\n")

    print(f"\n=== Player Details Population Complete ===")
    print(f"- Total players processed: {total_players}")
    print(f"- Players updated: {updated_players}")
    print(f"- Players already complete: {already_complete}\n")


# USED TO DOWNLOAD A PLAYERS PAGE TO PARSE THE SRTUCTURE. A URL IS REQUIRED TO RUN.
# NOT REQUIRED IN MAIN FUNCTION 

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