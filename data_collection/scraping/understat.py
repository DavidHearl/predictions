"""Understat xG importer.

Understat exposes a JSON endpoint per league-season
(https://understat.com/getLeagueData/<slug>/<year>, the same XHR its own pages
use since the 2025 redesign) whose `dates` list holds every match of the season
with home/away xG. One request per league-season gives xG for all played
matches - massively cheaper than scraping per-match pages.

Understat only covers the big five leagues (EPL, La liga, Bundesliga, Serie A,
Ligue 1) plus the RFPL; leagues without an `understat_slug` are skipped.

Understat xG overwrites xG imported from football-data (it is the more widely
used reference model), but matches themselves are never created here - results
come from football-data/fbref first.
"""
import logging

from data_collection.models import Match, MatchTeamStat
from .http import fetch
from .team_names import resolve_team

log = logging.getLogger("scraping.understat")

SOURCE = "understat"
DATA_URL = "https://understat.com/getLeagueData/{slug}/{year}"


def season_to_year(season_name):
    """'2026-2027' -> 2026 (understat identifies seasons by their starting year)."""
    return int(season_name.split("-")[0])


def fetch_league_season(league, season):
    """Return the list of match dicts for a league-season, or None."""
    year = season_to_year(season.name)
    url = DATA_URL.format(slug=league.understat_slug, year=year)
    response = fetch(url, headers={
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://understat.com/league/{league.understat_slug}/{year}",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })
    if response is None:
        log.warning("Could not fetch %s", url)
        return None
    try:
        payload = response.json()
    except ValueError:
        log.warning("Non-JSON response from %s (endpoint changed again?)", url)
        return None
    return payload.get("dates") or []


def import_league_season_xg(league, season):
    """Fetch understat xG for one league-season and merge into MatchTeamStat.
    Returns (updated, missing) counts."""
    if not league.understat_slug:
        return (0, 0)

    entries = fetch_league_season(league, season)
    if entries is None:
        return (0, 0)

    updated = missing = 0
    for entry in entries:
        if not entry.get("isResult"):
            continue
        home_name = entry.get("h", {}).get("title", "")
        away_name = entry.get("a", {}).get("title", "")
        try:
            home_xg = float(entry["xG"]["h"])
            away_xg = float(entry["xG"]["a"])
        except (KeyError, TypeError, ValueError):
            continue

        home_team = resolve_team(home_name, source=SOURCE)
        away_team = resolve_team(away_name, source=SOURCE)

        match = Match.objects.filter(
            season=season, league=league, home_team=home_team, away_team=away_team
        ).first()
        if match is None:
            missing += 1
            continue

        for team, is_home, xg, xga in (
            (home_team, True, home_xg, away_xg),
            (away_team, False, away_xg, home_xg),
        ):
            stat, _ = MatchTeamStat.objects.get_or_create(
                match=match, team=team, defaults={"is_home": is_home}
            )
            stat.expected_goals = xg
            stat.expected_goals_against = xga
            stat.save(update_fields=["expected_goals", "expected_goals_against"])
        updated += 1

    log.info("%s %s understat xG: %d matches updated, %d not found",
             league.name, season.name, updated, missing)
    return (updated, missing)
