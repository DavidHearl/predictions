import requests
import time
import re
import os

from bs4 import BeautifulSoup, Comment, NavigableString
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from data_collection.models import *
from pathlib import Path


SLEEP_TIME = 3.75  # Max requests 20 times per min


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


# USED TO DOWNLOAD A MATCH PAGE TO PARSE THE SRTUCTURE. A URL IS REQUIRED TO RUN.
# def download_match_html(match_url, match_id=None, save_dir="html_matches"):
#     """
#     Downloads the full HTML of an FBref match page and saves it locally.

#     Args:
#         match_url (str): The full URL of the FBref match page.
#         match_id (str): Optional. A unique identifier (e.g., from the URL) for filename.
#         save_dir (str): Directory to save the HTML files.
    
#     Returns:
#         str: Path to the saved HTML file.
#     """
#     try:
#         print(f"Downloading: {match_url}")
#         response = requests.get(match_url, timeout=15)
#         response.raise_for_status()

#         Path(save_dir).mkdir(parents=True, exist_ok=True)

#         if not match_id:
#             match_id = match_url.rstrip('/').split('/')[-1]

#         file_path = os.path.join(save_dir, f"{match_id}.html")
#         with open(file_path, "w", encoding="utf-8") as f:
#             f.write(response.text)

#         print(f"Saved to {file_path}")
#         return file_path

#     except Exception as e:
#         print(f"Failed to download {match_url}: {e}")
#         return None


def process_all_matches():
    matches = Match.objects.exclude(match_url__isnull=True).exclude(match_url="").order_by("date")
    total = matches.count()

    for i, match in enumerate(matches, start=1):
        print(f"\n[{i} / {total}] Fetching: {match.match_url}")
        time.sleep(SLEEP_TIME)

        try:
            response = requests.get(match.match_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            extract_match_shots(soup, match)
            extract_match_team_stats(soup, match)
            extract_match_player_stats(soup, match)

            print(f"Match {match.id} processed.")

        except Exception as e:
            print(f"Error processing match {match.id}: {e}")


def safe_int(val):
    try:
        return int(val)
    except:
        return None


def safe_float(val):
    try:
        return float(val.strip('%'))
    except:
        return None


def parse_minute(minute_str):
    if not minute_str:
        return None
    try:
        if "+" in minute_str:
            base, extra = minute_str.split("+")
            return int(base) + int(extra)
        return int(minute_str)
    except ValueError:
        return None


def extract_match_shots(soup, match):
    table = soup.find("table", id="shots_all")
    if not table:
        print(f"No 'shots_all' table found for match {match.id}")
        return

    # Exit early if shots are already present
    if MatchShot.objects.filter(match=match).exists():
        print(f"Shots already recorded for match {match.id}, skipping.")
        return

    for row in table.find("tbody").find_all("tr"):
        if "class" in row.attrs and "thead" in row["class"]:
            continue

        def get_href_identifier(stat):
            cell = row.find("td", {"data-stat": stat})
            if not cell:
                return None
            a = cell.find("a")
            if not a or not a.get("href"):
                return None
            return a["href"]

        def extract_player(href):
            if not href:
                return None
            code = href.split("/")[3]  # /en/players/<code>/<name>
            return Player.objects.filter(unique_code=code).first()

        def extract_team(href):
            if not href:
                return None
            match = re.search(r"/squads/([\w\d]+)/", href)
            if not match:
                return None
            team_code = match.group(1)
            return Team.objects.filter(unique_code=team_code).first()

        player_href = get_href_identifier("player")
        assister_href = get_href_identifier("sca_1_player")
        team_href = get_href_identifier("team")

        player = extract_player(player_href)
        assister = extract_player(assister_href)
        team = extract_team(team_href)

        if not team:
            print(f"Missing team for row: {team_href}")
            continue

        def get_text(stat):
            el = row.find("td", {"data-stat": stat}) or row.find("th", {"data-stat": stat})
            return el.get_text(strip=True) if el else None

        MatchShot.objects.create(
            match=match,
            team=team,
            player=player,
            minute=parse_minute(get_text("minute")),
            expected_goals=float(get_text("xg_shot")) if get_text("xg_shot") else None,
            post_shot_expected_goals=float(get_text("psxg_shot")) if get_text("psxg_shot") else 0.0,
            outcome=get_text("outcome") or None,
            distance=float(get_text("distance")) if get_text("distance") else None,
            body_part=get_text("body_part") or None,
            is_penalty="penalty" in (get_text("notes") or "").lower(),
            assisted_by=assister
        )


def extract_match_team_stats(soup, match):
    # Get team codes and xG values from scorebox
    team_blocks = soup.find_all("div", class_="scorebox")[0].find_all("div", recursive=False)
    team_data = []
    for block in team_blocks:
        a_tag = block.find("a", href=re.compile(r"/en/squads/"))
        xg_tag = block.find("div", class_="score_xg")
        if a_tag and xg_tag:
            href = a_tag.get("href", "")
            match_code = re.search(r"/squads/([\w\d]+)/", href)
            if match_code:
                team_code = match_code.group(1)
                team = Team.objects.filter(unique_code=team_code).first()
                xg = float(xg_tag.text.strip())
                team_data.append((team, xg))
    if len(team_data) != 2:
        print("Could not extract both teams or xG data.")
        return

    # Main stats table
    stats_table = soup.find("div", id="team_stats")
    stat_rows = stats_table.find_all("tr") if stats_table else []

    # Helper to find the index of a row header
    def get_row_index(label):
        for i, row in enumerate(stat_rows):
            th = row.find("th")
            if th and th.get_text(strip=True) == label:
                return i + 1  # data row is right after header row
        return None

    val_row_shots = get_row_index("Shots on Target")
    val_row_saves = get_row_index("Saves")
    val_row_possession = get_row_index("Possession")
    val_row_passing = get_row_index("Passing Accuracy")

    extra_stats = {}
    extra_block = soup.find("div", id="team_stats_extra")
    if extra_block:
        for group in extra_block.find_all("div", recursive=False):
            divs = group.find_all("div")
            for i in range(3, len(divs), 3):
                home_val = divs[i].text.strip()
                stat = divs[i + 1].text.strip()
                away_val = divs[i + 2].text.strip()
                extra_stats[stat] = (home_val, away_val)

    for i, (team, xg) in enumerate(team_data):
        if not team:
            continue
        side = 0 if i == 0 else 1  # home: 0, away: 1

        # Possession
        possession = None
        if val_row_possession is not None and val_row_possession < len(stat_rows):
            tds = stat_rows[val_row_possession].find_all("td")
            if len(tds) > side:
                perc = tds[side].find("strong")
                if perc:
                    possession = safe_float(perc.text.strip())

        # Passing Accuracy
        passing_accuracy = None
        if val_row_passing is not None and val_row_passing < len(stat_rows):
            tds = stat_rows[val_row_passing].find_all("td")
            if len(tds) > side:
                percent = re.search(r"(\d+)%", tds[side].get_text())
                if percent:
                    passing_accuracy = float(percent.group(1))

        # Shots on Target
        shots_on_target = None
        total_shots = None
        if val_row_shots is not None and val_row_shots < len(stat_rows):
            tds = stat_rows[val_row_shots].find_all("td")
            if len(tds) > side:
                txt = tds[side].get_text()
                sot_match = re.search(r"(\d+)\s+of\s+(\d+)", txt)
                if sot_match:
                    shots_on_target = int(sot_match.group(1))
                    total_shots = int(sot_match.group(2))

        # Saves
        saves = None
        if val_row_saves is not None and val_row_saves < len(stat_rows):
            tds = stat_rows[val_row_saves].find_all("td")
            if len(tds) > side:
                txt = tds[side].get_text()
                save_match = re.search(r"(\d+)\s+of\s+\d+", txt)
                if save_match:
                    saves = int(save_match.group(1))


        MatchTeamStat.objects.update_or_create(
            match=match,
            team=team,
            defaults={
                "is_home": (side == 0),
                "expected_goals": xg,
                "expected_goals_against": team_data[1 - i][1],
                "possession": possession,
                "passing_accuracy": passing_accuracy,
                "shots_on_target": shots_on_target,
                "total_shots": total_shots,
                "saves": saves,
                "fouls": safe_int(extra_stats.get("Fouls", ("", ""))[side]),
                "corners": safe_int(extra_stats.get("Corners", ("", ""))[side]),
                "crosses": safe_int(extra_stats.get("Crosses", ("", ""))[side]),
                "touches": safe_int(extra_stats.get("Touches", ("", ""))[side]),
                "tackles": safe_int(extra_stats.get("Tackles", ("", ""))[side]),
                "interceptions": safe_int(extra_stats.get("Interceptions", ("", ""))[side]),
                "aerials_won": safe_int(extra_stats.get("Aerials Won", ("", ""))[side]),
                "clearances": safe_int(extra_stats.get("Clearances", ("", ""))[side]),
                "offsides": safe_int(extra_stats.get("Offsides", ("", ""))[side]),
                "goal_kicks": safe_int(extra_stats.get("Goal Kicks", ("", ""))[side]),
                "throwins": safe_int(extra_stats.get("Throw Ins", ("", ""))[side]),
                "long_balls": safe_int(extra_stats.get("Long Balls", ("", ""))[side]),
            }
        )


def extract_match_player_stats(soup, match):
    all_tables = soup.find_all("table", id=re.compile(
        r"stats_(\w+?)_(summary|passing|passing_types|defense|possession|misc|keepers|keepers_adv)"
    ))

    player_stats = {}

    FIELD_MAP = {
        # Summary
        "summary__minutes": "minutes_played",
        "summary__goals": "goals",
        "summary__assists": "assists",
        "summary__shots": "shots",
        "summary__shots_on_target": "shots_on_target",
        "summary__xg": "expected_goals",
        "summary__npxg": "non_penalty_expected_goals",
        "summary__xg_assist": "expected_assists",
        "summary__sca": "shot_creation_actions",
        "summary__gca": "goal_creation_actions",
        "summary__cards_yellow": "yellow_cards",
        "summary__cards_red": "red_cards",
        "summary__pens_made": "penalty_kicks_made",
        "summary__pens_att": "penalty_kicks_attempted",
        "summary__tackles": "tackles",
        "summary__touches": "touches",
        "summary__interceptions": "interceptions",

        # Passing
        "passing__passes_completed": "passes_completed",
        "passing__passes": "passes_attempted",
        "passing__passes_pct": "pass_completion_percentage",
        "passing__passes_total_distance": "total_passing_distance",
        "passing__passes_progressive_distance": "total_progressive_distance",
        "passing__progressive_passes": "progressive_passes",
        "passing__passes_into_final_third": "passes_into_final_third",
        "passing__passes_into_penalty_area": "passes_into_penalty_area",
        "passing__crosses_into_penalty_area": "crosses_into_penalty_area",
        "passing__key_passes": "key_passes",
        "passing__assisted_shots": "key_passes",
        "passing__passes_completed_short": "short_passes_completed",
        "passing__passes_short": "short_passes_attempted",
        "passing__passes_pct_short": "short_passes_percentage",
        "passing__passes_completed_medium": "medium_passes_completed",
        "passing__passes_medium": "medium_passes_attempted",
        "passing__passes_pct_medium": "medium_passes_percentage",
        "passing__passes_completed_long": "long_passes_completed",
        "passing__passes_long": "long_passes_attempted",
        "passing__passes_pct_long": "long_passes_percentage",

        # Passing Types
        "passing__key_passes": "key_passes",
        "passing_types__passes_live": "live_passes",
        "passing_types__passes_dead": "dead_passes",
        "passing_types__passes_free_kicks": "free_kicks",
        "passing_types__through_balls": "through_balls",
        "passing_types__passes_switches": "switches",
        "passing_types__crosses": "crosses",
        "passing_types__throw_ins": "throwins",
        "passing_types__corner_kicks": "corners",
        "passing_types__corner_kicks_in": "inswinging_corner_kicks",
        "passing_types__corner_kicks_out": "outswinging_corner_kicks",
        "passing_types__corner_kicks_straight": "straight_corner_kicks",

        # Defense
        "defense__tackles_won": "tackles_won",
        "defense__tackles_def_3rd": "tackles_in_defensive_third",
        "defense__tackles_mid_3rd": "tackles_in_middle_third",
        "defense__tackles_att_3rd": "tackles_in_attacking_third",
        "defense__challenge_tackles": "dribblers_tackled",
        "defense__challenges": "dribbles_challenged",
        "defense__challenge_tackles_pct": "dribble_tackle_percent",
        "defense__blocks": "blocks",
        "defense__blocked_shots": "shots_blocked",
        "defense__blocked_passes": "passes_blocked",
        "defense__interceptions": "interceptions",
        "defense__tackles_interceptions": "tackles_and_interceptions",
        "defense__clearances": "clearances",
        "defense__errors": "errors",

        # Possession
        "possession__touches": "touches",
        "possession__touches_def_pen_area": "touches_in_defensive_penalty",
        "possession__touches_def_3rd": "touches_in_defensive_third",
        "possession__touches_mid_3rd": "touches_in_middle_third",
        "possession__touches_att_3rd": "touches_in_attacking_third",
        "possession__touches_att_pen_area": "touches_in_attacking_penalty",
        "possession__take_ons": "attempted_take_ons",
        "possession__take_ons_won": "successful_take_ons",
        "possession__take_ons_won_pct": "successful_take_on_percentage",
        "possession__take_ons_tackled": "take_ons_tackled",
        "possession__take_ons_tackled_pct": "take_ons_tackled_percentage",
        "possession__carries": "carries",
        "possession__progressive_carries": "progressive_carries",
        "possession__carries_progressive_distance": "total_progressive_distance_carried",
        "possession__carries_distance": "total_distance_carried",
        "possession__carries_into_final_third": "carries_into_attacking_third",
        "possession__carries_into_penalty_area": "carries_into_penalty_area",
        "possession__progressive_passes_received": "progressive_passes_recieved",
        "possession__miscontrols": "miscontrols",
        "possession__dispossessed": "disposessions",
        "possession__passes_received": "passes_recieved",

        # Misc
        "misc__cards_yellow_red": "second_yellow_cards",
        "misc__fouls": "fouls",
        "misc__fouled": "fouls_drawn",
        "misc__offsides": "offsides",
        "misc__pens_won": "penalty_kicks_won",
        "misc__pens_conceded": "penalty_kicks_conceeded",
        "misc__pens_made": "penalty_kicks_made",
        "misc__pens_att": "penalty_kicks_attempted",
        "misc__interceptions": "interceptions",
        "misc__own_goals": "own_goals",
        "misc__ball_recoveries": "balls_recovered",
        "misc__aerials_won": "aerials_won",
        "misc__aerials_lost": "aerials_lost",
        "misc__aerials_won_pct": "aerials_won_percentage",  
        "misc__aerials_won_pct": "aerial_win_percentage",

        # GK Basic
        # "keepers__shots_on_target_against": "gk_shots_on_targets",
        # "keepers__goals_against": "gk_goals_against",
        # "keepers__saves": "gk_saves",
        # "keepers__save_pct": "gk_save_percentage",

        # GK Advanced
        # "keepers_adv__psxg": "gk_post_shot_expected_goals",
        # "keepers_adv__passes_attempted": "gk_passes_attempted",
        # "keepers_adv__throws_attempted": "gk_thows_attempted",
        # "keepers_adv__launch_pct": "gk_launch_percent",
        # "keepers_adv__average_pass_length": "gk_average_pass_length",
        # "keepers_adv__goal_kicks": "gk_goal_kicks_attempted",
        # "keepers_adv__goal_kick_launch_pct": "gk_goal_kick_launch_percent",
        # "keepers_adv__goal_kick_length_avg": "gk_goak_kick_average_length",
        # "keepers_adv__crosses_faced": "gk_crosses_opposed",
        # "keepers_adv__crosses_stopped": "gk_crosses_stopped",
        # "keepers_adv__crosses_stopped_pct": "gk_cross_stop_percentage",
        # "keepers_adv__def_actions_outside_pen_area": "gk_actions_outside_penalty_area",
        # "keepers_adv__avg_distance_def_actions": "gk_average_distance_from_goal",
    }

    all_tables = soup.find_all("table")
    keeper_tables = [t for t in all_tables if t.get("id", "").startswith("keeper_stats_")]
    stat_tables = [t for t in all_tables if re.match(r"stats_(\w+?)_(summary|passing|passing_types|defense|possession|misc)", t.get("id", ""))]

    # Identify GK players by their player codes from keeper tables
    goalkeeper_codes = set()
    for table in keeper_tables:
        for row in table.find("tbody").find_all("tr"):
            player_cell = row.find("th", {"data-stat": "player"})
            if player_cell and player_cell.find("a"):
                href = player_cell.find("a")["href"]
                code = href.split("/")[3]
                goalkeeper_codes.add(code)

    for table in stat_tables:
        match_id = table.get("id")
        match_data = re.match(r"stats_(\w+?)_(\w+)", match_id)
        if not match_data:
            continue
        team_code, category = match_data.groups()
        team = Team.objects.filter(unique_code=team_code).first()
        if not team:
            continue

        for row in table.find("tbody").find_all("tr"):
            if "class" in row.attrs and "thead" in row["class"]:
                continue

            player_cell = row.find("th", {"data-stat": "player"})
            if not player_cell:
                continue

            player_href = player_cell.find("a")["href"] if player_cell.find("a") else None
            player_code = player_href.split("/")[3] if player_href else None
            if not player_code:
                continue

            player = Player.objects.filter(unique_code=player_code).first()
            if not player:
                continue

            stat_obj, created = MatchPlayerStat.objects.get_or_create(match=match, team=team, player=player)

            for cell in row.find_all("td"):
                stat = cell.get("data-stat")
                full_key = f"{category}__{stat}"
                if full_key in FIELD_MAP:
                    text = cell.get_text(strip=True).replace("%", "")
                    if text == "":
                        value = 0
                    else:
                        try:
                            value = float(text) if "." in text else int(text)
                        except ValueError:
                            continue
                    setattr(stat_obj, FIELD_MAP[full_key], value)

            # If player is not a goalkeeper, zero out GK fields
            if player_code not in goalkeeper_codes:
                for field in MatchPlayerStat._meta.fields:
                    if field.name.startswith("gk_"):
                        setattr(stat_obj, field.name, 0)

            stat_obj.save()

    # Now parse keeper stats tables
    GK_FIELD_MAP = {
        "gk_shots_on_target_against": "gk_shots_on_targets",
        "gk_goals_against": "gk_goals_against",
        "gk_saves": "gk_saves",
        "gk_save_pct": "gk_save_percentage",
        "gk_psxg": "gk_post_shot_expected_goals",
        "gk_passes_completed_launched": "gk_launches_completed",
        "gk_passes_launched": "gk_launches_attempted",
        "gk_passes_pct_launched": "gk_launches_completion_percentage",
        "gk_passes": "gk_passes_attempted",
        "gk_passes_throws": "gk_thows_attempted",
        "gk_pct_passes_launched": "gk_launch_percent",
        "gk_passes_length_avg": "gk_average_pass_length",
        "gk_goal_kicks": "gk_goal_kicks_attempted",
        "gk_pct_goal_kicks_launched": "gk_goal_kick_launch_percent",
        "gk_goal_kick_length_avg": "gk_goak_kick_average_length",
        "gk_crosses": "gk_crosses_opposed",
        "gk_crosses_stopped": "gk_crosses_stopped",
        "gk_crosses_stopped_pct": "gk_cross_stop_percentage",
        "gk_def_actions_outside_pen_area": "gk_actions_outside_penalty_area",
        "gk_avg_distance_def_actions": "gk_average_distance_from_goal",
    }

    for table in keeper_tables:
        for row in table.find("tbody").find_all("tr"):
            player_cell = row.find("th", {"data-stat": "player"})
            if not player_cell or not player_cell.find("a"):
                continue
            player_code = player_cell.find("a")["href"].split("/")[3]
            player = Player.objects.filter(unique_code=player_code).first()
            if not player:
                continue

            stat_obj = MatchPlayerStat.objects.filter(match=match, player=player).first()
            if not stat_obj:
                continue

            for cell in row.find_all("td"):
                stat = cell.get("data-stat")
                if stat in GK_FIELD_MAP:
                    text = cell.get_text(strip=True).replace("%", "")
                    if text == "":
                        value = 0
                    else:
                        try:
                            value = float(text) if "." in text else int(text)
                        except ValueError:
                            continue
                    setattr(stat_obj, GK_FIELD_MAP[stat], value)
            stat_obj.save()

    print(f"Finished parsing player stats for match {match.id}")