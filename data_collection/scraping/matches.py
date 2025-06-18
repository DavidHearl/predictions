import requests
import time
import re

from bs4 import BeautifulSoup, Comment
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from data_collection.models import *


SLEEP_TIME = 3.5  # Max requests 20 times per min


def build_fixture_urls():
    """
    Constructs FBref fixture URLs for each season-league combination in the database.
    Only returns raw URLs as strings.
    """
    urls = []
    seasons = Season.objects.all()
    leagues = League.objects.all()

    for season in seasons:
        for league in leagues:
            league_slug = league.name.replace(" ", "-")
            season_str = season.name
            league_id = league.league_id

            url = (
                f"https://fbref.com/en/comps/{league_id}/{season_str}/schedule/"
                f"{season_str}-{league_slug}-Scores-and-Fixtures"
            )
            urls.append(url)

    # for url in urls:
    #     print(url)

    return urls


def normalize_team_name(name):
    """
    Clean and standardize scraped team names for matching DB entries.
    """
    name = name.strip()
    name = name.replace("Utd", "United")
    name = name.replace("Nott'ham", "Nottingham")
    name = name.replace("Spurs", "Tottenham")
    name = name.replace("Man ", "Manchester ")  # catch things like 'Man Utd' just in case
    return name


def extract_team_name_from_href(td):
    """
    Extract clean team name from the <a href="/en/squads/..."> tag inside a cell.
    Converts "Newcastle-United-Stats" to "Newcastle United".
    """
    try:
        href = td.find("a")["href"]  # e.g. /en/squads/b2b47a98/2023-2024/Newcastle-United-Stats
        team_slug = href.strip("/").split("/")[-1]  # Newcastle-United-Stats
        clean_name = team_slug.replace("-Stats", "").replace("-", " ")
        return clean_name
    except Exception:
        return None


def get_fixture_tables():
    """
    Loops through all fixture URLs, extracts season/league from URL, and stores all matches to DB.
    """
    urls = build_fixture_urls()
    total_inserted = 0
    total_skipped = 0

    for url in urls:
        print(f"Fetching: {url}")
        time.sleep(SLEEP_TIME)

        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract identifiers from URL
            parts = url.split("/")
            league_id = int(parts[5])
            season_name = parts[6]

            try:
                season = Season.objects.get(name=season_name)
                league = League.objects.get(league_id=league_id)
            except (Season.DoesNotExist, League.DoesNotExist):
                print(f" - Skipping: missing Season or League ({season_name}, {league_id})")
                continue

            # Find schedule table
            table = soup.find("table", id=lambda x: x and x.startswith("sched_") and season_name in x)
            if not table:
                print(" - No table found")
                continue

            rows = table.find("tbody").find_all("tr")
            count = 0

            for row in rows:
                if row.get("class") and "thead" in row.get("class"):
                    continue

                date_cell = row.find("td", {"data-stat": "date"})
                if not date_cell or not date_cell.text.strip():
                    continue

                try:
                    naive_date = datetime.strptime(date_cell.text.strip(), "%Y-%m-%d")
                    date = timezone.make_aware(naive_date)
                except ValueError:
                    continue

                home_team = extract_team_name_from_href(row.find("td", {"data-stat": "home_team"}))
                away_team = extract_team_name_from_href(row.find("td", {"data-stat": "away_team"}))
                if not home_team or not away_team:
                    total_skipped += 1
                    continue

                score_text = row.find("td", {"data-stat": "score"}).text.strip()
                home_score, away_score = (None, None)
                if "–" in score_text:
                    try:
                        home_score, away_score = map(int, score_text.split("–"))
                    except ValueError:
                        pass

                attendance = row.find("td", {"data-stat": "attendance"})
                attendance = int(attendance.text.replace(",", "")) if attendance and attendance.text else None

                venue = row.find("td", {"data-stat": "venue"})
                venue = venue.text.strip() if venue else ""

                referee = row.find("td", {"data-stat": "referee"})
                referee = referee.text.strip() if referee else ""

                match_link = row.find("td", {"data-stat": "match_report"}).find("a")
                match_url = f"https://fbref.com{match_link['href']}" if match_link else None

                try:
                    home_team_obj = Team.objects.get(name=home_team)
                    away_team_obj = Team.objects.get(name=away_team)
                except Team.DoesNotExist:
                    print(f" - Skipping match: team not found - {home_team} vs {away_team}")
                    total_skipped += 1
                    continue

                Match.objects.update_or_create(
                    match_url=match_url,
                    defaults={
                        "date": date,
                        "home_team": home_team_obj,
                        "away_team": away_team_obj,
                        "season": season,
                        "league": league,
                        "attendance": attendance,
                        "venue": venue,
                        "referee": referee,
                        "home_score": home_score,
                        "away_score": away_score
                    }
                )

                count += 1

            print(f" - Inserted or updated {count} matches")
            total_inserted += count

        except Exception as e:
            print(f" - Error processing {url}: {e}")

    print(f"\nCompleted.\n - Matches added/updated: {total_inserted}\n - Matches skipped (teams not found or broken rows): {total_skipped}")